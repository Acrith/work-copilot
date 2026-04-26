# interactive_commands.py

from typing import Literal

from rich.table import Table
from rich.text import Text

from interactive_session import InteractiveSessionConfig, InteractiveSessionState

InteractiveCommand = Literal[
    "exit",
    "clear",
    "help",
    "status",
    "triage_servicedesk",
    "unknown",
]

COMMAND_HELP = [
    ("/help", "Show this help"),
    ("/status", "Show current session settings"),
    ("/clear", "Reset provider/session state"),
    ("/triage servicedesk <limit>", "Rank ServiceDesk tickets by ease/risk/readiness"),
    ("/exit", "Exit interactive mode"),
]


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

    if command == "/triage":
        parts = stripped.split()
        if len(parts) >= 2 and parts[1].lower() in {"servicedesk", "sdp", "tickets"}:
            return "triage_servicedesk"
        return "unknown"

    return "unknown"


def format_interactive_help() -> list[str]:
    return [
        "Commands:",
        *[f"  {command}  {description}" for command, description in COMMAND_HELP],
    ]


def build_interactive_help_renderable() -> Table:
    table = Table.grid(padding=(0, 3))
    table.add_column(justify="left", no_wrap=True)
    table.add_column(justify="left")

    table.add_row(Text("Commands:", style="bold #88c0d0"), "")
    for command, description in COMMAND_HELP:
        table.add_row(
            Text(command, style="bold #c586f7"),
            Text(description),
        )

    return table


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


def parse_triage_limit(user_input: str, *, default: int = 10, maximum: int = 20) -> int:
    parts = user_input.strip().split()

    if len(parts) < 3:
        return default

    try:
        requested = int(parts[2])
    except ValueError:
        return default

    return max(1, min(requested, maximum))


def build_servicedesk_triage_prompt(limit: int = 10) -> str:
    return (
        f"Check the default ServiceDesk IT queue. Read up to {limit} requests. "
        "Rank them by easiest to resolve and by automation/skill potential.\n\n"
        "Use this workflow:\n"
        "1. List requests from the configured default ServiceDesk filter.\n"
        "2. Read request details for up to the requested limit.\n"
        "3. For tickets where the status is ambiguous, recent conversation activity exists, "
        "or the ticket may be closeable, inspect request conversations.\n"
        "4. When conversation entries include content_url values and the conversation content "
        "is needed to understand the ticket state, fetch the conversation content.\n"
        "5. Check notes and attachment metadata when they are relevant for context. "
        "Do not download or inspect attachment contents.\n\n"
        "For each request, include:\n"
        "- request ID\n"
        "- subject\n"
        "- requester\n"
        "- status\n"
        "- priority\n"
        "- likely category\n"
        "- current state: not yet processed, needs work, waiting for requester, "
        "ready to close, or unclear\n"
        "- difficulty: easy, medium, hard, or risky\n"
        "- suggested next step\n"
        "- whether it looks like an automation/skill candidate\n"
        "- what context was inspected: request details, conversations, conversation content, "
        "notes, and/or attachment metadata\n\n"
        "Group the results into:\n"
        "1. Quick wins\n"
        "2. Waiting for requester or likely ready to close\n"
        "3. Needs more information\n"
        "4. Automation or skill candidates\n"
        "5. Risky/manual only\n\n"
        "Important rules:\n"
        "- Do not infer ticket status from conversation metadata alone if conversation body "
        "content is needed.\n"
        "- If only metadata is available, clearly say that the actual conversation text was "
        "not inspected.\n"
        "- If attachment metadata shows screenshots or files, mention that attachments exist, "
        "but do not claim to have inspected their contents.\n"
        "- Prefer concise summaries. Do not paste full conversation bodies unless necessary.\n"
        "- Use only read-only ServiceDesk tools. Do not update tickets. "
        "Do not add notes. Do not send replies. Do not execute commands."
        "Limit conversation content fetching to the tickets where it is most useful, "
        "especially closeable, ambiguous, or automation-candidate tickets.\n"
    )