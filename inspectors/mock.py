from inspectors.exchange_mailbox import (
    ExchangeMailboxSnapshot,
    MockExchangeMailboxInspectorClient,
    inspect_exchange_mailbox,
)
from inspectors.models import InspectorRequest, InspectorResult
from inspectors.registry import InspectorRegistry


def inspect_mock_exchange_mailbox(request: InspectorRequest) -> InspectorResult:
    mailbox_address = str(request.inputs.get("mailbox_address") or request.target.id)

    client = MockExchangeMailboxInspectorClient(
        {
            mailbox_address: ExchangeMailboxSnapshot(
                mailbox_address=mailbox_address,
                display_name="Mock Mailbox User",
                primary_smtp_address=mailbox_address,
                recipient_type="UserMailbox",
                mailbox_size="mock_unknown",
                item_count=None,
                archive_status="disabled",
                auto_expanding_archive_status="not_applicable",
                retention_policy="mock_unknown",
                quota_warning_status="mock_unknown",
            )
        }
    )

    return inspect_exchange_mailbox(request, client)


def create_mock_inspector_registry() -> InspectorRegistry:
    registry = InspectorRegistry()
    registry.register("exchange.mailbox.inspect", inspect_mock_exchange_mailbox)
    return registry