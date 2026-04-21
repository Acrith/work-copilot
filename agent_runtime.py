from dataclasses import asdict

from rich.console import Console

from agent_types import UsageStats, UsageTotals
from console_ui import (
    format_tool_call,
    print_agent_update,
    print_error,
    print_final_response,
)
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
    event_payload,
)
from tool_dispatch import execute_tool_call
from tool_registry import get_tool_specs

console = Console()


def is_meaningful_update(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False

    if stripped.startswith("[tool]"):
        return False

    return True


def print_verbose_usage(usage: UsageStats | None) -> None:
    if not usage:
        console.print("Turn usage: unavailable", style="dim")
        return

    total = (usage.prompt_tokens or 0) + (usage.response_tokens or 0)
    console.print(
        (
            "Turn usage: "
            f"input={usage.prompt_tokens} "
            f"output={usage.response_tokens} "
            f"total={total} tokens"
        ),
        style="dim",
    )


def format_usage_summary(usage_totals: UsageTotals) -> str:
    if not usage_totals.has_usage:
        return "Usage: unavailable"

    return (
        "Usage: "
        f"input={usage_totals.prompt_tokens} "
        f"output={usage_totals.response_tokens} "
        f"total={usage_totals.total_tokens} tokens"
    )


def print_usage_summary(usage_totals: UsageTotals) -> None:
    console.print(format_usage_summary(usage_totals), style="dim")


def save_run_log(run_logger: RunLogger | None) -> None:
    if run_logger is None:
        return

    path = run_logger.save()
    console.print(f"Run log: {path}", style="dim")


def emit_runtime_event(
    *,
    event: RuntimeEvent,
    event_sink: EventSink | None,
    run_logger: RunLogger | None,
) -> None:
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

    # Run logger | Start
    emit_runtime_event(
        event=RunStartedEvent(),
        event_sink=event_sink,
        run_logger=run_logger,
    )

    for _ in range(max_iterations):
        # Ask the model for the next turn.
        try:
            turn = provider.generate(system_prompt, tool_specs)
        except ProviderError as e:
            print_error(f"Provider error: {e}")

            # Run logger | ProviderError
            emit_runtime_event(
                event=ProviderErrorEvent(error=str(e)),
                event_sink=event_sink,
                run_logger=run_logger,
            )

            print_usage_summary(usage_totals)
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
            event_sink=event_sink,
            run_logger=run_logger,
        )

        if verbose:
            print_verbose_usage(turn.usage)

        # If the model requested tools, execute them and send results back.
        if turn.tool_calls:
            for text in turn.text_parts:
                if is_meaningful_update(text):
                    print_agent_update(text)

            tool_results = []

            for tool_call in turn.tool_calls:
                if tool_call.name not in {"write_file", "update"}:
                    console.print(format_tool_call(tool_call, verbose_functions))

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
                    event_sink=event_sink,
                    run_logger=run_logger,
                )

                if verbose:
                    console.print(result.payload, style="dim")

            provider.add_tool_results(tool_results)
            continue

        # Otherwise print the final answer and stop.
        final_text = "\n".join(turn.text_parts).strip()
        if final_text:
            print_final_response(final_text)

            # Run Logger | Final Response
            emit_runtime_event(
                event=FinalResponseEvent(text=final_text),
                event_sink=event_sink,
                run_logger=run_logger,
            )

            print_usage_summary(usage_totals)
            save_run_log(run_logger)
            return final_text

    print_error(f"Max iterations ({max_iterations}) reached.")

    # Run Logger | Max Iterations
    emit_runtime_event(
        event=MaxIterationsReachedEvent(max_iterations=max_iterations),
        event_sink=event_sink,
        run_logger=run_logger,
    )

    print_usage_summary(usage_totals)
    save_run_log(run_logger)
    return None
