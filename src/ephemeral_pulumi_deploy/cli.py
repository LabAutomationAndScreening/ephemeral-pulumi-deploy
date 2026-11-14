import argparse
import json
import logging
import os
import sys
from collections.abc import Callable
from typing import Any

from pulumi.automation import PulumiFn
from pulumi.automation import Stack
from pulumi.automation import StackNotFoundError
from typing_extensions import TypedDict

from .utils import PROTECTED_ENVS
from .utils import get_env_from_cli_input
from .utils import get_stack
from .utils import parser
from .utils import result_to_str

logger = logging.getLogger(__name__)


class StackKwargs(TypedDict, closed=True):
    diff: bool
    on_output: Callable[[str], None]


def _parse_args() -> argparse.Namespace:
    args = parser.parse_args()
    if args.json:
        if not args.outputs:
            parser.error("--json requires --outputs")
    return args


def _print_outputs(*, stack: Stack, show_secrets: bool, as_json: bool) -> None:
    printable_outputs: dict[str, object] = {}
    for key, output in stack.outputs().items():
        value = output.value
        if output.secret:
            if not show_secrets:
                value = "[secret]"
        printable_outputs[key] = value
    if as_json:
        print(json.dumps(printable_outputs))  # noqa: T201 # stdout is the machine-readable channel consumed by callers
        return
    for key, value in printable_outputs.items():
        print(f"{key}: {value}")  # noqa: T201 # stdout is the human-readable listing for the person running the CLI


def _action_is_valid_before_first_deploy(args: argparse.Namespace) -> bool:
    if args.outputs:
        return False
    if args.cancel:
        return False
    return True


def _load_stack(
    *,
    stack_name: str,
    pulumi_program: PulumiFn,
    stack_config: dict[str, Any],  # pyrefly: ignore[explicit-any] # passed through unchanged to get_stack, whose parameter has this type
    create_if_missing: bool,
) -> Stack:
    try:
        return get_stack(
            stack_name=stack_name,
            pulumi_program=pulumi_program,
            stack_config=stack_config,
            create_if_missing=create_if_missing,
        )
    except StackNotFoundError:
        logger.error(  # noqa: TRY400 # a missing stack is an expected user mistake (typo or not yet deployed), so a traceback would only bury the message
            f"Stack {stack_name} was not found. It may not have been deployed yet."
        )
        sys.exit(1)


# TODO: consider accepting Mapping[str, object] so callers can pass dicts with narrower value types. get_stack would then need to write its injected keys into a copy instead of the caller's dict, and narrow the values it reads to str.
def run_cli(
    *,
    stack_config: dict[str, Any],  # pyrefly: ignore[explicit-any] # matches Pulumi's own StackSettings.config type, and lets callers pass dicts with narrower value types (dict is invariant)
    pulumi_program: PulumiFn,
) -> None:
    args = _parse_args()
    stack_name = str(
        args.stack
    ).replace(
        "/", "-"
    )  # replace characters sometimes used in git branch names (for test/feature branches) that are incompatible with Pulumi and/or AWS resource naming

    env = get_env_from_cli_input(stack_name)

    if (env in PROTECTED_ENVS) and args.destroy and not args.force_destroy:
        logger.error(f"Stack {stack_name} can't be destroyed, because it's not a test/dev stack.")
        sys.exit(1)

    stack = _load_stack(
        stack_name=stack_name,
        pulumi_program=pulumi_program,
        stack_config=stack_config,
        create_if_missing=_action_is_valid_before_first_deploy(args),
    )

    if args.cancel:
        stack.cancel()
        logger.info("Stack update cancelled.")
        sys.exit(0)

    # if destroy then teardown and exit
    if args.destroy:
        destroy_response = stack.destroy(on_output=print)
        destroy_response_str = result_to_str(destroy_response)
        logger.info(destroy_response_str)
        # I see no reason not to completely remove the stack and history after destroying it. There is no returned output from the command https://github.com/pulumi/pulumi/blob/06ba63bb57e90706c1550861b785075ae860144a/sdk/python/lib/pulumi/automation/_local_workspace.py#L277
        stack.workspace.remove_stack(stack_name)
        sys.exit(0)

    if args.outputs:
        _print_outputs(stack=stack, show_secrets=args.show_secrets, as_json=args.json)
        sys.exit(0)

    up_and_preview_kwargs: StackKwargs = {
        "diff": True,
        "on_output": print,
        # 'on_event': print   # TODO: figure out how to log these? Seems too verbose to print to stdout though
    }

    if args.up:
        response = stack.up(**up_and_preview_kwargs, refresh=args.refresh)
    elif args.refresh and not args.preview:
        response = stack.refresh(on_output=print)
    else:  # plan only
        # TODO: Make use of this feature to guarantee the plan is what is actually executed https://www.pulumi.com/blog/announcing-public-preview-update-plans/
        response = stack.preview(**up_and_preview_kwargs, refresh=args.refresh)

    response_str = result_to_str(response)
    logger.info(response_str)

    try:
        custom_exit_code = os.environ["CUSTOM_PULUMI_OPERATION_EXIT_CODE"]
        if not custom_exit_code.isnumeric():
            raise NotImplementedError(f"Exit codes should always be set to integers, but received {custom_exit_code}")
        print(  # noqa: T201 # TODO: figure out a way to log this that also shows up in stdout in CI
            f"Exiting with non-zero custom error code {custom_exit_code}.  Look back through output to find the reason."
        )
        sys.exit(int(custom_exit_code))
    except KeyError:
        pass
