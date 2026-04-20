from rich.console import Console

from agent_types import UsageStats
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


def print_verbose_usage(user_prompt: str, usage: UsageStats | None) -> None:
    console.print(f"User prompt: {user_prompt}", style="dim")

    if not usage:
        console.print("Token usage unavailable", style="dim")
        return

    console.print(f"Prompt tokens: {usage.prompt_tokens}", style="dim")
    console.print(f"Response tokens: {usage.response_tokens}", style="dim")


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
    provider.add_user_message(user_prompt)
    tool_specs = get_tool_specs()

    for _ in range(max_iterations):
        turn = provider.generate(system_prompt, tool_specs)

        if verbose:
            print_verbose_usage(user_prompt, turn.usage)

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

        final_text = "\n".join(turn.text_parts).strip()
        if final_text:
            print_final_response(final_text)
            return final_text

    print_error(f"Max iterations ({max_iterations}) reached.")
    return None
