import pulumi
from pytest_mock import MockerFixture

from ephemeral_pulumi_deploy import append_resource_suffix


def test_Given_long_stack_name__Then_truncated(mocker: MockerFixture):
    resource_name = "foobar"
    long_stack_name = "this-is-a-very-long-stack-name"
    _ = mocker.patch.object(pulumi, "get_stack", autospec=True, return_value=long_stack_name)
    _ = mocker.patch.object(pulumi, "get_project", autospec=True, return_value="project")

    actual_full_name = append_resource_suffix(resource_name)

    assert actual_full_name.endswith(long_stack_name[:7])
