import json

from run_logging import RunLogEventSink, RunLogger
from runtime_events import FinalResponseEvent


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
