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
from providers.base import Provider
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


def run_agent(
    *,
    provider: Provider,
    user_prompt: str,
    workspace: str,
    permission_context: PermissionContext,
    verbose: bool = False,
    verbose_functions: bool = False,
    max_iterations: int = 20,
) -> str | None:
    # Add the user's first message to provider history.
    provider.add_user_message(user_prompt)
    tool_specs = get_tool_specs()
    usage_totals = UsageTotals()

    for _ in range(max_iterations):
        # Ask the model for the next turn.
        turn = provider.generate(system_prompt, tool_specs)
        usage_totals.add(turn.usage)

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

                if verbose:
                    console.print(result.payload, style="dim")

            provider.add_tool_results(tool_results)
            continue

        # Otherwise print the final answer and stop.
        final_text = "\n".join(turn.text_parts).strip()
        if final_text:
            print_final_response(final_text)
            print_usage_summary(usage_totals)
            return final_text

    print_error(f"Max iterations ({max_iterations}) reached.")
    print_usage_summary(usage_totals)
    return None
