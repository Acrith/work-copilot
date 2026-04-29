from dataclasses import dataclass
from typing import Any

from inspectors.exchange_command_runner import (
    ExchangePowerShellCommand,
    ExchangePowerShellCommandResult,
    ExchangePowerShellCommandRunner,
)
from inspectors.exchange_mailbox import (
    ExchangeMailboxInspectionError,
    ExchangeMailboxInspectorClient,
    ExchangeMailboxNotFoundError,
    ExchangeMailboxSnapshot,
)


@dataclass(frozen=True)
class ExchangeOnlinePowerShellConfig:
    enabled: bool = False


class ExchangeOnlinePowerShellMailboxClient(ExchangeMailboxInspectorClient):
    """Exchange Online PowerShell adapter for mailbox metadata inspection.

    This client is still disabled by default. It only works when explicitly enabled
    and provided with a command runner. Tests use a mock command runner; no real
    PowerShell execution happens here.
    """

    def __init__(
        self,
        config: ExchangeOnlinePowerShellConfig | None = None,
        runner: ExchangePowerShellCommandRunner | None = None,
    ) -> None:
        self.config = config or ExchangeOnlinePowerShellConfig()
        self.runner = runner

    def get_mailbox_snapshot(self, mailbox_address: str) -> ExchangeMailboxSnapshot:
        if not self.config.enabled:
            raise ExchangeMailboxInspectionError(
                "Exchange Online PowerShell mailbox inspector is not implemented yet."
            )

        if self.runner is None:
            raise ExchangeMailboxInspectionError(
                "Exchange Online PowerShell mailbox inspector requires a command runner."
            )

        mailbox_result = self.runner.run(
            ExchangePowerShellCommand(
                name="Get-EXOMailbox",
                parameters={
                    "Identity": mailbox_address,
                },
            )
        )
        mailbox_data = _required_mailbox_row(
            mailbox_result,
            mailbox_address=mailbox_address,
        )

        statistics_result = self.runner.run(
            ExchangePowerShellCommand(
                name="Get-EXOMailboxStatistics",
                parameters={
                    "Identity": mailbox_address,
                },
            )
        )
        statistics_data = _required_command_row(
            statistics_result,
            command_name="Get-EXOMailboxStatistics",
        )

        primary_smtp_address = _optional_str(
            mailbox_data.get("PrimarySmtpAddress")
            or mailbox_data.get("PrimarySMTPAddress")
            or mailbox_data.get("WindowsEmailAddress")
        )

        return ExchangeMailboxSnapshot(
            mailbox_address=mailbox_address,
            display_name=_optional_str(mailbox_data.get("DisplayName")),
            primary_smtp_address=primary_smtp_address,
            recipient_type=_optional_str(
                mailbox_data.get("RecipientTypeDetails")
                or mailbox_data.get("RecipientType")
            ),
            mailbox_size=_optional_str(
                statistics_data.get("TotalItemSize")
                or statistics_data.get("MailboxSize")
            ),
            item_count=_optional_int(statistics_data.get("ItemCount")),
            archive_status=_normalize_archive_status(mailbox_data.get("ArchiveStatus")),
            auto_expanding_archive_status=_normalize_auto_expanding_archive_status(
                mailbox_data.get("AutoExpandingArchiveEnabled")
            ),
            retention_policy=_optional_str(mailbox_data.get("RetentionPolicy")),
            quota_warning_status=_optional_str(
                statistics_data.get("StorageLimitStatus")
                or statistics_data.get("QuotaWarningStatus")
            ),
        )


def _required_mailbox_row(
    result: ExchangePowerShellCommandResult,
    *,
    mailbox_address: str,
) -> dict[str, object]:
    if not result.ok:
        error = result.error or "Mailbox lookup failed."

        if _looks_like_not_found(error):
            raise ExchangeMailboxNotFoundError(f"Mailbox not found: {mailbox_address}")

        raise ExchangeMailboxInspectionError(f"{result.command} failed: {error}")

    row = _first_result_row(result.data)

    if row is None:
        raise ExchangeMailboxNotFoundError(f"Mailbox not found: {mailbox_address}")

    return row


def _required_command_row(
    result: ExchangePowerShellCommandResult,
    *,
    command_name: str,
) -> dict[str, object]:
    if not result.ok:
        error = result.error or "Command failed."
        raise ExchangeMailboxInspectionError(f"{result.command} failed: {error}")

    row = _first_result_row(result.data)

    if row is None:
        raise ExchangeMailboxInspectionError(f"{command_name} returned no data.")

    return row


def _first_result_row(data: Any) -> dict[str, object] | None:
    if data is None:
        return None

    if isinstance(data, dict):
        return data

    if isinstance(data, list):
        if not data:
            return None

        first_item = data[0]

        if not isinstance(first_item, dict):
            raise ExchangeMailboxInspectionError(
                "Exchange command returned unsupported list data."
            )

        return first_item

    raise ExchangeMailboxInspectionError(
        "Exchange command returned unsupported data shape."
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    return text or None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None

    if isinstance(value, int):
        return value

    text = str(value).strip()

    if not text.isdigit():
        return None

    return int(text)


def _normalize_archive_status(value: object) -> str | None:
    text = _optional_str(value)

    if text is None:
        return None

    normalized = text.lower()

    if normalized in {"none", "disabled", "not_enabled", "not enabled"}:
        return "disabled"

    if normalized in {"active", "enabled"}:
        return "enabled"

    return text


def _normalize_auto_expanding_archive_status(value: object) -> str | None:
    if isinstance(value, bool):
        return "enabled" if value else "disabled"

    text = _optional_str(value)

    if text is None:
        return None

    normalized = text.lower()

    if normalized in {"true", "enabled", "active"}:
        return "enabled"

    if normalized in {"false", "disabled", "not_enabled", "not enabled"}:
        return "disabled"

    return text


def _looks_like_not_found(error: str) -> bool:
    normalized = error.lower()

    return "not found" in normalized or "couldn't be found" in normalized