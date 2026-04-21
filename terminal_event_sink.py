from types import SimpleNamespace
from typing import Any

from rich.console import Console

from console_ui import (
    format_tool_call,
    print_agent_update,
    print_error,
    print_final_response,
)
from runtime_events import (
    EventSink,
    FinalResponseEvent,
    MaxIterationsReachedEvent,
    ModelTurnEvent,
    ProviderErrorEvent,
    RuntimeEvent,
    ToolResultEvent,
    UsageSummaryEvent,
)


def is_meaningful_update(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False

    if stripped.startswith("[tool]"):
        return False

    return True


def format_turn_usage(usage: dict[str, Any] | None) -> str:
    if not usage:
        return "Turn usage: unavailable"

    prompt_tokens = usage.get("prompt_tokens")
    response_tokens = usage.get("response_tokens")
    total = (prompt_tokens or 0) + (response_tokens or 0)

    return f"Turn usage: input={prompt_tokens} output={response_tokens} total={total} tokens"


def format_usage_summary_event(event: UsageSummaryEvent) -> str:
    if event.total_tokens is None:
        return "Usage: unavailable"

    return (
        "Usage: "
        f"input={event.prompt_tokens} "
        f"output={event.response_tokens} "
        f"total={event.total_tokens} tokens"
    )


class TerminalEventSink(EventSink):
    def __init__(
        self,
        *,
        verbose: bool = False,
        verbose_functions: bool = False,
        console: Console | None = None,
    ) -> None:
        self.verbose = verbose
        self.verbose_functions = verbose_functions
        self.console = console or Console()

    def emit(self, event: RuntimeEvent) -> None:
        if isinstance(event, ModelTurnEvent):
            self._emit_model_turn(event)
            return

        if isinstance(event, ToolResultEvent):
            self._emit_tool_result(event)
            return

        if isinstance(event, FinalResponseEvent):
            print_final_response(event.text)
            return

        if isinstance(event, ProviderErrorEvent):
            print_error(f"Provider error: {event.error}")
            return

        if isinstance(event, MaxIterationsReachedEvent):
            print_error(f"Max iterations ({event.max_iterations}) reached.")
            return

        if isinstance(event, UsageSummaryEvent):
            self.console.print(format_usage_summary_event(event), style="dim")
            return

    def _emit_model_turn(self, event: ModelTurnEvent) -> None:
        if self.verbose:
            self.console.print(format_turn_usage(event.usage), style="dim")

        if not event.tool_calls:
            return

        for text in event.text_parts:
            if is_meaningful_update(text):
                print_agent_update(text)

        for tool_call in event.tool_calls:
            name = str(tool_call.get("name", ""))
            if name in {"write_file", "update"}:
                continue

            args = tool_call.get("args") or {}
            tool_call_obj = SimpleNamespace(name=name, args=args)
            self.console.print(format_tool_call(tool_call_obj, self.verbose_functions))

    def _emit_tool_result(self, event: ToolResultEvent) -> None:
        if self.verbose:
            self.console.print(event.payload, style="dim")
