import json

from run_logging import RunLogEventSink, RunLogger, sanitize_event_payload
from runtime_events import FinalResponseEvent, ToolResultEvent


def test_run_log_event_sink_records_runtime_events(tmp_path):
    logger = RunLogger(
        log_dir=tmp_path,
        metadata={"provider": "test"},
    )
    sink = RunLogEventSink(logger)

    sink.emit(FinalResponseEvent(text="done"))

    path = sink.save()
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert len(payload["events"]) == 1
    assert payload["events"][0]["type"] == "final_response"
    assert payload["events"][0]["text"] == "done"
    assert "timestamp" in payload["events"][0]


def test_sanitize_event_payload_leaves_non_tool_result_unchanged():
    payload = {"text": "hello"}

    result = sanitize_event_payload("final_response", payload)

    assert result == {"text": "hello"}


def test_sanitize_event_payload_leaves_non_connector_tool_result_unchanged():
    payload = {
        "name": "get_file_content",
        "payload": {
            "result": "file contents",
        },
        "call_id": "abc",
    }

    result = sanitize_event_payload("tool_result", payload)

    assert result == payload


def test_sanitize_event_payload_redacts_connector_tool_result(monkeypatch):
    class FakeDefinition:
        connector = "servicedeskplus"
        resource_type = "request_conversation_content"

    def fake_get_tool_definition(name):
        assert name == "servicedesk_get_request_conversation_content"
        return FakeDefinition()

    import tool_registry

    monkeypatch.setattr(tool_registry, "get_tool_definition", fake_get_tool_definition)

    payload = {
        "name": "servicedesk_get_request_conversation_content",
        "payload": {
            "result": {
                "description": "Sensitive conversation body",
                "from": {"name": "Someone"},
            }
        },
        "call_id": "abc",
    }

    result = sanitize_event_payload("tool_result", payload)

    assert result["name"] == "servicedesk_get_request_conversation_content"
    assert result["call_id"] == "abc"
    assert result["payload"]["result"]["redacted"] is True
    assert result["payload"]["result"]["connector"] == "servicedeskplus"
    assert result["payload"]["result"]["resource_type"] == "request_conversation_content"
    assert result["payload"]["result"]["has_description"] is True
    assert "Sensitive conversation body" not in str(result)


def test_run_log_event_sink_redacts_connector_tool_payload(monkeypatch, tmp_path):
    class FakeDefinition:
        connector = "servicedeskplus"
        resource_type = "request"

    def fake_get_tool_definition(name):
        assert name == "servicedesk_get_request"
        return FakeDefinition()

    import tool_registry

    monkeypatch.setattr(tool_registry, "get_tool_definition", fake_get_tool_definition)

    logger = RunLogger(
        log_dir=tmp_path,
        metadata={"test": True},
    )
    sink = RunLogEventSink(logger)

    sink.emit(
        ToolResultEvent(
            name="servicedesk_get_request",
            payload={
                "result": {
                    "request": {
                        "id": "55478",
                        "subject": "Sensitive subject",
                        "description": "Sensitive body",
                    }
                }
            },
            call_id="abc",
        )
    )

    assert len(logger.events) == 1

    event = logger.events[0]
    result = event["payload"]["result"]

    assert result["redacted"] is True
    assert result["connector"] == "servicedeskplus"
    assert result["resource_type"] == "request"
    assert result["request_id"] == "55478"
    assert "Sensitive body" not in str(event)