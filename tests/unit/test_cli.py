import sys
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

import ephemeral_pulumi_deploy.cli as cli_module
from ephemeral_pulumi_deploy.cli import run_cli


def test_cancel_calls_stack_cancel_and_exits_zero(mocker: MockerFixture):
    mock_stack = MagicMock()
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, return_value=mock_stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", "test-stack", "--cancel"])

    with pytest.raises(SystemExit, match="0") as exc_info:
        run_cli(stack_config={}, pulumi_program=MagicMock())

    assert exc_info.value.code == 0
    mock_stack.cancel.assert_called_once_with()
