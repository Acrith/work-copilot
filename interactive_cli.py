# interactive_cli.py

from collections.abc import Callable
from pathlib import Path
from typing import Literal
from uuid import uuid4

from rich.console import Console

from agent_runtime import run_agent
from permissions import PermissionContext
from providers.base import Provider
from run_logging import RunLogger

InteractiveCommand = Literal["exit", "clear", "help", "status", "unknown"]

console = Console()


def parse_interactive_command(user_input: str) -> InteractiveCommand | None:
    stripped = user_input.strip()

    if not stripped.startswith("/"):
        return None

    command = stripped.split(maxsplit=1)[0].lower()

    if command in {"/exit", "/quit"}:
        return "exit"

    if command == "/clear":
        return "clear"

    if command == "/help":
        return "help"
    
    if command == "/status":
        return "status"

    return "unknown"


def print_interactive_help() -> None:
    console.print(
        "\nCommands:\n"
        "  /help    Show this help\n"
        "  /status  Show current session settings\n"
        "  /clear   Reset provider/session state\n"
        "  /exit    Exit interactive mode\n",
        style="dim",
    )


def print_interactive_status(
    *,
    provider_name: str,
    model: str,
    workspace: str,
    permission_mode: str,
    max_iterations: int,
    log_run: bool,
    log_dir: str,
    interactive_session_id: str,
    context_index: int,
    turn_index: int,
) -> None:
    logging_status = "enabled" if log_run else "disabled"

    console.print("\nInteractive session status", style="bold")
    console.print(f"  Provider:        {provider_name}", style="dim")
    console.print(f"  Model:           {model}", style="dim")
    console.print(f"  Workspace:       {workspace}", style="dim")
    console.print(f"  Permission mode: {permission_mode}", style="dim")
    console.print(f"  Max iterations:  {max_iterations}", style="dim")
    console.print(f"  Logging:         {logging_status}", style="dim")

    if log_run:
        console.print(f"  Log dir:         {log_dir}", style="dim")

    console.print(f"  Session id:      {interactive_session_id}", style="dim")
    console.print(f"  Context index:   {context_index}", style="dim")
    console.print(f"  Turn index:      {turn_index}", style="dim")


def build_interactive_run_logger(
    *,
    enabled: bool,
    log_dir: str,
    provider_name: str,
    model: str,
    workspace: str,
    permission_mode: str,
    max_iterations: int,
    interactive_session_id: str,
    context_index: int,
    turn_index: int,
    user_prompt: str,
) -> RunLogger | None:
    if not enabled:
        return None

    interactive_log_dir = Path(log_dir) / "interactive" / interactive_session_id
    interactive_log_dir.mkdir(parents=True, exist_ok=True)

    return RunLogger(
        log_dir=str(interactive_log_dir),
        metadata={
            "mode": "interactive",
            "interactive_session_id": interactive_session_id,
            "context_index": context_index,
            "provider": provider_name,
            "model": model,
            "workspace": workspace,
            "permission_mode": permission_mode,
            "max_iterations": max_iterations,
            "turn_index": turn_index,
            "user_prompt": user_prompt,
        },
    )


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
    provider = provider_factory()
    interactive_session_id = uuid4().hex[:12]
    context_index = 1
    turn_index = 0

    console.print("Work Copilot interactive mode", style="bold")
    console.print("Type /help for commands. Type /exit to quit.", style="dim")

    if log_run:
        interactive_log_dir = Path(log_dir) / "interactive" / interactive_session_id
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
            print_interactive_status(
                provider_name=provider_name,
                model=model,
                workspace=workspace,
                permission_mode=permission_mode,
                max_iterations=max_iterations,
                log_run=log_run,
                log_dir=log_dir,
                interactive_session_id=interactive_session_id,
                context_index=context_index,
                turn_index=turn_index,
            )
            continue

        if command == "clear":
            provider = provider_factory()
            context_index += 1
            console.print("Session cleared.", style="green")
            continue

        if command == "unknown":
            console.print(
                f"Unknown command: {user_prompt}. Type /help for commands.",
                style="yellow",
            )
            continue

        turn_index += 1
        run_logger = build_interactive_run_logger(
            enabled=log_run,
            log_dir=log_dir,
            provider_name=provider_name,
            model=model,
            workspace=workspace,
            permission_mode=permission_mode,
            max_iterations=max_iterations,
            interactive_session_id=interactive_session_id,
            context_index=context_index,
            turn_index=turn_index,
            user_prompt=user_prompt,
        )

        final_text = run_agent(
            provider=provider,
            user_prompt=user_prompt,
            workspace=workspace,
            permission_context=permission_context,
            verbose=verbose,
            verbose_functions=verbose_functions,
            max_iterations=max_iterations,
            run_logger=run_logger,
        )

        if final_text is None:
            console.print(
                "Turn ended without a final response. You can continue or use /clear.",
                style="yellow",
            )