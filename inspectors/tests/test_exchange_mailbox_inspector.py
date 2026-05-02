from inspectors.exchange_mailbox import (
    ExchangeMailboxFolderStat,
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


def test_inspect_exchange_mailbox_emits_largest_folders_fact_and_evidence():
    snapshot = ExchangeMailboxSnapshot(
        mailbox_address="user@example.com",
        recipient_type="UserMailbox",
        mailbox_size="12 GB",
        archive_status="enabled",
        largest_folders=[
            ExchangeMailboxFolderStat(
                name="Inbox",
                folder_path="/Inbox",
                folder_size="8 GB",
                items_in_folder=4321,
            ),
            ExchangeMailboxFolderStat(
                name="Sent Items",
                folder_path="/Sent Items",
                folder_size="2 GB",
                items_in_folder=1234,
            ),
        ],
    )
    client = MockExchangeMailboxInspectorClient({"user@example.com": snapshot})

    result = inspect_exchange_mailbox(make_request(), client)

    facts = {fact.key: fact.value for fact in result.facts}

    assert "largest_folders" in facts
    assert facts["largest_folders"] == [
        {
            "name": "Inbox",
            "folder_path": "/Inbox",
            "folder_size": "8 GB",
            "items_in_folder": 4321,
        },
        {
            "name": "Sent Items",
            "folder_path": "/Sent Items",
            "folder_size": "2 GB",
            "items_in_folder": 1234,
        },
    ]

    folder_evidence = [
        item for item in result.evidence if item.label == "largest_folder"
    ]

    assert len(folder_evidence) == 2
    assert folder_evidence[0].value == "/Inbox: 8 GB — 4321 items"
    assert folder_evidence[1].value == "/Sent Items: 2 GB — 1234 items"


def test_inspect_exchange_mailbox_omits_largest_folders_fact_when_absent():
    snapshot = ExchangeMailboxSnapshot(
        mailbox_address="user@example.com",
        recipient_type="UserMailbox",
        archive_status="enabled",
    )
    client = MockExchangeMailboxInspectorClient({"user@example.com": snapshot})

    result = inspect_exchange_mailbox(make_request(), client)

    fact_keys = {fact.key for fact in result.facts}

    assert "largest_folders" not in fact_keys

    evidence_labels = {item.label for item in result.evidence}

    assert "largest_folder" not in evidence_labels


def test_recommends_archive_review_when_disabled_and_primary_mailbox_full():
    client = MockExchangeMailboxInspectorClient(
        {
            "user@example.com": ExchangeMailboxSnapshot(
                mailbox_address="user@example.com",
                recipient_type="UserMailbox",
                archive_status="disabled",
                quota_warning_status="primary_mailbox_near_quota",
            )
        }
    )

    result = inspect_exchange_mailbox(make_request(), client)

    assert result.recommendations == [
        "Mailbox appears full and archive is disabled. Review whether enabling "
        "archive (exchange.archive.enable) is appropriate. No change has been made."
    ]


def test_recommends_retention_review_when_archive_enabled_and_primary_full():
    client = MockExchangeMailboxInspectorClient(
        {
            "user@example.com": ExchangeMailboxSnapshot(
                mailbox_address="user@example.com",
                recipient_type="UserMailbox",
                archive_status="enabled",
                auto_expanding_archive_status="enabled",
                quota_warning_status="primary_mailbox_near_quota",
            )
        }
    )

    result = inspect_exchange_mailbox(make_request(), client)

    assert any(
        "Primary mailbox appears full while archive is enabled" in rec
        and "retention policy" in rec
        and "No change has been made" in rec
        for rec in result.recommendations
    )


def test_recommends_auto_expanding_review_when_archive_full_and_auto_expanding_disabled():
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

    assert any(
        "auto-expanding archive is disabled" in rec
        and "exchange.archive.enable_auto_expanding" in rec
        and "No change has been made" in rec
        for rec in result.recommendations
    )


def test_recommends_retention_review_when_archive_enabled_and_archive_full_with_auto_expanding_enabled():
    client = MockExchangeMailboxInspectorClient(
        {
            "user@example.com": ExchangeMailboxSnapshot(
                mailbox_address="user@example.com",
                recipient_type="UserMailbox",
                archive_status="enabled",
                auto_expanding_archive_status="enabled",
                quota_warning_status="archive_quota_full",
            )
        }
    )

    result = inspect_exchange_mailbox(make_request(), client)

    assert any(
        "Archive is enabled and appears full" in rec
        and "retention policy" in rec
        for rec in result.recommendations
    )


def test_returns_no_recommendation_fallback_when_evidence_is_insufficient():
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
        "No archive-readiness recommendation was generated. Existing facts "
        "do not indicate a mailbox-full or archive-capacity problem. "
        "No change has been made."
    ]


def test_recommends_manual_review_when_full_but_archive_status_unknown():
    client = MockExchangeMailboxInspectorClient(
        {
            "user@example.com": ExchangeMailboxSnapshot(
                mailbox_address="user@example.com",
                recipient_type="UserMailbox",
                quota_warning_status="primary_mailbox_near_quota",
            )
        }
    )

    result = inspect_exchange_mailbox(make_request(), client)

    assert any(
        "archive status is unknown" in rec
        and "Manual review" in rec
        and "No change has been made" in rec
        for rec in result.recommendations
    )


def test_recommendations_never_claim_archive_was_enabled_or_changed():
    snapshots = [
        ExchangeMailboxSnapshot(
            mailbox_address="user@example.com",
            archive_status="disabled",
            quota_warning_status="primary_mailbox_near_quota",
        ),
        ExchangeMailboxSnapshot(
            mailbox_address="user@example.com",
            archive_status="enabled",
            auto_expanding_archive_status="disabled",
            quota_warning_status="archive_quota_full",
        ),
        ExchangeMailboxSnapshot(
            mailbox_address="user@example.com",
            archive_status="enabled",
            auto_expanding_archive_status="enabled",
            quota_warning_status="primary_mailbox_near_quota",
        ),
    ]

    forbidden = [
        "archive enabled",
        "archive has been enabled",
        "archive was enabled",
        "auto-expanding archive enabled",
        "auto-expanding archive has been enabled",
        "we enabled",
        "we have enabled",
    ]

    for snapshot in snapshots:
        client = MockExchangeMailboxInspectorClient({snapshot.mailbox_address: snapshot})
        result = inspect_exchange_mailbox(make_request(), client)

        for rec in result.recommendations:
            lowered = rec.lower()
            assert "no change has been made" in lowered
            for phrase in forbidden:
                assert phrase not in lowered, (
                    f"Recommendation falsely implies a change: {rec!r}"
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