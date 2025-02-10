import random
import string

import pulumi
import pytest
from pytest_mock import MockerFixture

from ephemeral_pulumi_deploy import append_resource_suffix


def test_Given_long_stack_name__Then_truncated(mocker: MockerFixture):
    resource_name = "foobar"
    long_stack_name = "this-is-a-very-long-stack-name"
    _ = mocker.patch.object(pulumi, "get_stack", autospec=True, return_value=long_stack_name)
    _ = mocker.patch.object(pulumi, "get_project", autospec=True, return_value="project")

    actual_full_name = append_resource_suffix(resource_name)

    assert actual_full_name.endswith(long_stack_name[:7])


class TestGivenMockedStackAndProject:
    @pytest.fixture(autouse=True)
    def _setup(self, mocker: MockerFixture):
        self.stack_value = "".join(random.choices(string.ascii_lowercase, k=10))
        _ = mocker.patch.object(pulumi, "get_stack", autospec=True, return_value=self.stack_value)

        _ = mocker.patch.object(
            pulumi, "get_project", autospec=True, return_value="".join(random.choices(string.ascii_lowercase, k=10))
        )

    def test_Given_longer_limit_allowed__When_long_name__Then_no_error(self):
        resource_name = "".join(random.choices(string.ascii_lowercase, k=70))
        actual_full_name = append_resource_suffix(resource_name, max_length=100)

        assert len(actual_full_name) > len(resource_name)
