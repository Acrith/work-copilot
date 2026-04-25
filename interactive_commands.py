# interactive_commands.py

from typing import Literal

from interactive_session import InteractiveSessionConfig, InteractiveSessionState

InteractiveCommand = Literal["exit", "clear", "help", "status", "unknown"]


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


def format_interactive_help() -> list[str]:
    return [
        "Commands:",
        "  /help    Show this help",
        "  /status  Show current session settings",
        "  /clear   Reset provider/session state",
        "  /exit    Exit interactive mode",
    ]


def format_interactive_status(
    *,
    config: InteractiveSessionConfig,
    state: InteractiveSessionState,
) -> list[str]:
    logging_status = "enabled" if config.log_run else "disabled"

    lines = [
        "Interactive session status",
        f"  Provider:        {config.provider_name}",
        f"  Model:           {config.model}",
        f"  Workspace:       {config.workspace}",
        f"  Permission mode: {config.permission_mode}",
        f"  Max iterations:  {config.max_iterations}",
        f"  Logging:         {logging_status}",
    ]

    if config.log_run:
        lines.append(f"  Log dir:         {config.log_dir}")

    lines.extend(
        [
            f"  Session id:      {state.interactive_session_id}",
            f"  Context index:   {state.context_index}",
            f"  Turn index:      {state.turn_index}",
        ]
    )

    return lines