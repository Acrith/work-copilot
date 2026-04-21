from runtime_events import UsageSummaryEvent
from terminal_event_sink import format_turn_usage, format_usage_summary_event


def test_format_turn_usage_when_missing():
    assert format_turn_usage(None) == "Turn usage: unavailable"


def test_format_turn_usage_with_values():
    assert (
        format_turn_usage(
            {
                "prompt_tokens": 10,
                "response_tokens": 5,
            }
        )
        == "Turn usage: input=10 output=5 total=15 tokens"
    )


def test_format_usage_summary_event_when_missing():
    event = UsageSummaryEvent(
        prompt_tokens=None,
        response_tokens=None,
        total_tokens=None,
    )

    assert format_usage_summary_event(event) == "Usage: unavailable"


def test_format_usage_summary_event_with_values():
    event = UsageSummaryEvent(
        prompt_tokens=10,
        response_tokens=5,
        total_tokens=15,
    )

    assert format_usage_summary_event(event) == ("Usage: input=10 output=5 total=15 tokens")
