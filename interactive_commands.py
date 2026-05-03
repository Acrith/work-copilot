# interactive_commands.py

from typing import Literal

from rich.table import Table
from rich.text import Text

from interactive_session import InteractiveSessionConfig, InteractiveSessionState

# Re-export ServiceDesk prompt builders, shared label constants, and
# shared prompt fragments from servicedesk_prompts so existing imports
# (e.g. `from interactive_commands import build_servicedesk_skill_plan_prompt`)
# keep working after the mechanical refactor.
from servicedesk_prompts import (
    AUTOMATION_CANDIDATE_LABELS,
    CAPABILITY_CLASSIFICATION_LABELS,
    CONFIDENCE_LABELS,
    CURRENT_STATE_LABELS,
    REPLY_INTENT_LABELS,
    REPLY_RECOMMENDED_LABELS,
    RISK_LEVEL_LABELS,
    SERVICEDESK_CHRONOLOGY_RULES,
    SERVICEDESK_CONTEXT_WORKFLOW,
    SERVICEDESK_DRAFT_REPLY_LANGUAGE_GUIDANCE,
    SERVICEDESK_DRAFT_REPLY_TONE_GUIDANCE,
    SERVICEDESK_READ_ONLY_RULES,
    build_servicedesk_context_prompt,
    build_servicedesk_draft_note_prompt,
    build_servicedesk_draft_reply_prompt,
    build_servicedesk_skill_plan_prompt,
    build_servicedesk_skill_plan_repair_prompt,
    format_allowed_label_section,
    format_allowed_labels,
)

InteractiveCommand = Literal[
    "exit",
    "clear",
    "help",
    "status",
    "triage_servicedesk",
    "sdp_context",
    "sdp_draft_reply",
    "sdp_save_draft",
    "sdp_skill_plan",
    "sdp_repair_skill_plan",
    "sdp_inspect_skill",
    "sdp_inspection_report",
    "sdp_draft_note",
    "sdp_save_note",
    "sdp_status",
    "sdp_work",
    "sdp_triage",
    "unknown",
]

COMMAND_HELP = [
    ("/help", "Show this help"),
    ("/status", "Show current session settings"),
    ("/clear", "Reset provider/session state"),
    ("/sdp context <id>", "Summarize ServiceDesk ticket context and save it locally"),
    ("/sdp draft-reply <id>", "Draft a requester reply and save it locally"),
    ("/sdp save-draft <id>", "Save latest local reply as a ServiceDesk draft"),
    ("/sdp skill-plan <id>", "Prepare a read-only skill plan for ServiceDesk request"),
    (
        "/sdp repair-skill-plan <id>",
        "Repair latest local skill plan using validation findings",
    ),
    ("/sdp inspect-skill <id>", "Run registered read-only inspectors from the latest skill plan"),
    (
        "/sdp inspection-report <id>",
        "Render saved inspector JSON into a local Markdown report",
    ),
    (
        "/sdp draft-note <id>",
        "Draft a local internal technician note from saved context and inspection report",
    ),
    (
        "/sdp save-note <id>",
        "Save the local note draft as an internal ServiceDesk note (approval-gated)",
    ),
    (
        "/sdp status <id>",
        "Show local ServiceDesk workflow state and next safe action",
    ),
    ("/sdp work <id>", "Advance ServiceDesk workflow by one safe step"),
    ("/sdp triage <limit>", "Rank ServiceDesk tickets by ease/risk/readiness"),
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

        if len(parts) >= 2 and parts[1].lower() in {"save-draft", "save_draft"}:
            return "sdp_save_draft"

        if len(parts) >= 2 and parts[1].lower() in {
            "repair-skill-plan",
            "repair_skill_plan",
            "repair-plan",
            "repair_plan",
        }:
            return "sdp_repair_skill_plan"

        if len(parts) >= 2 and parts[1].lower() in {"skill-plan", "skill_plan"}:
            return "sdp_skill_plan"

        if len(parts) >= 2 and parts[1].lower() in {"inspect-skill", "inspect_skill"}:
            return "sdp_inspect_skill"

        if len(parts) >= 2 and parts[1].lower() in {
            "inspection-report",
            "inspection_report",
        }:
            return "sdp_inspection_report"

        if len(parts) >= 2 and parts[1].lower() in {
            "draft-note",
            "draft_note",
            "note",
        }:
            return "sdp_draft_note"

        if len(parts) >= 2 and parts[1].lower() in {
            "save-note",
            "save_note",
        }:
            return "sdp_save_note"

        if len(parts) >= 2 and parts[1].lower() in {
            "status",
            "workflow-status",
            "workflow_status",
        }:
            return "sdp_status"

        if len(parts) >= 2 and parts[1].lower() in {"work", "continue"}:
            return "sdp_work"

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
        "Triage them by how well they fit Work Copilot's current local "
        "workflow so the operator can quickly pick which ticket to run "
        "`/sdp work <id>` on next.\n\n"
        "Use this workflow:\n"
        "1. List requests from the configured default ServiceDesk filter.\n"
        "2. Read request details for up to the requested limit.\n"
        "3. For tickets where the status is ambiguous, recent conversation activity exists, "
        "or the ticket may be closeable, inspect request conversations.\n"
        "4. When conversation entries include content_url values and the conversation content "
        "is needed to understand the ticket state, fetch the conversation content.\n"
        "5. Check notes and attachment metadata when they are relevant for context. "
        "Do not download or inspect attachment contents.\n\n"
        "Current Work Copilot capability boundary (use this to decide fit):\n"
        "- Read-only Active Directory inspection of a single user, group, "
        "or user/group membership pair (no AD writes).\n"
        "- Read-only Exchange Online mailbox inspection (no Exchange "
        "writes; no mailbox content / attachment / message inspection).\n"
        "- Local-only ServiceDesk context summary, skill plan, "
        "inspection report, and internal-note draft generation.\n"
        "- The only ServiceDesk write is `/sdp save-note <id>`, which is "
        "explicit and approval-gated. Triage must not post anything, run "
        "any inspector, or modify any ticket.\n\n"
        "For each candidate request, include:\n"
        "- request ID\n"
        "- short title / subject\n"
        "- requester\n"
        "- status / priority\n"
        "- likely skill or category (e.g. `active_directory.user.inspect`, "
        "`active_directory.group.inspect`, "
        "`active_directory.group_membership.inspect`, "
        "`exchange.mailbox.inspect`, "
        "`active_directory.user.update_profile_attributes` (draft-only), "
        "`exchange.shared_mailbox.grant_full_access` (manual), …)\n"
        "- confidence in the skill match: high, medium, or low\n"
        "- fit (one of: `ready_for_work`, `needs_missing_info`, "
        "`draft_only_manual`, `unsupported_or_risky`)\n"
        "- suggested next command (one of: `/sdp work <id>`, "
        "`/sdp status <id>`, or `manual review`)\n"
        "- one-sentence why\n"
        "- what context was inspected: request details, conversations, "
        "conversation content, notes, and/or attachment metadata\n\n"
        "Fit definitions:\n"
        "- `ready_for_work`: target identity is clear, the likely skill "
        "is one of the supported read-only inspectors, and a "
        "technician-facing draft note plus optional manual action is a "
        "credible next step. Suggested next command: `/sdp work <id>`.\n"
        "- `needs_missing_info`: the request is plausibly in scope but "
        "is missing target identity (mailbox address, AD user/group "
        "identifier), missing approval, or missing required input. "
        "Suggested next action: `manual review` (ask the requester or "
        "clarify the ticket); do not recommend `/sdp work <id>` until "
        "the missing info is on the ticket.\n"
        "- `draft_only_manual`: the work itself requires manual "
        "technician action that Work Copilot cannot perform (e.g. "
        "Exchange shared-mailbox permissions, AD profile attribute "
        "edits), but a local context/inspection/draft-note pass would "
        "still be useful evidence for the technician. Suggested next "
        "command: `/sdp work <id>` only if local inspection or a draft "
        "note would help; otherwise `manual review`.\n"
        "- `unsupported_or_risky`: out of scope for the current "
        "capability set (broad/mass changes, destructive operations, "
        "requires write automation that Work Copilot does not have, "
        "requires inspecting mailbox content/attachments, multiple "
        "targets at once, cross-forest, etc.). Suggested next action: "
        "`manual review`. Do not recommend `/sdp work <id>`.\n\n"
        "Group the results in this exact section order, using these "
        "Markdown headings so the output is scan-friendly:\n\n"
        "# ServiceDesk triage\n\n"
        "## High-confidence / ready for work\n"
        "## Manual-only / draft-only\n"
        "## Needs clarification\n"
        "## Unsupported / risky\n\n"
        "Within each section, sort by likely operator value (clearest "
        "target first). Omit a section entirely if it has no entries.\n\n"
        "Prefer tickets that benefit from:\n"
        "- read-only AD or Exchange mailbox inspection of a single, "
        "clearly-named target\n"
        "- a local draft note that summarizes inspection findings for "
        "the technician\n"
        "- manual technician action backed by good local inspection "
        "evidence\n\n"
        "De-prioritize:\n"
        "- unclear or context-free requests\n"
        "- requests with no identifiable target user / mailbox / group\n"
        "- broad or mass changes (multiple users, many mailboxes)\n"
        "- destructive or high-risk changes (delete account, purge "
        "mailbox, remove permissions for many users)\n"
        "- requests that need write automation Work Copilot does not "
        "support\n\n"
        "Important rules:\n"
        "- Do not infer ticket status from conversation metadata alone if conversation body "
        "content is needed.\n"
        "- If only metadata is available, clearly say that the actual conversation text was "
        "not inspected.\n"
        "- If attachment metadata shows screenshots or files, mention that attachments exist, "
        "but do not claim to have inspected their contents.\n"
        "- Prefer concise summaries. Do not paste full conversation bodies unless necessary.\n"
        "- Use only read-only ServiceDesk tools. Do not update tickets. "
        "Do not add notes. Do not send replies. Do not execute commands. "
        "Do not run inspectors from triage; inspector runs only happen "
        "via `/sdp work <id>` or `/sdp inspect-skill <id>` after the "
        "operator picks a ticket.\n"
        "- Do not claim triage will solve, fix, post, or write anything "
        "automatically. Triage only reads tickets and recommends a next "
        "command. The only ServiceDesk write remains "
        "`/sdp save-note <id>`, and only after the operator "
        "intentionally runs and approves it.\n"
        "- Limit conversation content fetching to the tickets where it is most useful, "
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


__all__ = [
    "AUTOMATION_CANDIDATE_LABELS",
    "CAPABILITY_CLASSIFICATION_LABELS",
    "COMMAND_HELP",
    "CONFIDENCE_LABELS",
    "CURRENT_STATE_LABELS",
    "InteractiveCommand",
    "REPLY_INTENT_LABELS",
    "REPLY_RECOMMENDED_LABELS",
    "RISK_LEVEL_LABELS",
    "SERVICEDESK_CHRONOLOGY_RULES",
    "SERVICEDESK_CONTEXT_WORKFLOW",
    "SERVICEDESK_DRAFT_REPLY_LANGUAGE_GUIDANCE",
    "SERVICEDESK_DRAFT_REPLY_TONE_GUIDANCE",
    "SERVICEDESK_READ_ONLY_RULES",
    "build_interactive_help_renderable",
    "build_servicedesk_context_prompt",
    "build_servicedesk_draft_note_prompt",
    "build_servicedesk_draft_reply_prompt",
    "build_servicedesk_skill_plan_prompt",
    "build_servicedesk_skill_plan_repair_prompt",
    "build_servicedesk_triage_prompt",
    "format_allowed_label_section",
    "format_allowed_labels",
    "format_interactive_help",
    "format_interactive_status",
    "parse_interactive_command",
    "parse_sdp_request_id",
    "parse_triage_limit",
]
