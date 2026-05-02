import pytest

from inspectors.active_directory_command_runner import (
    ActiveDirectoryCommand,
    ActiveDirectoryCommandResult,
    ActiveDirectoryCommandValidationError,
    MockActiveDirectoryCommandRunner,
    is_read_only_active_directory_command,
    validate_read_only_active_directory_command,
)


@pytest.mark.parametrize(
    "command_name",
    [
        "Get-ADUser",
        "Get-ADGroup",
        "Get-ADPrincipalGroupMembership",
    ],
)
def test_validate_read_only_active_directory_command_allows_allowlisted_get_commands(
    command_name,
):
    command = ActiveDirectoryCommand(
        name=command_name,
        parameters={"Identity": "user@example.com"},
    )

    validate_read_only_active_directory_command(command)


@pytest.mark.parametrize(
    "command_name",
    [
        "Set-ADUser",
        "Set-ADAccountPassword",
        "New-ADUser",
        "New-ADGroup",
        "Remove-ADUser",
        "Remove-ADGroup",
        "Add-ADGroupMember",
        "Clear-ADAccountAuthenticationPolicySilo",
        "Enable-ADAccount",
        "Disable-ADAccount",
        "Unlock-ADAccount",
        "Move-ADObject",
        "Rename-ADObject",
        "Reset-ADServiceAccountPassword",
    ],
)
def test_validate_read_only_active_directory_command_rejects_forbidden_prefixes(
    command_name,
):
    command = ActiveDirectoryCommand(
        name=command_name,
        parameters={"Identity": "user@example.com"},
    )

    with pytest.raises(
        ActiveDirectoryCommandValidationError,
        match="forbidden for inspectors",
    ):
        validate_read_only_active_directory_command(command)


def test_validate_read_only_active_directory_command_rejects_unknown_get_command():
    command = ActiveDirectoryCommand(
        name="Get-ADGroupMember",
        parameters={"Identity": "Engineers"},
    )

    with pytest.raises(
        ActiveDirectoryCommandValidationError,
        match="not allowlisted for inspectors",
    ):
        validate_read_only_active_directory_command(command)


def test_validate_read_only_active_directory_command_rejects_empty_command_name():
    command = ActiveDirectoryCommand(name="   ", parameters={})

    with pytest.raises(
        ActiveDirectoryCommandValidationError,
        match="cannot be empty",
    ):
        validate_read_only_active_directory_command(command)


def test_is_read_only_active_directory_command_returns_true_for_allowlisted_command():
    command = ActiveDirectoryCommand(
        name="Get-ADUser",
        parameters={"Identity": "user@example.com"},
    )

    assert is_read_only_active_directory_command(command) is True


def test_is_read_only_active_directory_command_returns_false_for_forbidden_command():
    command = ActiveDirectoryCommand(
        name="Set-ADUser",
        parameters={"Identity": "user@example.com"},
    )

    assert is_read_only_active_directory_command(command) is False


def test_mock_active_directory_command_runner_returns_configured_result():
    expected = ActiveDirectoryCommandResult(
        command="Get-ADUser",
        ok=True,
        data={"DisplayName": "Example User"},
    )
    runner = MockActiveDirectoryCommandRunner(results={"Get-ADUser": expected})

    result = runner.run(
        ActiveDirectoryCommand(
            name="Get-ADUser",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert result is expected
    assert [command.name for command in runner.commands] == ["Get-ADUser"]


def test_mock_active_directory_command_runner_validates_before_recording():
    runner = MockActiveDirectoryCommandRunner()

    with pytest.raises(
        ActiveDirectoryCommandValidationError,
        match="forbidden for inspectors",
    ):
        runner.run(
            ActiveDirectoryCommand(
                name="Set-ADUser",
                parameters={"Identity": "user@example.com"},
            )
        )

    # Forbidden commands must NOT be recorded as if they were attempted.
    assert runner.commands == []


def test_mock_active_directory_command_runner_returns_default_when_no_result_configured():
    runner = MockActiveDirectoryCommandRunner()

    result = runner.run(
        ActiveDirectoryCommand(
            name="Get-ADUser",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert result.ok is False
    assert "No mock result configured" in (result.error or "")
