from inspectors.models import (
    InspectorEvidence,
    InspectorFact,
    InspectorResult,
    InspectorStatus,
    InspectorTarget,
)
from inspectors.storage import (
    build_inspector_output_dir,
    build_inspector_result_path,
    read_inspector_result_payload,
    save_inspector_result,
)


def test_build_inspector_output_dir(tmp_path):
    path = build_inspector_output_dir(
        workspace=str(tmp_path),
        request_id="55948",
    )

    assert path == (
        tmp_path
        / ".work_copilot"
        / "servicedesk"
        / "55948"
        / "inspectors"
    )


def test_build_inspector_result_path(tmp_path):
    path = build_inspector_result_path(
        workspace=str(tmp_path),
        request_id="55948",
        inspector_id="exchange.mailbox.inspect",
    )

    assert path == (
        tmp_path
        / ".work_copilot"
        / "servicedesk"
        / "55948"
        / "inspectors"
        / "exchange.mailbox.inspect.json"
    )


def test_build_inspector_result_path_sanitizes_slashes(tmp_path):
    path = build_inspector_result_path(
        workspace=str(tmp_path),
        request_id="55948",
        inspector_id="exchange/mailbox\\inspect",
    )

    assert path.name == "exchange_mailbox_inspect.json"


def test_save_inspector_result_writes_json(tmp_path):
    result = InspectorResult(
        inspector="exchange.mailbox.inspect",
        target=InspectorTarget(
            type="mailbox",
            id="user@example.com",
            metadata={"source": "test"},
        ),
        status=InspectorStatus.PARTIAL,
        summary="Mailbox partially inspected.",
        facts=[
            InspectorFact(
                key="archive_enabled",
                value=False,
                source="mock",
            )
        ],
        evidence=[
            InspectorEvidence(
                label="mailbox_type",
                value="UserMailbox",
            )
        ],
        limitations=["Mailbox content not inspected"],
        recommendations=["exchange.archive.enable may be relevant"],
    )

    path = save_inspector_result(
        workspace=str(tmp_path),
        request_id="55948",
        result=result,
    )

    assert path.exists()
    assert path.name == "exchange.mailbox.inspect.json"

    payload = read_inspector_result_payload(path)

    assert payload["inspector"] == "exchange.mailbox.inspect"
    assert payload["target"] == {
        "type": "mailbox",
        "id": "user@example.com",
        "metadata": {"source": "test"},
    }
    assert payload["status"] == "partial"
    assert payload["summary"] == "Mailbox partially inspected."
    assert payload["facts"] == [
        {
            "key": "archive_enabled",
            "value": False,
            "source": "mock",
        }
    ]
    assert payload["evidence"] == [
        {
            "label": "mailbox_type",
            "value": "UserMailbox",
        }
    ]
    assert payload["limitations"] == ["Mailbox content not inspected"]
    assert payload["recommendations"] == [
        "exchange.archive.enable may be relevant",
    ]
    assert payload["partial"] is True
    assert payload["errors"] == []


def test_save_inspector_result_preserves_unicode(tmp_path):
    result = InspectorResult(
        inspector="active_directory.user.lookup",
        target=InspectorTarget(
            type="user",
            id="melek.bas@example.com",
        ),
        status=InspectorStatus.OK,
        summary="Użytkownik sprawdzony: Baş",
        facts=[
            InspectorFact(
                key="display_name",
                value="Melek Baş",
                source="mock",
            )
        ],
    )

    path = save_inspector_result(
        workspace=str(tmp_path),
        request_id="55948",
        result=result,
    )

    raw = path.read_text(encoding="utf-8")

    assert "Użytkownik sprawdzony: Baş" in raw
    assert "Melek Baş" in raw