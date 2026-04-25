# textual_event_sink.py

from collections.abc import Callable

from rich.console import RenderableType
from rich.markdown import Markdown
from rich.text import Text
from textual.widgets import RichLog

from runtime_events import (
    FinalResponseEvent,
    MaxIterationsReachedEvent,
    ModelTurnEvent,
    ProviderErrorEvent,
    RunStartedEvent,
    RuntimeEvent,
    ToolResultEvent,
    UsageSummaryEvent,
)


class TextualEventSink:
    def __init__(
        self,
        log: RichLog,
        *,
        write_callback: Callable[[RenderableType], None] | None = None,
    ) -> None:
        self.log = log
        self.write_callback = write_callback

    def emit(self, event: RuntimeEvent) -> None:
        if isinstance(event, RunStartedEvent):
            self._handle_run_started(event)
            return

        if isinstance(event, ModelTurnEvent):
            self._handle_model_turn(event)
            return

        if isinstance(event, ToolResultEvent):
            self._handle_tool_result(event)
            return

        if isinstance(event, FinalResponseEvent):
            self._handle_final_response(event)
            return

        if isinstance(event, ProviderErrorEvent):
            self._handle_provider_error(event)
            return

        if isinstance(event, MaxIterationsReachedEvent):
            self._handle_max_iterations_reached(event)
            return

        if isinstance(event, UsageSummaryEvent):
            self._handle_usage_summary(event)
            return

    def _write(self, message: RenderableType) -> None:
        if self.write_callback is not None:
            self.write_callback(message)
            return

        self.log.write(message)

    def _write_markup(self, markup: str) -> None:
        self._write(Text.from_markup(markup))

    def _write_markdown(self, markdown: str) -> None:
        self._write(Markdown(markdown))

    def _write_blank(self) -> None:
        self._write("")

    def _handle_run_started(self, event: RunStartedEvent) -> None:
        return

    def _handle_model_turn(self, event: ModelTurnEvent) -> None:
        has_tool_calls = bool(event.tool_calls)

        for text in event.text_parts:
            if text.strip():
                self._write_blank()
                self._write_markup("[bold #a3be8c]Work Copilot[/]")
                if has_tool_calls:
                    self._write(text)
                else:
                    self._write_markdown(text)

        for tool_call in event.tool_calls:
            tool_name = str(tool_call.get("name", "unknown"))
            self._write_markup(f"[#88c0d0]• tool[/] {tool_name}")

    def _handle_tool_result(self, event: ToolResultEvent) -> None:
        status = "ok"

        if event.payload.get("error"):
            status = "error"
        elif event.payload.get("denied_by_user"):
            status = "denied"

        self._write_markup(f"[#88c0d0]• tool result[/] {event.name} ({status})")

    def _handle_final_response(self, event: FinalResponseEvent) -> None:
        return

    def _handle_provider_error(self, event: ProviderErrorEvent) -> None:
        self._write_markup(f"[bold #bf616a]Provider error:[/] {event.error}")

    def _handle_max_iterations_reached(self, event: MaxIterationsReachedEvent) -> None:
        self._write_markup(
            f"[bold #ebcb8b]Max iterations reached:[/] {event.max_iterations}"
        )

    def _handle_usage_summary(self, event: UsageSummaryEvent) -> None:
        return