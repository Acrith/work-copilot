from dataclasses import dataclass

from inspectors.exchange_mailbox import (
    ExchangeMailboxInspectionError,
    ExchangeMailboxInspectorClient,
    ExchangeMailboxSnapshot,
)


@dataclass(frozen=True)
class ExchangeOnlinePowerShellConfig:
    enabled: bool = False


class ExchangeOnlinePowerShellMailboxClient(ExchangeMailboxInspectorClient):
    """Disabled placeholder for a future real Exchange Online PowerShell client."""

    def __init__(self, config: ExchangeOnlinePowerShellConfig | None = None) -> None:
        self.config = config or ExchangeOnlinePowerShellConfig()

    def get_mailbox_snapshot(self, mailbox_address: str) -> ExchangeMailboxSnapshot:
        raise ExchangeMailboxInspectionError(
            "Exchange Online PowerShell mailbox inspector is not implemented yet."
        )