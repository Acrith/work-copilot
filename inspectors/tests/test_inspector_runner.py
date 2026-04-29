import pytest

from inspectors.mock import create_mock_inspector_registry, inspect_mock_exchange_mailbox
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
    assert "Mock mailbox inspection completed" in result.summary
    assert any(fact.key == "mailbox_exists" for fact in result.facts)
    assert any(fact.key == "archive_status" for fact in result.facts)
    assert "Mailbox content not inspected" in result.limitations
    assert "No permission changes performed" in result.limitations


def test_create_mock_inspector_registry_registers_mailbox_inspector():
    registry = create_mock_inspector_registry()

    handler = registry.get("exchange.mailbox.inspect")

    assert handler is inspect_mock_exchange_mailbox


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
    assert payload["facts"]
    assert payload["limitations"]


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