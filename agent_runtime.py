from collections.abc import Sequence
from dataclasses import asdict

from rich.console import Console

from agent_types import UsageTotals
from approval import ApprovalHandler
from permissions import PermissionContext
from prompts import system_prompt
from providers.base import Provider, ProviderError
from run_logging import RunLogEventSink, RunLogger
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
)
from terminal_approval import TerminalApprovalHandler
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


def save_run_log(run_log_sink: RunLogEventSink | None) -> None:
    if run_log_sink is None:
        return

    path = run_log_sink.save()
    console.print(f"Run log: {path}", style="dim")


def emit_runtime_event(
    event: RuntimeEvent,
    event_sinks: Sequence[EventSink],
) -> None:
    for sink in event_sinks:
        sink.emit(event)


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
    extra_event_sinks: Sequence[EventSink] | None = None,
    approval_handler: ApprovalHandler | None = None,
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

    resolved_approval_handler = approval_handler or TerminalApprovalHandler()

    run_log_sink = RunLogEventSink(run_logger) if run_logger else None

    event_sinks: list[EventSink] = [terminal_sink]

    if run_log_sink is not None:
        event_sinks.append(run_log_sink)

    if extra_event_sinks is not None:
        event_sinks.extend(extra_event_sinks)

    # Run logger | Start
    emit_runtime_event(
        RunStartedEvent(),
        event_sinks,
    )

    for _ in range(max_iterations):
        # Ask the model for the next turn.
        try:
            turn = provider.generate(system_prompt, tool_specs)
        except ProviderError as e:
            # Run logger | ProviderError
            emit_runtime_event(
                ProviderErrorEvent(error=str(e)),
                event_sinks,
            )
            emit_runtime_event(
                build_usage_summary_event(usage_totals),
                event_sinks,
            )
            save_run_log(run_log_sink)
            return None

        usage_totals.add(turn.usage)

        # Run logger | Turn
        emit_runtime_event(
            ModelTurnEvent(
                text_parts=turn.text_parts,
                tool_calls=[asdict(tool_call) for tool_call in turn.tool_calls],
                usage=asdict(turn.usage) if turn.usage else None,
            ),
            event_sinks,
        )

        # If the model requested tools, execute them and send results back.
        if turn.tool_calls:
            tool_results = []

            for tool_call in turn.tool_calls:
                result = execute_tool_call(
                    tool_call,
                    workspace,
                    permission_context,
                    approval_handler=resolved_approval_handler,
                    verbose=verbose_functions,
                )
                tool_results.append(result)

                # Run Logger | Tool Result
                emit_runtime_event(
                    ToolResultEvent(
                        name=result.name,
                        payload=result.payload,
                        call_id=result.call_id,
                    ),
                    event_sinks,
                )

            provider.add_tool_results(tool_results)
            continue

        # Otherwise print the final answer and stop.
        final_text = "\n".join(turn.text_parts).strip()
        if final_text:
            # Run Logger | Final Response
            emit_runtime_event(
                FinalResponseEvent(text=final_text),
                event_sinks,
            )
            emit_runtime_event(
                build_usage_summary_event(usage_totals),
                event_sinks,
            )

            save_run_log(run_log_sink)
            return final_text

    # Run Logger | Max Iterations
    emit_runtime_event(
        MaxIterationsReachedEvent(max_iterations=max_iterations),
        event_sinks,
    )
    emit_runtime_event(
        build_usage_summary_event(usage_totals),
        event_sinks,
    )
    save_run_log(run_log_sink)
    return None
