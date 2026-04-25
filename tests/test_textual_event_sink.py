# tests/test_textual_event_sink.py

from runtime_events import (
    FinalResponseEvent,
    MaxIterationsReachedEvent,
    ModelTurnEvent,
    ProviderErrorEvent,
    RunStartedEvent,
    ToolResultEvent,
    UsageSummaryEvent,
)
from textual_event_sink import TextualEventSink


class FakeRichLog:
    def __init__(self):
        self.messages = []

    def write(self, message):
        self.messages.append(message)


def test_textual_event_sink_renders_run_started():
    log = FakeRichLog()
    sink = TextualEventSink(log)

    sink.emit(RunStartedEvent())

    assert log.messages == []


def test_textual_event_sink_renders_model_text():
    log = FakeRichLog()
    sink = TextualEventSink(log)

    sink.emit(
        ModelTurnEvent(
            text_parts=["Hello"],
            tool_calls=[],
            usage=None,
        )
    )

    assert any("Hello" in str(message) for message in log.messages)


def test_textual_event_sink_renders_tool_call():
    log = FakeRichLog()
    sink = TextualEventSink(log)

    sink.emit(
        ModelTurnEvent(
            text_parts=[],
            tool_calls=[{"name": "get_files_info"}],
            usage=None,
        )
    )

    assert any("get_files_info" in str(message) for message in log.messages)


def test_textual_event_sink_renders_tool_result():
    log = FakeRichLog()
    sink = TextualEventSink(log)

    sink.emit(
        ToolResultEvent(
            name="get_files_info",
            payload={"ok": True},
            call_id="abc123",
        )
    )

    assert any("get_files_info" in str(message) for message in log.messages)


def test_textual_event_sink_renders_denied_tool_result():
    log = FakeRichLog()
    sink = TextualEventSink(log)

    sink.emit(
        ToolResultEvent(
            name="update",
            payload={"denied_by_user": True},
            call_id="abc123",
        )
    )

    assert any("denied" in str(message) for message in log.messages)


def test_textual_event_sink_renders_final_response():
    log = FakeRichLog()
    sink = TextualEventSink(log)

    sink.emit(FinalResponseEvent(text="Done."))

    assert log.messages == []


def test_textual_event_sink_renders_provider_error():
    log = FakeRichLog()
    sink = TextualEventSink(log)

    sink.emit(ProviderErrorEvent(error="boom"))

    assert any("boom" in str(message) for message in log.messages)


def test_textual_event_sink_renders_max_iterations():
    log = FakeRichLog()
    sink = TextualEventSink(log)

    sink.emit(MaxIterationsReachedEvent(max_iterations=20))

    assert any("20" in str(message) for message in log.messages)


def test_textual_event_sink_renders_usage_summary():
    log = FakeRichLog()
    sink = TextualEventSink(log)

    sink.emit(
        UsageSummaryEvent(
            prompt_tokens=10,
            response_tokens=5,
            total_tokens=15,
        )
    )

    assert log.messages == []