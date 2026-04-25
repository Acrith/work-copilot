# interactive_cli.py

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

from rich.console import Console

from agent_runtime import run_agent
from permissions import PermissionContext
from providers.base import Provider
from run_logging import RunLogger

InteractiveCommand = Literal["exit", "clear", "help", "status", "unknown"]

@dataclass(frozen=True)
class InteractiveSessionConfig:
    provider_name: str
    model: str
    workspace: str
    permission_mode: str
    verbose: bool
    verbose_functions: bool
    max_iterations: int
    log_run: bool
    log_dir: str


@dataclass
class InteractiveSessionState:
    provider: Provider
    interactive_session_id: str
    context_index: int = 1
    turn_index: int = 0

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
    config: InteractiveSessionConfig,
    state: InteractiveSessionState,
) -> None:
    logging_status = "enabled" if config.log_run else "disabled"

    console.print("\nInteractive session status", style="bold")
    console.print(f"  Provider:        {config.provider_name}", style="dim")
    console.print(f"  Model:           {config.model}", style="dim")
    console.print(f"  Workspace:       {config.workspace}", style="dim")
    console.print(f"  Permission mode: {config.permission_mode}", style="dim")
    console.print(f"  Max iterations:  {config.max_iterations}", style="dim")
    console.print(f"  Logging:         {logging_status}", style="dim")

    if config.log_run:
        console.print(f"  Log dir:         {config.log_dir}", style="dim")

    console.print(f"  Session id:      {state.interactive_session_id}", style="dim")
    console.print(f"  Context index:   {state.context_index}", style="dim")
    console.print(f"  Turn index:      {state.turn_index}", style="dim")


def build_interactive_log_dir(log_dir: str, interactive_session_id: str) -> Path:
    return Path(log_dir) / "interactive" / interactive_session_id


def build_interactive_run_logger(
    *,
    config: InteractiveSessionConfig,
    state: InteractiveSessionState,
    user_prompt: str,
) -> RunLogger | None:
    if not config.log_run:
        return None

    interactive_log_dir = build_interactive_log_dir(
        config.log_dir,
        state.interactive_session_id,
    )
    interactive_log_dir.mkdir(parents=True, exist_ok=True)

    return RunLogger(
        log_dir=str(interactive_log_dir),
        metadata={
            "mode": "interactive",
            "interactive_session_id": state.interactive_session_id,
            "context_index": state.context_index,
            "provider": config.provider_name,
            "model": config.model,
            "workspace": config.workspace,
            "permission_mode": config.permission_mode,
            "max_iterations": config.max_iterations,
            "turn_index": state.turn_index,
            "user_prompt": user_prompt,
        },
    )


def run_interactive_model_turn(
    *,
    config: InteractiveSessionConfig,
    state: InteractiveSessionState,
    permission_context: PermissionContext,
    user_prompt: str,
) -> str | None:
    state.turn_index += 1

    run_logger = build_interactive_run_logger(
        config=config,
        state=state,
        user_prompt=user_prompt,
    )

    return run_agent(
        provider=state.provider,
        user_prompt=user_prompt,
        workspace=config.workspace,
        permission_context=permission_context,
        verbose=config.verbose,
        verbose_functions=config.verbose_functions,
        max_iterations=config.max_iterations,
        run_logger=run_logger,
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
    config = InteractiveSessionConfig(
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

    state = InteractiveSessionState(
        provider=provider_factory(),
        interactive_session_id=uuid4().hex[:12],
    )

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
            state.provider = provider_factory()
            state.context_index += 1
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