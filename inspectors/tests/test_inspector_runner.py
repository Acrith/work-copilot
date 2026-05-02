import pytest

from inspectors.mock import (
    create_mock_inspector_registry,
    inspect_mock_active_directory_group,
    inspect_mock_active_directory_group_membership,
    inspect_mock_active_directory_user,
    inspect_mock_exchange_mailbox,
)
from inspectors.models import (
    InspectorRequest,
    InspectorResult,
    InspectorStatus,
    InspectorTarget,
)
from inspectors.registry import InspectorRegistry
from inspectors.runner import run_inspector_and_save
from inspectors.storage import read_inspector_result_payload


def make_mailbox_request(
    *,
    inspector: str = "exchange.mailbox.inspect",
    request_id: str | None = "55948",
) -> InspectorRequest:
    return InspectorRequest(
        inspector=inspector,
        request_id=request_id,
        target=InspectorTarget(
            type="mailbox",
            id="user@example.com",
            metadata={"source": "test"},
        ),
        inputs={"mailbox_address": "user@example.com"},
    )


def test_mock_exchange_mailbox_inspector_returns_read_only_result():
    request = make_mailbox_request()

    result = inspect_mock_exchange_mailbox(request)

    assert result.inspector == "exchange.mailbox.inspect"
    assert result.target is request.target
    assert result.status == InspectorStatus.OK
    assert result.ok is True
    assert result.summary == "Mailbox metadata inspected for user@example.com."

    facts = {fact.key: fact.value for fact in result.facts}

    assert facts["mailbox_exists"] is True
    assert facts["recipient_type"] == "UserMailbox"
    assert facts["archive_status"] == "disabled"
    assert facts["auto_expanding_archive_status"] == "not_applicable"

    assert "Mailbox content not inspected" in result.limitations
    assert "Attachments not inspected" in result.limitations
    assert "No permission changes performed" in result.limitations
    assert "No archive or retention changes performed" in result.limitations
    assert "No ServiceDesk writes performed" in result.limitations


def test_create_mock_inspector_registry_registers_mailbox_inspector():
    registry = create_mock_inspector_registry()

    handler = registry.get("exchange.mailbox.inspect")

    assert handler is inspect_mock_exchange_mailbox


def test_create_mock_inspector_registry_registers_active_directory_inspectors():
    registry = create_mock_inspector_registry()

    assert registry.get("active_directory.user.inspect") is (
        inspect_mock_active_directory_user
    )
    assert registry.get("active_directory.group.inspect") is (
        inspect_mock_active_directory_group
    )
    assert registry.get("active_directory.group_membership.inspect") is (
        inspect_mock_active_directory_group_membership
    )


def test_run_inspector_and_save_writes_registered_result(tmp_path):
    registry = create_mock_inspector_registry()
    request = make_mailbox_request()

    output = run_inspector_and_save(
        registry=registry,
        request=request,
        workspace=str(tmp_path),
    )

    assert output.result.status == InspectorStatus.OK
    assert output.saved_path == (
        tmp_path
        / ".work_copilot"
        / "servicedesk"
        / "55948"
        / "inspectors"
        / "exchange.mailbox.inspect.json"
    )
    assert output.saved_path.exists()

    payload = read_inspector_result_payload(output.saved_path)

    assert payload["inspector"] == "exchange.mailbox.inspect"
    assert payload["target"] == {
        "type": "mailbox",
        "id": "user@example.com",
        "metadata": {"source": "test"},
    }
    assert payload["status"] == "ok"
    assert payload["summary"] == "Mailbox metadata inspected for user@example.com."
    assert payload["facts"]
    assert payload["limitations"]

    facts = {fact["key"]: fact["value"] for fact in payload["facts"]}

    assert facts["mailbox_exists"] is True
    assert facts["archive_status"] == "disabled"
    assert facts["recipient_type"] == "UserMailbox"


def test_run_inspector_and_save_writes_unknown_inspector_error(tmp_path):
    registry = InspectorRegistry()
    request = make_mailbox_request(inspector="exchange.unknown.inspect")

    output = run_inspector_and_save(
        registry=registry,
        request=request,
        workspace=str(tmp_path),
    )

    assert output.result.status == InspectorStatus.ERROR
    assert output.saved_path.name == "exchange.unknown.inspect.json"

    payload = read_inspector_result_payload(output.saved_path)

    assert payload["inspector"] == "exchange.unknown.inspect"
    assert payload["status"] == "error"
    assert payload["errors"] == [
        {
            "code": "inspector_not_found",
            "message": "No inspector registered for exchange.unknown.inspect",
            "recoverable": True,
        }
    ]


def test_run_inspector_and_save_requires_request_id(tmp_path):
    registry = create_mock_inspector_registry()
    request = make_mailbox_request(request_id=None)

    with pytest.raises(ValueError, match="request_id is required"):
        run_inspector_and_save(
            registry=registry,
            request=request,
            workspace=str(tmp_path),
        )


def test_run_inspector_and_save_calls_handler_after_request_id_validation(tmp_path):
    registry = InspectorRegistry()
    called = False

    def handler(request: InspectorRequest) -> InspectorResult:
        nonlocal called
        called = True

        return InspectorResult(
            inspector=request.inspector,
            target=request.target,
            status=InspectorStatus.OK,
            summary="Handled.",
        )

    registry.register("exchange.mailbox.inspect", handler)
    request = make_mailbox_request(request_id="")

    with pytest.raises(ValueError, match="request_id is required"):
        run_inspector_and_save(
            registry=registry,
            request=request,
            workspace=str(tmp_path),
        )

    assert called is False


def test_mock_exchange_mailbox_inspector_uses_real_inspection_shape():
    request = make_mailbox_request()

    result = inspect_mock_exchange_mailbox(request)
    payload = result.to_dict()

    assert payload["summary"] == "Mailbox metadata inspected for user@example.com."
    assert {
        "key": "archive_status",
        "value": "disabled",
        "source": "read_only_exchange_metadata",
    } in payload["facts"]
    assert {
        "label": "primary_smtp_address",
        "value": "user@example.com",
    } in payload["evidence"]


def test_run_all_supported_inspectors_from_no_match_skill_plan(tmp_path):
    """End-to-end-ish: a no-match AD inspection plan with target_user and
    target_group, against the mock registry, runs all three AD inspectors
    and writes one JSON file per inspector. No real AD calls."""
    from inspectors.skill_plan import (
        build_inspector_request_from_skill_plan,
        select_inspectors_for_skill_plan,
    )

    skill_plan = """
## Metadata

- Skill match: none
- Skill relevance: no_match

## Extracted inputs

- field: target_user
  status: present
  value: name.surname@example.com
  evidence: saved context
  needed_now: yes

- field: target_group
  status: present
  value: usr.podpis.test
  evidence: saved context
  needed_now: yes

## Automation handoff

- Ready for inspection: yes
- Suggested inspector tools: active_directory.user.inspect, active_directory.group.inspect, active_directory.group_membership.inspect
"""

    registry = create_mock_inspector_registry()
    selections = select_inspectors_for_skill_plan(skill_plan)

    saved_paths: list = []

    for selection in selections:
        request = build_inspector_request_from_skill_plan(
            request_id="55948",
            skill_plan_text=skill_plan,
            inspector_id=selection.inspector_id,
        )
        output = run_inspector_and_save(
            registry=registry,
            request=request,
            workspace=str(tmp_path),
        )
        saved_paths.append(output.saved_path)

        assert output.result.status == InspectorStatus.OK
        assert output.result.inspector == selection.inspector_id

    assert {path.name for path in saved_paths} == {
        "active_directory.user.inspect.json",
        "active_directory.group.inspect.json",
        "active_directory.group_membership.inspect.json",
    }

    for path in saved_paths:
        assert path.exists()
        payload = read_inspector_result_payload(path)
        assert payload["status"] == "ok"
