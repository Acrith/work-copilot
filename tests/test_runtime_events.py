from runtime_events import FinalResponseEvent, ListEventSink, RunStartedEvent, event_payload


def test_event_payload_extracts_type_and_payload():
    event_type, payload = event_payload(FinalResponseEvent(text="done"))

    assert event_type == "final_response"
    assert payload == {"text": "done"}


def test_list_event_sink_stores_events():
    sink = ListEventSink()

    event = RunStartedEvent()
    sink.emit(event)

    assert sink.events == [event]
