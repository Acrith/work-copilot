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
    "sdp_context",
    "sdp_draft_reply",
    "sdp_triage",
    "unknown",
]

COMMAND_HELP = [
    ("/help", "Show this help"),
    ("/status", "Show current session settings"),
    ("/clear", "Reset provider/session state"),
    ("/sdp context <id>", "Summarize ServiceDesk ticket context and save it locally"),
    ("/sdp triage <limit>", "Rank ServiceDesk tickets by ease/risk/readiness"),
    ("/sdp draft-reply <id>", "Draft a requester reply and save it locally"),
    ("/exit", "Exit interactive mode"),
]


def parse_interactive_command(user_input: str) -> InteractiveCommand:
    stripped = user_input.strip()

    if not stripped.startswith("/"):
        return None

    parts = stripped.split()
    command = parts[0].lower()

    if command in {"/exit", "/quit"}:
        return "exit"

    if command == "/help":
        return "help"

    if command == "/status":
        return "status"

    if command == "/clear":
        return "clear"

    if command == "/triage":
        if len(parts) >= 2 and parts[1].lower() in {"servicedesk", "sdp", "tickets"}:
            return "triage_servicedesk"
        return "unknown"

    if command == "/sdp":
        if len(parts) >= 2 and parts[1].lower() in {"context", "summary", "summarize"}:
            return "sdp_context"

        if len(parts) >= 2 and parts[1].lower() in {"draft-reply", "draft_reply", "reply"}:
            return "sdp_draft_reply"

        if len(parts) >= 2 and parts[1].lower() == "triage":
            return "sdp_triage"

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

    for part in parts[2:]:
        try:
            requested = int(part)
        except ValueError:
            continue

        return max(1, min(requested, maximum))

    return default


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


def parse_sdp_request_id(user_input: str) -> str | None:
    parts = user_input.strip().split()

    if len(parts) < 3:
        return None

    request_id = parts[2].strip()

    if not request_id:
        return None

    return request_id


def build_servicedesk_draft_reply_prompt(request_id: str) -> str:
    return (
        f"Prepare a ServiceDesk reply draft for request {request_id}.\n\n"
        "Use this workflow:\n"
        "1. Read the request details.\n"
        "2. Read request notes.\n"
        "3. Read attachment metadata. Do not download or inspect attachment contents.\n"
        "4. Read request conversations.\n"
        "5. When conversation entries include content_url values and the content is needed, "
        "fetch the conversation content.\n\n"
        "Return a concise draft suitable for the requester. If the situation is unclear, "
        "draft a question asking for the missing information instead of pretending the issue "
        "is resolved.\n\n"
        "Use this output structure:\n\n"
        "# ServiceDesk reply draft\n\n"
        f"Ticket: {request_id}\n"
        "Reply type: public requester reply\n\n"
        "## Draft reply\n\n"
        "<write the reply text here>\n\n"
        "## Internal reasoning\n\n"
        "<briefly explain why this reply is appropriate>\n\n"
        "## Safety notes\n\n"
        "<mention uncertainties, missing information, or risky assumptions>\n\n"
        "Important rules:\n"
        "- Use only read-only ServiceDesk tools.\n"
        "- Do not update ServiceDesk.\n"
        "- Do not add notes.\n"
        "- Do not send replies.\n"
        "- Do not execute commands.\n"
        "- Do not claim attachment contents were inspected."
    )


def build_servicedesk_context_prompt(request_id: str) -> str:
    return (
        f"Prepare a ServiceDesk context summary for request {request_id}.\n\n"
        "Use this workflow:\n"
        "1. Read the request details.\n"
        "2. Read request notes.\n"
        "3. Read attachment metadata. Do not download or inspect attachment contents.\n"
        "4. Read request conversations.\n"
        "5. When conversation entries include content_url values and the content is needed, "
        "fetch the conversation content.\n\n"
        "Return a concise but useful context summary. Focus on what happened, current state, "
        "who is waiting on whom, and the safest next action.\n\n"
        "Use this output structure:\n\n"
        "# ServiceDesk request context\n\n"
        f"Ticket: {request_id}\n\n"
        "## Current state\n\n"
        "Choose one: not yet processed, needs work, waiting for requester, ready to close, "
        "blocked, risky/manual, or unclear.\n\n"
        "## Summary\n\n"
        "<summarize the request and relevant conversation history>\n\n"
        "## Latest known activity\n\n"
        "<summarize the newest meaningful requester/technician activity>\n\n"
        "## Suggested next action\n\n"
        "<recommend the safest next action>\n\n"
        "## Possible reply intent\n\n"
        "Choose one if applicable: ask-info, confirm-resolution, completed, follow-up, "
        "reject-or-explain, or unclear.\n\n"
        "## Context inspected\n\n"
        "List which context was inspected: request details, notes, attachment metadata, "
        "conversations, conversation content.\n\n"
        "## Safety notes\n\n"
        "<mention uncertainty, missing information, risky assumptions, or attachments that "
        "exist but were not inspected>\n\n"
        "Important rules:\n"
        "- Use only read-only ServiceDesk tools.\n"
        "- Do not update ServiceDesk.\n"
        "- Do not add notes.\n"
        "- Do not send replies.\n"
        "- Do not execute commands.\n"
        "- Do not claim attachment contents were inspected."
    )