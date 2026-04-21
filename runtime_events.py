from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol, TypeAlias


@dataclass(frozen=True)
class RunStartedEvent:
    type: str = field(default="run_started", init=False)


@dataclass(frozen=True)
class ModelTurnEvent:
    text_parts: list[str]
    tool_calls: list[dict[str, Any]]
    usage: dict[str, Any] | None
    type: str = field(default="model_turn", init=False)


@dataclass(frozen=True)
class ToolResultEvent:
    name: str
    payload: dict[str, Any]
    call_id: str | None
    type: str = field(default="tool_result", init=False)


@dataclass(frozen=True)
class FinalResponseEvent:
    text: str
    type: str = field(default="final_response", init=False)


@dataclass(frozen=True)
class ProviderErrorEvent:
    error: str
    type: str = field(default="provider_error", init=False)


@dataclass(frozen=True)
class MaxIterationsReachedEvent:
    max_iterations: int
    type: str = field(default="max_iterations_reached", init=False)


@dataclass(frozen=True)
class UsageSummaryEvent:
    prompt_tokens: int | None
    response_tokens: int | None
    total_tokens: int | None
    type: str = field(default="usage_summary", init=False)


RuntimeEvent: TypeAlias = (
    RunStartedEvent
    | ModelTurnEvent
    | ToolResultEvent
    | FinalResponseEvent
    | ProviderErrorEvent
    | MaxIterationsReachedEvent
    | UsageSummaryEvent
)


class EventSink(Protocol):
    def emit(self, event: RuntimeEvent) -> None:
        """Consume a runtime event."""


class ListEventSink:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    def emit(self, event: RuntimeEvent) -> None:
        self.events.append(event)


def event_payload(event: RuntimeEvent) -> tuple[str, dict[str, Any]]:
    payload = asdict(event)
    event_type = payload.pop("type")

    return event_type, payload
