from inspectors.exchange_mailbox import (
    ExchangeMailboxInspectionError,
    ExchangeMailboxNotFoundError,
    ExchangeMailboxSnapshot,
    MockExchangeMailboxInspectorClient,
    inspect_exchange_mailbox,
)
from inspectors.models import InspectorRequest, InspectorStatus, InspectorTarget


def make_request(
    *,
    mailbox_address: str | None = "user@example.com",
    target_id: str = "user@example.com",
) -> InspectorRequest:
    inputs = {}

    if mailbox_address is not None:
        inputs["mailbox_address"] = mailbox_address

    return InspectorRequest(
        inspector="exchange.mailbox.inspect",
        request_id="55948",
        target=InspectorTarget(
            type="mailbox",
            id=target_id,
            metadata={"source": "test"},
        ),
        inputs=inputs,
    )


def test_inspect_exchange_mailbox_returns_read_only_facts():
    client = MockExchangeMailboxInspectorClient(
        {
            "user@example.com": ExchangeMailboxSnapshot(
                mailbox_address="user@example.com",
                display_name="Example User",
                primary_smtp_address="user@example.com",
                recipient_type="UserMailbox",
                mailbox_size="12 GB",
                item_count=12345,
                archive_status="disabled",
                auto_expanding_archive_status="not_applicable",
                retention_policy="Default MRM Policy",
                quota_warning_status="primary_mailbox_near_quota",
            )
        }
    )

    result = inspect_exchange_mailbox(make_request(), client)

    assert result.status == InspectorStatus.OK
    assert result.ok is True
    assert result.summary == "Mailbox metadata inspected for user@example.com."

    facts = {fact.key: fact.value for fact in result.facts}

    assert facts["mailbox_exists"] is True
    assert facts["display_name"] == "Example User"
    assert facts["primary_smtp_address"] == "user@example.com"
    assert facts["recipient_type"] == "UserMailbox"
    assert facts["mailbox_size"] == "12 GB"
    assert facts["item_count"] == 12345
    assert facts["archive_status"] == "disabled"
    assert facts["auto_expanding_archive_status"] == "not_applicable"
    assert facts["retention_policy"] == "Default MRM Policy"
    assert facts["quota_warning_status"] == "primary_mailbox_near_quota"

    assert "Mailbox content not inspected" in result.limitations
    assert "No permission changes performed" in result.limitations
    assert "No archive or retention changes performed" in result.limitations


def test_inspect_exchange_mailbox_recommends_archive_enable_when_archive_disabled():
    client = MockExchangeMailboxInspectorClient(
        {
            "user@example.com": ExchangeMailboxSnapshot(
                mailbox_address="user@example.com",
                recipient_type="UserMailbox",
                archive_status="disabled",
            )
        }
    )

    result = inspect_exchange_mailbox(make_request(), client)

    assert result.recommendations == [
        "exchange.archive.enable may be relevant if archive is required."
    ]


def test_inspect_exchange_mailbox_recommends_auto_expanding_for_archive_quota_issue():
    client = MockExchangeMailboxInspectorClient(
        {
            "user@example.com": ExchangeMailboxSnapshot(
                mailbox_address="user@example.com",
                recipient_type="UserMailbox",
                archive_status="enabled",
                auto_expanding_archive_status="disabled",
                quota_warning_status="archive_quota_full",
            )
        }
    )

    result = inspect_exchange_mailbox(make_request(), client)

    assert (
        "exchange.archive.enable_auto_expanding may be relevant if archive capacity "
        "is the issue."
    ) in result.recommendations
    assert (
        "Confirm whether auto-expanding archive is needed before any archive expansion."
        in result.recommendations
    )


def test_inspect_exchange_mailbox_uses_target_id_when_input_missing():
    client = MockExchangeMailboxInspectorClient(
        {
            "target@example.com": ExchangeMailboxSnapshot(
                mailbox_address="target@example.com",
                archive_status="enabled",
            )
        }
    )

    result = inspect_exchange_mailbox(
        make_request(
            mailbox_address=None,
            target_id="target@example.com",
        ),
        client,
    )

    assert result.status == InspectorStatus.OK
    assert result.target.id == "target@example.com"


def test_inspect_exchange_mailbox_returns_error_when_mailbox_missing():
    client = MockExchangeMailboxInspectorClient({})

    result = inspect_exchange_mailbox(make_request(), client)

    assert result.status == InspectorStatus.ERROR
    assert result.error is True
    assert result.summary == "Mailbox not found: user@example.com"

    facts = {fact.key: fact.value for fact in result.facts}

    assert facts["mailbox_exists"] is False
    assert result.errors[0].code == "mailbox_not_found"
    assert result.errors[0].recoverable is True
    assert "Mailbox content not inspected" in result.limitations


def test_inspect_exchange_mailbox_returns_error_when_target_is_empty():
    client = MockExchangeMailboxInspectorClient({})

    result = inspect_exchange_mailbox(
        make_request(
            mailbox_address=None,
            target_id="",
        ),
        client,
    )

    assert result.status == InspectorStatus.ERROR
    assert result.errors[0].code == "missing_mailbox_address"
    assert result.errors[0].recoverable is True


def test_inspect_exchange_mailbox_returns_structured_client_error():
    class FailingClient:
        def get_mailbox_snapshot(self, mailbox_address: str) -> ExchangeMailboxSnapshot:
            raise ExchangeMailboxInspectionError("Exchange metadata lookup failed.")

    result = inspect_exchange_mailbox(make_request(), FailingClient())

    assert result.status == InspectorStatus.ERROR
    assert result.summary == "Exchange metadata lookup failed."
    assert result.errors[0].code == "exchange_mailbox_inspection_failed"
    assert result.errors[0].message == "Exchange metadata lookup failed."
    assert result.errors[0].recoverable is True


def test_mock_client_raises_not_found_for_unknown_mailbox():
    client = MockExchangeMailboxInspectorClient({})

    try:
        client.get_mailbox_snapshot("missing@example.com")
    except ExchangeMailboxNotFoundError as exc:
        assert str(exc) == "Mailbox not found: missing@example.com"
    else:
        raise AssertionError("Expected ExchangeMailboxNotFoundError")