import pytest

from inspectors.exchange_command_runner import (
    ExchangeCommandValidationError,
    ExchangePowerShellCommand,
    ExchangePowerShellCommandResult,
    MockExchangePowerShellCommandRunner,
    is_read_only_exchange_command,
    validate_read_only_exchange_command,
)


@pytest.mark.parametrize(
    "command_name",
    [
        "Get-EXOMailbox",
        "Get-EXOMailboxStatistics",
        "Get-Mailbox",
    ],
)
def test_validate_read_only_exchange_command_allows_allowlisted_get_commands(
    command_name,
):
    command = ExchangePowerShellCommand(
        name=command_name,
        parameters={"Identity": "user@example.com"},
    )

    validate_read_only_exchange_command(command)


@pytest.mark.parametrize(
    "command_name",
    [
        "Set-Mailbox",
        "New-Mailbox",
        "Remove-Mailbox",
        "Enable-Mailbox",
        "Disable-Mailbox",
        "Add-MailboxPermission",
        "Remove-MailboxPermission",
        "Clear-MobileDevice",
        "Update-DistributionGroupMember",
        "Start-ManagedFolderAssistant",
        "Stop-ComplianceSearch",
        "Restart-Service",
    ],
)
def test_validate_read_only_exchange_command_rejects_forbidden_prefixes(
    command_name,
):
    command = ExchangePowerShellCommand(
        name=command_name,
        parameters={"Identity": "user@example.com"},
    )

    with pytest.raises(
        ExchangeCommandValidationError,
        match="forbidden for inspectors",
    ):
        validate_read_only_exchange_command(command)


def test_validate_read_only_exchange_command_rejects_unknown_get_command():
    command = ExchangePowerShellCommand(
        name="Get-InboxRule",
        parameters={"Mailbox": "user@example.com"},
    )

    with pytest.raises(
        ExchangeCommandValidationError,
        match="not allowlisted for inspectors",
    ):
        validate_read_only_exchange_command(command)


def test_validate_read_only_exchange_command_rejects_empty_command_name():
    command = ExchangePowerShellCommand(
        name="   ",
        parameters={},
    )

    with pytest.raises(
        ExchangeCommandValidationError,
        match="cannot be empty",
    ):
        validate_read_only_exchange_command(command)


def test_is_read_only_exchange_command_returns_true_for_allowlisted_command():
    command = ExchangePowerShellCommand(
        name="Get-EXOMailbox",
        parameters={"Identity": "user@example.com"},
    )

    assert is_read_only_exchange_command(command) is True


def test_is_read_only_exchange_command_returns_false_for_forbidden_command():
    command = ExchangePowerShellCommand(
        name="Set-Mailbox",
        parameters={"Identity": "user@example.com"},
    )

    assert is_read_only_exchange_command(command) is False


def test_mock_exchange_command_runner_returns_configured_result():
    command = ExchangePowerShellCommand(
        name="Get-EXOMailbox",
        parameters={"Identity": "user@example.com"},
    )
    configured_result = ExchangePowerShellCommandResult(
        command="Get-EXOMailbox",
        ok=True,
        data={
            "DisplayName": "Example User",
            "PrimarySmtpAddress": "user@example.com",
        },
    )
    runner = MockExchangePowerShellCommandRunner(
        results={
            "Get-EXOMailbox": configured_result,
        }
    )

    result = runner.run(command)

    assert result is configured_result
    assert runner.commands == [command]


def test_mock_exchange_command_runner_validates_before_recording_command():
    command = ExchangePowerShellCommand(
        name="Set-Mailbox",
        parameters={"Identity": "user@example.com"},
    )
    runner = MockExchangePowerShellCommandRunner()

    with pytest.raises(
        ExchangeCommandValidationError,
        match="forbidden for inspectors",
    ):
        runner.run(command)

    assert runner.commands == []


def test_mock_exchange_command_runner_returns_error_for_missing_mock_result():
    command = ExchangePowerShellCommand(
        name="Get-EXOMailbox",
        parameters={"Identity": "user@example.com"},
    )
    runner = MockExchangePowerShellCommandRunner()

    result = runner.run(command)

    assert result == ExchangePowerShellCommandResult(
        command="Get-EXOMailbox",
        ok=False,
        error="No mock result configured for command: Get-EXOMailbox",
    )
    assert runner.commands == [command]


def test_exchange_command_result_can_hold_list_data():
    result = ExchangePowerShellCommandResult(
        command="Get-EXOMailboxStatistics",
        ok=True,
        data=[
            {
                "DisplayName": "Example User",
                "ItemCount": 123,
            }
        ],
    )

    assert result.command == "Get-EXOMailboxStatistics"
    assert result.ok is True
    assert result.data == [
        {
            "DisplayName": "Example User",
            "ItemCount": 123,
        }
    ]
    assert result.error is None