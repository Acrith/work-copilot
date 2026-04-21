from dataclasses import asdict

from rich.console import Console

from agent_types import UsageTotals
from permissions import PermissionContext
from prompts import system_prompt
from providers.base import Provider, ProviderError
from run_logging import RunLogger
from runtime_events import (
    EventSink,
    FinalResponseEvent,
    MaxIterationsReachedEvent,
    ModelTurnEvent,
    ProviderErrorEvent,
    RunStartedEvent,
    RuntimeEvent,
    ToolResultEvent,
    UsageSummaryEvent,
    event_payload,
)
from terminal_event_sink import TerminalEventSink
from tool_dispatch import execute_tool_call
from tool_registry import get_tool_specs

console = Console()


def build_usage_summary_event(usage_totals: UsageTotals) -> UsageSummaryEvent:
    if not usage_totals.has_usage:
        return UsageSummaryEvent(
            prompt_tokens=None,
            response_tokens=None,
            total_tokens=None,
        )

    return UsageSummaryEvent(
        prompt_tokens=usage_totals.prompt_tokens,
        response_tokens=usage_totals.response_tokens,
        total_tokens=usage_totals.total_tokens,
    )


def save_run_log(run_logger: RunLogger | None) -> None:
    if run_logger is None:
        return

    path = run_logger.save()
    console.print(f"Run log: {path}", style="dim")


def emit_runtime_event(
    *,
    event: RuntimeEvent,
    terminal_sink: EventSink,
    event_sink: EventSink | None,
    run_logger: RunLogger | None,
) -> None:
    terminal_sink.emit(event)

    if event_sink is not None:
        event_sink.emit(event)

    if run_logger is not None:
        event_type, payload = event_payload(event)
        run_logger.record(event_type, **payload)


def run_agent(
    *,
    provider: Provider,
    user_prompt: str,
    workspace: str,
    permission_context: PermissionContext,
    verbose: bool = False,
    verbose_functions: bool = False,
    max_iterations: int = 20,
    run_logger: RunLogger | None = None,
    event_sink: EventSink | None = None,
) -> str | None:
    # Add the user's first message to provider history.
    provider.add_user_message(user_prompt)
    tool_specs = get_tool_specs()
    usage_totals = UsageTotals()

    # Event Rendering
    terminal_sink = TerminalEventSink(
        verbose=verbose,
        verbose_functions=verbose_functions,
    )

    # Run logger | Start
    emit_runtime_event(
        event=RunStartedEvent(),
        terminal_sink=terminal_sink,
        event_sink=event_sink,
        run_logger=run_logger,
    )

    for _ in range(max_iterations):
        # Ask the model for the next turn.
        try:
            turn = provider.generate(system_prompt, tool_specs)
        except ProviderError as e:
            # Run logger | ProviderError
            emit_runtime_event(
                event=ProviderErrorEvent(error=str(e)),
                terminal_sink=terminal_sink,
                event_sink=event_sink,
                run_logger=run_logger,
            )
            emit_runtime_event(
                event=build_usage_summary_event(usage_totals),
                terminal_sink=terminal_sink,
                event_sink=event_sink,
                run_logger=run_logger,
            )
            save_run_log(run_logger)
            return None

        usage_totals.add(turn.usage)

        # Run logger | Turn
        emit_runtime_event(
            event=ModelTurnEvent(
                text_parts=turn.text_parts,
                tool_calls=[asdict(tool_call) for tool_call in turn.tool_calls],
                usage=asdict(turn.usage) if turn.usage else None,
            ),
            terminal_sink=terminal_sink,
            event_sink=event_sink,
            run_logger=run_logger,
        )

        # If the model requested tools, execute them and send results back.
        if turn.tool_calls:
            tool_results = []

            for tool_call in turn.tool_calls:
                result = execute_tool_call(
                    tool_call,
                    workspace,
                    permission_context,
                    verbose=verbose_functions,
                )
                tool_results.append(result)

                # Run Logger | Tool Result
                emit_runtime_event(
                    event=ToolResultEvent(
                        name=result.name,
                        payload=result.payload,
                        call_id=result.call_id,
                    ),
                    terminal_sink=terminal_sink,
                    event_sink=event_sink,
                    run_logger=run_logger,
                )

            provider.add_tool_results(tool_results)
            continue

        # Otherwise print the final answer and stop.
        final_text = "\n".join(turn.text_parts).strip()
        if final_text:
            # Run Logger | Final Response
            emit_runtime_event(
                event=FinalResponseEvent(text=final_text),
                terminal_sink=terminal_sink,
                event_sink=event_sink,
                run_logger=run_logger,
            )
            emit_runtime_event(
                event=build_usage_summary_event(usage_totals),
                terminal_sink=terminal_sink,
                event_sink=event_sink,
                run_logger=run_logger,
            )

            save_run_log(run_logger)
            return final_text

    # Run Logger | Max Iterations
    emit_runtime_event(
        event=MaxIterationsReachedEvent(max_iterations=max_iterations),
        terminal_sink=terminal_sink,
        event_sink=event_sink,
        run_logger=run_logger,
    )
    emit_runtime_event(
        event=build_usage_summary_event(usage_totals),
        terminal_sink=terminal_sink,
        event_sink=event_sink,
        run_logger=run_logger,
    )
    save_run_log(run_logger)
    return None
