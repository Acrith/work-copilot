from inspectors.models import (
    InspectorError,
    InspectorEvidence,
    InspectorFact,
    InspectorRequest,
    InspectorResult,
    InspectorStatus,
    InspectorTarget,
)


def test_inspector_request_stores_target_and_inputs():
    request = InspectorRequest(
        inspector="exchange.mailbox.inspect",
        request_id="55948",
        target=InspectorTarget(
            type="mailbox",
            id="user@example.com",
            metadata={"source": "skill_plan"},
        ),
        inputs={"mailbox_address": "user@example.com"},
    )

    assert request.inspector == "exchange.mailbox.inspect"
    assert request.request_id == "55948"
    assert request.target.type == "mailbox"
    assert request.target.id == "user@example.com"
    assert request.target.metadata == {"source": "skill_plan"}
    assert request.inputs == {"mailbox_address": "user@example.com"}


def test_inspector_result_status_helpers():
    ok_result = InspectorResult(
        inspector="exchange.mailbox.inspect",
        target=InspectorTarget(type="mailbox", id="user@example.com"),
        status=InspectorStatus.OK,
        summary="Mailbox inspected.",
    )

    partial_result = InspectorResult(
        inspector="exchange.mailbox.inspect",
        target=InspectorTarget(type="mailbox", id="user@example.com"),
        status=InspectorStatus.PARTIAL,
        summary="Some facts were collected.",
    )

    error_result = InspectorResult(
        inspector="exchange.mailbox.inspect",
        target=InspectorTarget(type="mailbox", id="user@example.com"),
        status=InspectorStatus.ERROR,
        summary="Mailbox inspection failed.",
    )

    assert ok_result.ok is True
    assert ok_result.partial is False
    assert ok_result.error is False

    assert partial_result.ok is False
    assert partial_result.partial is True
    assert partial_result.error is False

    assert error_result.ok is False
    assert error_result.partial is False
    assert error_result.error is True


def test_inspector_result_to_dict_matches_documented_schema():
    result = InspectorResult(
        inspector="exchange.mailbox.inspect",
        target=InspectorTarget(
            type="mailbox",
            id="user@example.com",
            metadata={"request_id": "55948"},
        ),
        status=InspectorStatus.PARTIAL,
        summary="Mailbox was partially inspected.",
        facts=[
            InspectorFact(
                key="archive_enabled",
                value=False,
                source="read_only_metadata",
            )
        ],
        evidence=[
            InspectorEvidence(
                label="mailbox_type",
                value="UserMailbox",
            )
        ],
        limitations=[
            "Mailbox content not inspected",
            "No permission changes performed",
        ],
        recommendations=[
            "exchange.archive.enable may be relevant",
        ],
        errors=[
            InspectorError(
                code="quota_unavailable",
                message="Mailbox quota could not be read.",
                recoverable=True,
            )
        ],
    )

    assert result.to_dict() == {
        "inspector": "exchange.mailbox.inspect",
        "target": {
            "type": "mailbox",
            "id": "user@example.com",
            "metadata": {"request_id": "55948"},
        },
        "status": "partial",
        "summary": "Mailbox was partially inspected.",
        "facts": [
            {
                "key": "archive_enabled",
                "value": False,
                "source": "read_only_metadata",
            }
        ],
        "evidence": [
            {
                "label": "mailbox_type",
                "value": "UserMailbox",
            }
        ],
        "limitations": [
            "Mailbox content not inspected",
            "No permission changes performed",
        ],
        "recommendations": [
            "exchange.archive.enable may be relevant",
        ],
        "partial": True,
        "errors": [
            {
                "code": "quota_unavailable",
                "message": "Mailbox quota could not be read.",
                "recoverable": True,
            }
        ],
    }


def test_inspector_result_defaults_are_empty_collections():
    result = InspectorResult(
        inspector="exchange.mailbox.inspect",
        target=InspectorTarget(type="mailbox", id="user@example.com"),
        status=InspectorStatus.OK,
        summary="Mailbox inspected.",
    )

    assert result.facts == []
    assert result.evidence == []
    assert result.limitations == []
    assert result.recommendations == []
    assert result.errors == []

    payload = result.to_dict()

    assert payload["facts"] == []
    assert payload["evidence"] == []
    assert payload["limitations"] == []
    assert payload["recommendations"] == []
    assert payload["errors"] == []