import pytest

from inspectors.exchange_command_runner import (
    ExchangePowerShellCommandResult,
    MockExchangePowerShellCommandRunner,
)
from inspectors.exchange_mailbox import (
    ExchangeMailboxInspectionError,
    ExchangeMailboxNotFoundError,
)
from inspectors.exchange_online_powershell import (
    ExchangeOnlinePowerShellConfig,
    ExchangeOnlinePowerShellMailboxClient,
)


def test_exchange_online_powershell_config_defaults_to_disabled():
    config = ExchangeOnlinePowerShellConfig()

    assert config.enabled is False


def test_exchange_online_powershell_client_is_disabled_placeholder():
    client = ExchangeOnlinePowerShellMailboxClient()

    with pytest.raises(
        ExchangeMailboxInspectionError,
        match="not implemented yet",
    ):
        client.get_mailbox_snapshot("user@example.com")


def test_exchange_online_powershell_client_accepts_config():
    config = ExchangeOnlinePowerShellConfig(enabled=True)
    client = ExchangeOnlinePowerShellMailboxClient(config)

    assert client.config is config


def test_exchange_online_powershell_client_requires_runner_when_enabled():
    client = ExchangeOnlinePowerShellMailboxClient(
        ExchangeOnlinePowerShellConfig(enabled=True)
    )

    with pytest.raises(
        ExchangeMailboxInspectionError,
        match="requires a command runner",
    ):
        client.get_mailbox_snapshot("user@example.com")


def test_exchange_online_powershell_client_builds_snapshot_from_mock_results():
    runner = MockExchangePowerShellCommandRunner(
        results={
            "Get-EXOMailbox": ExchangePowerShellCommandResult(
                command="Get-EXOMailbox",
                ok=True,
                data={
                    "DisplayName": "Example User",
                    "PrimarySmtpAddress": "user@example.com",
                    "RecipientTypeDetails": "UserMailbox",
                    "ArchiveStatus": "None",
                    "AutoExpandingArchiveEnabled": False,
                    "RetentionPolicy": "Default MRM Policy",
                },
            ),
            "Get-EXOMailboxStatistics": ExchangePowerShellCommandResult(
                command="Get-EXOMailboxStatistics",
                ok=True,
                data={
                    "TotalItemSize": "12 GB",
                    "ItemCount": 12345,
                    "StorageLimitStatus": "BelowLimit",
                },
            ),
        }
    )
    client = ExchangeOnlinePowerShellMailboxClient(
        ExchangeOnlinePowerShellConfig(enabled=True),
        runner=runner,
    )

    snapshot = client.get_mailbox_snapshot("user@example.com")

    assert snapshot.mailbox_address == "user@example.com"
    assert snapshot.display_name == "Example User"
    assert snapshot.primary_smtp_address == "user@example.com"
    assert snapshot.recipient_type == "UserMailbox"
    assert snapshot.mailbox_size == "12 GB"
    assert snapshot.item_count == 12345
    assert snapshot.archive_status == "disabled"
    assert snapshot.auto_expanding_archive_status == "disabled"
    assert snapshot.retention_policy == "Default MRM Policy"
    assert snapshot.quota_warning_status == "BelowLimit"

    assert [command.name for command in runner.commands] == [
        "Get-EXOMailbox",
        "Get-EXOMailboxStatistics",
    ]
    assert runner.commands[0].parameters == {"Identity": "user@example.com"}
    assert runner.commands[1].parameters == {"Identity": "user@example.com"}


def test_exchange_online_powershell_client_accepts_list_shaped_command_data():
    runner = MockExchangePowerShellCommandRunner(
        results={
            "Get-EXOMailbox": ExchangePowerShellCommandResult(
                command="Get-EXOMailbox",
                ok=True,
                data=[
                    {
                        "DisplayName": "Example User",
                        "PrimarySmtpAddress": "user@example.com",
                        "RecipientTypeDetails": "UserMailbox",
                        "ArchiveStatus": "Active",
                        "AutoExpandingArchiveEnabled": True,
                    }
                ],
            ),
            "Get-EXOMailboxStatistics": ExchangePowerShellCommandResult(
                command="Get-EXOMailboxStatistics",
                ok=True,
                data=[
                    {
                        "TotalItemSize": "98 GB",
                        "ItemCount": "9001",
                        "StorageLimitStatus": "ArchiveQuotaFull",
                    }
                ],
            ),
        }
    )
    client = ExchangeOnlinePowerShellMailboxClient(
        ExchangeOnlinePowerShellConfig(enabled=True),
        runner=runner,
    )

    snapshot = client.get_mailbox_snapshot("user@example.com")

    assert snapshot.archive_status == "enabled"
    assert snapshot.auto_expanding_archive_status == "enabled"
    assert snapshot.item_count == 9001
    assert snapshot.quota_warning_status == "ArchiveQuotaFull"


def test_exchange_online_powershell_client_raises_not_found_for_empty_mailbox_result():
    runner = MockExchangePowerShellCommandRunner(
        results={
            "Get-EXOMailbox": ExchangePowerShellCommandResult(
                command="Get-EXOMailbox",
                ok=True,
                data=[],
            ),
        }
    )
    client = ExchangeOnlinePowerShellMailboxClient(
        ExchangeOnlinePowerShellConfig(enabled=True),
        runner=runner,
    )

    with pytest.raises(
        ExchangeMailboxNotFoundError,
        match="Mailbox not found: user@example.com",
    ):
        client.get_mailbox_snapshot("user@example.com")


def test_exchange_online_powershell_client_maps_not_found_error():
    runner = MockExchangePowerShellCommandRunner(
        results={
            "Get-EXOMailbox": ExchangePowerShellCommandResult(
                command="Get-EXOMailbox",
                ok=False,
                error="The operation couldn't be performed because object was not found.",
            ),
        }
    )
    client = ExchangeOnlinePowerShellMailboxClient(
        ExchangeOnlinePowerShellConfig(enabled=True),
        runner=runner,
    )

    with pytest.raises(
        ExchangeMailboxNotFoundError,
        match="Mailbox not found: user@example.com",
    ):
        client.get_mailbox_snapshot("user@example.com")


def test_exchange_online_powershell_client_raises_inspection_error_for_mailbox_failure():
    runner = MockExchangePowerShellCommandRunner(
        results={
            "Get-EXOMailbox": ExchangePowerShellCommandResult(
                command="Get-EXOMailbox",
                ok=False,
                error="Authentication failed.",
            ),
        }
    )
    client = ExchangeOnlinePowerShellMailboxClient(
        ExchangeOnlinePowerShellConfig(enabled=True),
        runner=runner,
    )

    with pytest.raises(
        ExchangeMailboxInspectionError,
        match="Get-EXOMailbox failed: Authentication failed.",
    ):
        client.get_mailbox_snapshot("user@example.com")


def test_exchange_online_powershell_client_raises_inspection_error_for_statistics_failure():
    runner = MockExchangePowerShellCommandRunner(
        results={
            "Get-EXOMailbox": ExchangePowerShellCommandResult(
                command="Get-EXOMailbox",
                ok=True,
                data={
                    "DisplayName": "Example User",
                    "PrimarySmtpAddress": "user@example.com",
                },
            ),
            "Get-EXOMailboxStatistics": ExchangePowerShellCommandResult(
                command="Get-EXOMailboxStatistics",
                ok=False,
                error="Statistics lookup failed.",
            ),
        }
    )
    client = ExchangeOnlinePowerShellMailboxClient(
        ExchangeOnlinePowerShellConfig(enabled=True),
        runner=runner,
    )

    with pytest.raises(
        ExchangeMailboxInspectionError,
        match="Get-EXOMailboxStatistics failed: Statistics lookup failed.",
    ):
        client.get_mailbox_snapshot("user@example.com")


def test_exchange_online_powershell_client_rejects_unsupported_data_shape():
    runner = MockExchangePowerShellCommandRunner(
        results={
            "Get-EXOMailbox": ExchangePowerShellCommandResult(
                command="Get-EXOMailbox",
                ok=True,
                data="not a dict or list",  # type: ignore[arg-type]
            ),
        }
    )
    client = ExchangeOnlinePowerShellMailboxClient(
        ExchangeOnlinePowerShellConfig(enabled=True),
        runner=runner,
    )

    with pytest.raises(
        ExchangeMailboxInspectionError,
        match="unsupported data shape",
    ):
        client.get_mailbox_snapshot("user@example.com")