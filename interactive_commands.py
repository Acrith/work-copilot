# interactive_commands.py

from typing import Literal

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