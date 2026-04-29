import pytest

from inspectors.models import (
    InspectorError,
    InspectorFact,
    InspectorRequest,
    InspectorResult,
    InspectorStatus,
    InspectorTarget,
)
from inspectors.registry import InspectorRegistry, create_default_inspector_registry


def make_request(inspector: str = "exchange.mailbox.inspect") -> InspectorRequest:
    return InspectorRequest(
        inspector=inspector,
        request_id="55948",
        target=InspectorTarget(
            type="mailbox",
            id="user@example.com",
            metadata={"source": "test"},
        ),
        inputs={"mailbox_address": "user@example.com"},
    )


def test_register_and_get_handler():
    registry = InspectorRegistry()

    def handler(request: InspectorRequest) -> InspectorResult:
        return InspectorResult(
            inspector=request.inspector,
            target=request.target,
            status=InspectorStatus.OK,
            summary="Handled.",
        )

    registry.register("exchange.mailbox.inspect", handler)

    assert registry.get("exchange.mailbox.inspect") is handler


def test_register_duplicate_handler_raises_value_error():
    registry = InspectorRegistry()

    def handler(request: InspectorRequest) -> InspectorResult:
        return InspectorResult(
            inspector=request.inspector,
            target=request.target,
            status=InspectorStatus.OK,
            summary="Handled.",
        )

    registry.register("exchange.mailbox.inspect", handler)

    with pytest.raises(
        ValueError,
        match="Inspector already registered: exchange.mailbox.inspect",
    ):
        registry.register("exchange.mailbox.inspect", handler)


def test_run_registered_handler_returns_result_and_receives_original_request():
    registry = InspectorRegistry()
    captured: dict[str, InspectorRequest] = {}

    def handler(request: InspectorRequest) -> InspectorResult:
        captured["request"] = request

        return InspectorResult(
            inspector=request.inspector,
            target=request.target,
            status=InspectorStatus.OK,
            summary="Mailbox inspected.",
            facts=[
                InspectorFact(
                    key="mailbox_exists",
                    value=True,
                    source="mock_inspector",
                )
            ],
        )

    registry.register("exchange.mailbox.inspect", handler)

    request = make_request()
    result = registry.run(request)

    assert captured["request"] is request
    assert result.inspector == "exchange.mailbox.inspect"
    assert result.target is request.target
    assert result.status == InspectorStatus.OK
    assert result.summary == "Mailbox inspected."
    assert result.facts == [
        InspectorFact(
            key="mailbox_exists",
            value=True,
            source="mock_inspector",
        )
    ]


def test_run_unknown_inspector_returns_structured_error_result():
    registry = InspectorRegistry()
    request = make_request("exchange.unknown.inspect")

    result = registry.run(request)

    assert result.inspector == "exchange.unknown.inspect"
    assert result.target is request.target
    assert result.status == InspectorStatus.ERROR
    assert result.error is True
    assert result.summary == "Inspector not found: exchange.unknown.inspect"
    assert result.facts == []
    assert result.evidence == []
    assert result.limitations == []
    assert result.recommendations == []
    assert result.errors == [
        InspectorError(
            code="inspector_not_found",
            message="No inspector registered for exchange.unknown.inspect",
            recoverable=True,
        )
    ]


def test_unknown_inspector_error_serializes_to_dict():
    registry = InspectorRegistry()
    request = make_request("exchange.unknown.inspect")

    result = registry.run(request)
    payload = result.to_dict()

    assert payload["inspector"] == "exchange.unknown.inspect"
    assert payload["target"] == {
        "type": "mailbox",
        "id": "user@example.com",
        "metadata": {"source": "test"},
    }
    assert payload["status"] == "error"
    assert payload["partial"] is False
    assert payload["errors"] == [
        {
            "code": "inspector_not_found",
            "message": "No inspector registered for exchange.unknown.inspect",
            "recoverable": True,
        }
    ]


def test_create_default_inspector_registry_returns_empty_registry():
    registry = create_default_inspector_registry()

    assert isinstance(registry, InspectorRegistry)
    assert registry.get("exchange.mailbox.inspect") is None