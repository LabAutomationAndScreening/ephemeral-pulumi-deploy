import json
import logging
import sys
from unittest.mock import ANY
from unittest.mock import MagicMock
from uuid import uuid4

import boto3
import pytest
from faker import Faker
from pulumi.automation import CommandResult
from pulumi.automation import LocalWorkspace
from pulumi.automation import OutputValue
from pulumi.automation import Stack
from pulumi.automation import StackNotFoundError
from pytest_mock import MockerFixture

import ephemeral_pulumi_deploy.cli as cli_module
import ephemeral_pulumi_deploy.utils as utils_module
from ephemeral_pulumi_deploy.cli import run_cli

arbitrary_stack_name = str(uuid4())
ARGPARSE_USAGE_ERROR_EXIT_CODE = 2


def _select_stack(mocker: MockerFixture) -> Stack:
    return Stack.select(arbitrary_stack_name, mocker.create_autospec(LocalWorkspace, instance=True))


def _patch_stack_with_outputs(mocker: MockerFixture, outputs: dict[str, OutputValue]) -> None:
    stack = _select_stack(mocker)
    _ = mocker.patch.object(Stack, Stack.outputs.__name__, autospec=True, return_value=outputs)
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, autospec=True, return_value=stack)


def test_cancel_calls_stack_cancel_and_exits_zero(mocker: MockerFixture):
    stack = _select_stack(mocker)
    cancel_spy = mocker.patch.object(Stack, Stack.cancel.__name__, autospec=True)
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, autospec=True, return_value=stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--cancel"])

    with pytest.raises(SystemExit, match="0") as exc_info:
        run_cli(stack_config={}, pulumi_program=MagicMock())

    assert exc_info.value.code == 0
    cancel_spy.assert_called_once_with(stack)


def test_up_without_refresh_passes_refresh_false_to_up(mocker: MockerFixture):
    stack = _select_stack(mocker)
    up_spy = mocker.patch.object(Stack, Stack.up.__name__, autospec=True)
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, autospec=True, return_value=stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--up"])

    run_cli(stack_config={}, pulumi_program=MagicMock())

    up_spy.assert_called_once_with(stack, diff=True, on_output=print, refresh=False)


def test_up_with_refresh_passes_refresh_true_to_up(mocker: MockerFixture):
    stack = _select_stack(mocker)
    up_spy = mocker.patch.object(Stack, Stack.up.__name__, autospec=True)
    refresh_spy = mocker.patch.object(Stack, Stack.refresh.__name__, autospec=True)
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, autospec=True, return_value=stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--up", "--refresh"])

    run_cli(stack_config={}, pulumi_program=MagicMock())

    up_spy.assert_called_once_with(stack, diff=True, on_output=print, refresh=True)
    refresh_spy.assert_not_called()


def test_refresh_standalone_calls_stack_refresh(mocker: MockerFixture):
    stack = _select_stack(mocker)
    refresh_spy = mocker.patch.object(Stack, Stack.refresh.__name__, autospec=True)
    up_spy = mocker.patch.object(Stack, Stack.up.__name__, autospec=True)
    preview_spy = mocker.patch.object(Stack, Stack.preview.__name__, autospec=True)
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, autospec=True, return_value=stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--refresh"])

    run_cli(stack_config={}, pulumi_program=MagicMock())

    refresh_spy.assert_called_once_with(stack, on_output=print)
    up_spy.assert_not_called()
    preview_spy.assert_not_called()


def test_preview_with_refresh_passes_refresh_true_to_preview(mocker: MockerFixture):
    stack = _select_stack(mocker)
    preview_spy = mocker.patch.object(Stack, Stack.preview.__name__, autospec=True)
    refresh_spy = mocker.patch.object(Stack, Stack.refresh.__name__, autospec=True)
    up_spy = mocker.patch.object(Stack, Stack.up.__name__, autospec=True)
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, autospec=True, return_value=stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--preview", "--refresh"])

    run_cli(stack_config={}, pulumi_program=MagicMock())

    preview_spy.assert_called_once_with(stack, diff=True, on_output=print, refresh=True)
    refresh_spy.assert_not_called()
    up_spy.assert_not_called()


def test_default_no_flags_calls_preview_with_refresh_false(mocker: MockerFixture):
    stack = _select_stack(mocker)
    preview_spy = mocker.patch.object(Stack, Stack.preview.__name__, autospec=True)
    up_spy = mocker.patch.object(Stack, Stack.up.__name__, autospec=True)
    refresh_spy = mocker.patch.object(Stack, Stack.refresh.__name__, autospec=True)
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, autospec=True, return_value=stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name])

    run_cli(stack_config={}, pulumi_program=MagicMock())

    preview_spy.assert_called_once_with(stack, diff=True, on_output=print, refresh=False)
    up_spy.assert_not_called()
    refresh_spy.assert_not_called()


def test_destroy_on_non_protected_stack_destroys_and_removes(mocker: MockerFixture):
    workspace = mocker.create_autospec(LocalWorkspace, instance=True)
    remove_stack_spy = mocker.patch.object(workspace, LocalWorkspace.remove_stack.__name__)
    stack = Stack.select(arbitrary_stack_name, workspace)
    destroy_spy = mocker.patch.object(Stack, Stack.destroy.__name__, autospec=True)
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, autospec=True, return_value=stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--destroy"])

    with pytest.raises(SystemExit, match="0") as exc_info:
        run_cli(stack_config={}, pulumi_program=MagicMock())

    assert exc_info.value.code == 0
    destroy_spy.assert_called_once_with(stack, on_output=print)
    remove_stack_spy.assert_called_once_with(arbitrary_stack_name)


def test_destroy_protected_stack_without_force_exits_one(mocker: MockerFixture):
    mock_get_stack = mocker.patch.object(cli_module, cli_module.get_stack.__name__)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", "prod-stack", "--destroy"])

    with pytest.raises(SystemExit, match="1") as exc_info:
        run_cli(stack_config={}, pulumi_program=MagicMock())

    assert exc_info.value.code == 1
    mock_get_stack.assert_not_called()


def test_destroy_protected_stack_with_force_destroy_proceeds(mocker: MockerFixture):
    stack = _select_stack(mocker)
    destroy_spy = mocker.patch.object(Stack, Stack.destroy.__name__, autospec=True)
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, autospec=True, return_value=stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", "prod-stack", "--destroy", "--force-destroy"])

    with pytest.raises(SystemExit, match="0"):
        run_cli(stack_config={}, pulumi_program=MagicMock())

    destroy_spy.assert_called_once_with(stack, on_output=print)


def test_custom_exit_code_env_var_causes_exit_with_that_code(mocker: MockerFixture):
    custom_exit_code = 42
    stack = _select_stack(mocker)
    _ = mocker.patch.object(Stack, Stack.preview.__name__, autospec=True)
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, autospec=True, return_value=stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", "test-stack"])
    _ = mocker.patch.dict(cli_module.os.environ, {"CUSTOM_PULUMI_OPERATION_EXIT_CODE": str(custom_exit_code)})

    with pytest.raises(SystemExit, match=str(custom_exit_code)) as exc_info:
        run_cli(stack_config={}, pulumi_program=MagicMock())

    assert exc_info.value.code == custom_exit_code


def test_custom_exit_code_non_numeric_raises(mocker: MockerFixture):
    stack = _select_stack(mocker)
    _ = mocker.patch.object(Stack, Stack.preview.__name__, autospec=True)
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, autospec=True, return_value=stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", "test-stack"])
    _ = mocker.patch.dict(cli_module.os.environ, {"CUSTOM_PULUMI_OPERATION_EXIT_CODE": "bad"})

    with pytest.raises(NotImplementedError, match="bad"):
        run_cli(stack_config={}, pulumi_program=MagicMock())


def test_slash_in_stack_name_is_replaced_with_dash(mocker: MockerFixture):
    mock_get_stack = mocker.patch.object(cli_module, cli_module.get_stack.__name__, return_value=MagicMock())
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", "feature/my-branch"])

    run_cli(stack_config={}, pulumi_program=MagicMock())

    actual_stack_name = mock_get_stack.call_args.kwargs["stack_name"]
    assert actual_stack_name == "feature-my-branch"


def test_When_json_passed_without_outputs__Then_usage_error_names_both_flags_before_stack_is_loaded(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
):
    get_stack_spy = mocker.patch.object(cli_module, cli_module.get_stack.__name__, autospec=True)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--json"])

    with pytest.raises(SystemExit, match=str(ARGPARSE_USAGE_ERROR_EXIT_CODE)) as exc_info:
        run_cli(stack_config={}, pulumi_program=MagicMock())

    error_line = capsys.readouterr().err.strip().splitlines()[-1]

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR_EXIT_CODE
    assert "--json" in error_line
    assert "--outputs" in error_line
    get_stack_spy.assert_not_called()


class TestGivenStackWithPlainAndSecretOutputs:
    @pytest.fixture(autouse=True)
    def _setup(self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str], faker: Faker):
        self.mocker = mocker
        self.capsys = capsys
        self.plain_key = faker.unique.pystr()
        self.plain_value = faker.sentence()
        self.secret_key = faker.unique.pystr()
        self.secret_value = faker.password()
        _patch_stack_with_outputs(
            mocker,
            {
                self.plain_key: OutputValue(value=self.plain_value, secret=False),
                self.secret_key: OutputValue(value=self.secret_value, secret=True),
            },
        )

    def test_When_outputs__Then_prints_one_line_per_output_with_secrets_masked_without_stack_operations(self):
        up_spy = self.mocker.patch.object(Stack, Stack.up.__name__, autospec=True)
        preview_spy = self.mocker.patch.object(Stack, Stack.preview.__name__, autospec=True)
        refresh_spy = self.mocker.patch.object(Stack, Stack.refresh.__name__, autospec=True)
        destroy_spy = self.mocker.patch.object(Stack, Stack.destroy.__name__, autospec=True)
        _ = self.mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--outputs"])

        with pytest.raises(SystemExit, match="0") as exc_info:
            run_cli(stack_config={}, pulumi_program=MagicMock())

        stdout = self.capsys.readouterr().out

        assert exc_info.value.code == 0
        assert stdout == f"{self.plain_key}: {self.plain_value}\n{self.secret_key}: [secret]\n"
        up_spy.assert_not_called()
        preview_spy.assert_not_called()
        refresh_spy.assert_not_called()
        destroy_spy.assert_not_called()

    def test_When_outputs_with_show_secrets__Then_secret_values_are_revealed(self):
        _ = self.mocker.patch.object(
            sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--outputs", "--show-secrets"]
        )

        with pytest.raises(SystemExit, match="0"):
            run_cli(stack_config={}, pulumi_program=MagicMock())

        stdout = self.capsys.readouterr().out

        assert stdout == f"{self.plain_key}: {self.plain_value}\n{self.secret_key}: {self.secret_value}\n"

    def test_When_outputs_with_json__Then_prints_single_line_json_object_with_secrets_masked_without_stack_operations(
        self,
    ):
        up_spy = self.mocker.patch.object(Stack, Stack.up.__name__, autospec=True)
        preview_spy = self.mocker.patch.object(Stack, Stack.preview.__name__, autospec=True)
        refresh_spy = self.mocker.patch.object(Stack, Stack.refresh.__name__, autospec=True)
        destroy_spy = self.mocker.patch.object(Stack, Stack.destroy.__name__, autospec=True)
        _ = self.mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--outputs", "--json"])

        with pytest.raises(SystemExit, match="0") as exc_info:
            run_cli(stack_config={}, pulumi_program=MagicMock())

        stdout = self.capsys.readouterr().out

        assert exc_info.value.code == 0
        assert len(stdout.splitlines()) == 1
        assert json.loads(stdout) == {self.plain_key: self.plain_value, self.secret_key: "[secret]"}
        assert self.secret_value not in stdout
        up_spy.assert_not_called()
        preview_spy.assert_not_called()
        refresh_spy.assert_not_called()
        destroy_spy.assert_not_called()

    def test_When_outputs_with_json_and_show_secrets__Then_secret_values_are_revealed(self):
        _ = self.mocker.patch.object(
            sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--outputs", "--json", "--show-secrets"]
        )

        with pytest.raises(SystemExit, match="0"):
            run_cli(stack_config={}, pulumi_program=MagicMock())

        stdout = self.capsys.readouterr().out

        assert json.loads(stdout) == {self.plain_key: self.plain_value, self.secret_key: self.secret_value}


def test_Given_dict_and_list_output_values__When_outputs_with_json__Then_values_stay_native_json_structures(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str], faker: Faker
):
    dict_key = faker.unique.pystr()
    dict_value = {faker.unique.pystr(): [faker.word(), faker.pyint()], faker.unique.pystr(): faker.pybool()}
    list_key = faker.unique.pystr()
    list_value = [faker.word(), {faker.unique.pystr(): faker.pyint()}]
    _patch_stack_with_outputs(
        mocker,
        {
            dict_key: OutputValue(value=dict_value, secret=False),
            list_key: OutputValue(value=list_value, secret=False),
        },
    )
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--outputs", "--json"])

    with pytest.raises(SystemExit, match="0"):
        run_cli(stack_config={}, pulumi_program=MagicMock())

    stdout = capsys.readouterr().out

    assert json.loads(stdout) == {dict_key: dict_value, list_key: list_value}


def test_Given_stack_without_outputs__When_outputs_with_json__Then_prints_empty_json_object(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
):
    _patch_stack_with_outputs(mocker, {})
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--outputs", "--json"])

    with pytest.raises(SystemExit, match="0"):
        run_cli(stack_config={}, pulumi_program=MagicMock())

    stdout = capsys.readouterr().out

    assert stdout == "{}\n"


def _patch_aws_account_lookups(mocker: MockerFixture, faker: Faker) -> None:
    aws_client = mocker.patch.object(boto3, boto3.Session.__name__).return_value.client.return_value
    aws_client.get_caller_identity.return_value = {"Account": faker.numerify("#" * utils_module.AWS_ACCOUNT_ID_LENGTH)}
    aws_client.get_parameter.return_value = {"Parameter": {"Value": faker.pystr()}}


class TestGivenNoStackWithRequestedName:
    @pytest.fixture(autouse=True)
    def _setup(self, mocker: MockerFixture, faker: Faker):
        self.mocker = mocker
        self.stack_config = {
            "proj:pulumi_project_name": faker.slug(),
            "proj:github_repo_name": faker.slug(),
        }
        _patch_aws_account_lookups(mocker, faker)
        self.select_stack_spy = mocker.patch.object(
            utils_module,
            utils_module.select_stack.__name__,
            autospec=True,
            side_effect=StackNotFoundError(
                CommandResult(stdout=faker.sentence(), stderr=faker.sentence(), code=faker.pyint(min_value=1))
            ),
        )
        self.create_or_select_stack_spy = mocker.patch.object(
            utils_module, utils_module.create_or_select_stack.__name__, autospec=True
        )

    @pytest.mark.parametrize(
        "action_flags",
        [
            pytest.param(["--outputs"], id="outputs-human-readable-listing"),
            pytest.param(["--outputs", "--json"], id="outputs-json-so-callers-never-parse-an-empty-object"),
            pytest.param(["--cancel"], id="cancel"),
            pytest.param(["--destroy"], id="destroy"),
        ],
    )
    def test_When_action_requiring_prior_deploy__Then_exits_one_logging_error_naming_stack_without_printing_or_creating_it(
        self, action_flags: list[str], capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
    ):
        _ = self.mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, *action_flags])

        with pytest.raises(SystemExit, match="1") as exc_info:
            run_cli(stack_config=self.stack_config, pulumi_program=MagicMock())

        stdout = capsys.readouterr().out
        error_messages = [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR]

        assert exc_info.value.code == 1
        assert len(error_messages) == 1
        assert arbitrary_stack_name in error_messages[0]
        assert stdout == ""
        self.create_or_select_stack_spy.assert_not_called()

    @pytest.mark.parametrize(
        "action_flags",
        [
            pytest.param(["--up"], id="up"),
            pytest.param(["--preview"], id="preview"),
            pytest.param(["--refresh"], id="standalone-refresh"),
            pytest.param([], id="no-action-flag-defaults-to-preview"),
        ],
    )
    def test_When_action_valid_before_first_deploy__Then_stack_is_created(self, action_flags: list[str]):
        pulumi_program = MagicMock()
        _ = self.mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, *action_flags])

        run_cli(stack_config=self.stack_config, pulumi_program=pulumi_program)

        self.create_or_select_stack_spy.assert_called_once_with(
            arbitrary_stack_name,
            project_name=self.stack_config["proj:pulumi_project_name"],
            program=pulumi_program,
            opts=ANY,
        )
        self.select_stack_spy.assert_not_called()
