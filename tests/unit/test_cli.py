import sys
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

import ephemeral_pulumi_deploy.cli as cli_module
from ephemeral_pulumi_deploy.cli import run_cli

arbitrary_stack_name = str(uuid4())


def test_cancel_calls_stack_cancel_and_exits_zero(mocker: MockerFixture):
    mock_stack = MagicMock()
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, return_value=mock_stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--cancel"])

    with pytest.raises(SystemExit, match="0") as exc_info:
        run_cli(stack_config={}, pulumi_program=MagicMock())

    assert exc_info.value.code == 0
    mock_stack.cancel.assert_called_once_with()


def test_up_without_refresh_passes_refresh_false_to_up(mocker: MockerFixture):
    mock_stack = MagicMock()
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, return_value=mock_stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--up"])

    run_cli(stack_config={}, pulumi_program=MagicMock())

    mock_stack.up.assert_called_once_with(diff=True, on_output=print, refresh=False)


def test_up_with_refresh_passes_refresh_true_to_up(mocker: MockerFixture):
    mock_stack = MagicMock()
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, return_value=mock_stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--up", "--refresh"])

    run_cli(stack_config={}, pulumi_program=MagicMock())

    mock_stack.up.assert_called_once_with(diff=True, on_output=print, refresh=True)
    mock_stack.refresh.assert_not_called()


def test_refresh_standalone_calls_stack_refresh(mocker: MockerFixture):
    mock_stack = MagicMock()
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, return_value=mock_stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--refresh"])

    run_cli(stack_config={}, pulumi_program=MagicMock())

    mock_stack.refresh.assert_called_once_with(on_output=print)
    mock_stack.up.assert_not_called()
    mock_stack.preview.assert_not_called()


def test_preview_with_refresh_passes_refresh_true_to_preview(mocker: MockerFixture):
    mock_stack = MagicMock()
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, return_value=mock_stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--preview", "--refresh"])

    run_cli(stack_config={}, pulumi_program=MagicMock())

    mock_stack.preview.assert_called_once_with(diff=True, on_output=print, refresh=True)
    mock_stack.refresh.assert_not_called()
    mock_stack.up.assert_not_called()


def test_default_no_flags_calls_preview_with_refresh_false(mocker: MockerFixture):
    mock_stack = MagicMock()
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, return_value=mock_stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name])

    run_cli(stack_config={}, pulumi_program=MagicMock())

    mock_stack.preview.assert_called_once_with(diff=True, on_output=print, refresh=False)
    mock_stack.up.assert_not_called()
    mock_stack.refresh.assert_not_called()


def test_destroy_on_non_protected_stack_destroys_and_removes(mocker: MockerFixture):
    mock_stack = MagicMock()
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, return_value=mock_stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", arbitrary_stack_name, "--destroy"])

    with pytest.raises(SystemExit, match="0") as exc_info:
        run_cli(stack_config={}, pulumi_program=MagicMock())

    assert exc_info.value.code == 0
    mock_stack.destroy.assert_called_once_with(on_output=print)
    mock_stack.workspace.remove_stack.assert_called_once_with(arbitrary_stack_name)


def test_destroy_protected_stack_without_force_exits_one(mocker: MockerFixture):
    mock_get_stack = mocker.patch.object(cli_module, cli_module.get_stack.__name__)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", "prod-stack", "--destroy"])

    with pytest.raises(SystemExit, match="1") as exc_info:
        run_cli(stack_config={}, pulumi_program=MagicMock())

    assert exc_info.value.code == 1
    mock_get_stack.assert_not_called()


def test_destroy_protected_stack_with_force_destroy_proceeds(mocker: MockerFixture):
    mock_stack = MagicMock()
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, return_value=mock_stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", "prod-stack", "--destroy", "--force-destroy"])

    with pytest.raises(SystemExit, match="0"):
        run_cli(stack_config={}, pulumi_program=MagicMock())

    mock_stack.destroy.assert_called_once_with(on_output=print)


def test_custom_exit_code_env_var_causes_exit_with_that_code(mocker: MockerFixture):
    custom_exit_code = 42
    mock_stack = MagicMock()
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, return_value=mock_stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", "test-stack"])
    _ = mocker.patch.dict(cli_module.os.environ, {"CUSTOM_PULUMI_OPERATION_EXIT_CODE": str(custom_exit_code)})

    with pytest.raises(SystemExit, match=str(custom_exit_code)) as exc_info:
        run_cli(stack_config={}, pulumi_program=MagicMock())

    assert exc_info.value.code == custom_exit_code


def test_custom_exit_code_non_numeric_raises(mocker: MockerFixture):
    mock_stack = MagicMock()
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, return_value=mock_stack)
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


def test_outputs_does_not_invoke_stack_operations(mocker: MockerFixture):
    mock_stack = MagicMock()
    mock_stack.outputs.return_value = {}
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, return_value=mock_stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", "test-stack", "--outputs"])

    with pytest.raises(SystemExit, match="0"):
        run_cli(stack_config={}, pulumi_program=MagicMock())

    mock_stack.up.assert_not_called()
    mock_stack.preview.assert_not_called()
    mock_stack.refresh.assert_not_called()
    mock_stack.destroy.assert_not_called()


def test_outputs_prints_values_and_masks_secrets(mocker: MockerFixture, capsys: pytest.CaptureFixture[str]):
    mock_stack = MagicMock()
    plain_output = MagicMock()
    plain_output.value = "hello"
    plain_output.secret = False
    secret_output = MagicMock()
    secret_output.value = "s3cr3t"
    secret_output.secret = True
    mock_stack.outputs.return_value = {"greeting": plain_output, "token": secret_output}
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, return_value=mock_stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", "test-stack", "--outputs"])

    with pytest.raises(SystemExit, match="0") as exc_info:
        run_cli(stack_config={}, pulumi_program=MagicMock())

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "greeting: hello" in captured.out
    assert "token: [secret]" in captured.out
    assert "s3cr3t" not in captured.out


def test_outputs_with_show_secrets_reveals_secret_values(mocker: MockerFixture, capsys: pytest.CaptureFixture[str]):
    mock_stack = MagicMock()
    secret_output = MagicMock()
    secret_output.value = "s3cr3t"
    secret_output.secret = True
    mock_stack.outputs.return_value = {"token": secret_output}
    _ = mocker.patch.object(cli_module, cli_module.get_stack.__name__, return_value=mock_stack)
    _ = mocker.patch.object(sys, "argv", new=["cli", "--stack", "test-stack", "--outputs", "--show-secrets"])

    with pytest.raises(SystemExit, match="0"):
        run_cli(stack_config={}, pulumi_program=MagicMock())

    captured = capsys.readouterr()
    assert "token: s3cr3t" in captured.out
