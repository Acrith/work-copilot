# interactive_cli.py

from collections.abc import Callable

from rich.console import Console

from interactive_commands import (
    format_interactive_help,
    format_interactive_status,
    parse_interactive_command,
)
from interactive_session import (
    InteractiveSessionConfig,
    InteractiveSessionState,
    build_interactive_log_dir,
    build_interactive_session_config,
    create_interactive_session_state,
    reset_interactive_context,
    run_interactive_model_turn,
)
from permissions import PermissionContext
from providers.base import Provider

console = Console()


def print_interactive_help() -> None:
    console.print()
    for line in format_interactive_help():
        console.print(line, style="dim")


def print_interactive_status(
    *,
    config: InteractiveSessionConfig,
    state: InteractiveSessionState,
) -> None:
    console.print()
    for line in format_interactive_status(config=config, state=state):
        console.print(line, style="dim")


def run_interactive_session(
    *,
    provider_factory: Callable[[], Provider],
    provider_name: str,
    model: str,
    workspace: str,
    permission_context: PermissionContext,
    permission_mode: str,
    verbose: bool,
    verbose_functions: bool,
    max_iterations: int,
    log_run: bool,
    log_dir: str,
) -> int:
    config = build_interactive_session_config(
        provider_name=provider_name,
        model=model,
        workspace=workspace,
        permission_mode=permission_mode,
        verbose=verbose,
        verbose_functions=verbose_functions,
        max_iterations=max_iterations,
        log_run=log_run,
        log_dir=log_dir,
    )

    state = create_interactive_session_state(provider_factory)

    console.print("Work Copilot interactive mode", style="bold")
    console.print("Type /help for commands. Type /exit to quit.", style="dim")

    if config.log_run:
        interactive_log_dir = build_interactive_log_dir(
            config.log_dir,
            state.interactive_session_id,
        )
        console.print(f"Logging turns under: {interactive_log_dir}", style="dim")

    while True:
        try:
            raw_prompt = input("\nwork-copilot> ")
        except EOFError:
            console.print("\nExiting.", style="dim")
            return 0
        except KeyboardInterrupt:
            console.print("\nExiting.", style="dim")
            return 0

        user_prompt = raw_prompt.strip()

        if not user_prompt:
            continue

        command = parse_interactive_command(user_prompt)

        if command == "exit":
            console.print("Bye.", style="dim")
            return 0

        if command == "help":
            print_interactive_help()
            continue

        if command == "status":
            print_interactive_status(config=config, state=state)
            continue

        if command == "clear":
            reset_interactive_context(
                state=state,
                provider_factory=provider_factory,
            )
            console.print("Session cleared.", style="green")
            continue

        if command == "unknown":
            console.print(
                f"Unknown command: {user_prompt}. Type /help for commands.",
                style="yellow",
            )
            continue

        final_text = run_interactive_model_turn(
            config=config,
            state=state,
            permission_context=permission_context,
            user_prompt=user_prompt,
        )

        if final_text is None:
            console.print(
                "Turn ended without a final response. You can continue or use /clear.",
                style="yellow",
            )