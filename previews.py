import difflib
import os
import re
from dataclasses import dataclass

from functions.update_file import plan_update

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class ParsedDiffLine:
    kind: str  # "context", "add", "remove", "meta", "hunk"
    text: str
    old_lineno: int | None = None
    new_lineno: int | None = None


@dataclass
class ParsedDiff:
    lines: list[ParsedDiffLine]


def normalize_tool_path(working_directory: str, file_path: str) -> tuple[str, str]:
    workspace = os.path.abspath(working_directory)
    target = os.path.normpath(os.path.join(workspace, file_path))
    return workspace, target


def build_write_preview(working_directory: str, file_path: str, new_content: str) -> str:
    workspace, target = normalize_tool_path(working_directory, file_path)

    if os.path.commonpath([workspace, target]) != workspace:
        return f'Preview unavailable: "{file_path}" is outside the workspace.'

    if os.path.isdir(target):
        return f'Preview unavailable: "{file_path}" is a directory.'

    if not os.path.exists(target):
        added = "\n".join(f"+ {line}" for line in new_content.splitlines())
        return f'New file: "{file_path}"\n' + (added or "+ <empty file>")

    try:
        with open(target, "r", encoding="utf-8") as f:
            old_content = f.read()
    except Exception as e:
        return f"Could not read existing file for preview: {e}"

    diff = difflib.unified_diff(
        old_content.splitlines(),
        new_content.splitlines(),
        fromfile=f"{file_path} (current)",
        tofile=f"{file_path} (proposed)",
        lineterm="",
    )
    preview = "\n".join(diff)
    return preview if preview.strip() else f'No content changes for "{file_path}".'


def build_update_preview(
    working_directory: str,
    file_path: str,
    old_text: str,
    new_text: str,
) -> str:
    plan = plan_update(working_directory, file_path, old_text, new_text)

    if plan["status"] == "error":
        return f"Preview unavailable: {plan['message']}"

    if plan["status"] == "no_change":
        return plan["message"]

    diff = difflib.unified_diff(
        plan["current_content"].splitlines(),
        plan["updated_content"].splitlines(),
        fromfile=f"{file_path} (current)",
        tofile=f"{file_path} (proposed)",
        lineterm="",
    )
    preview = "\n".join(diff)
    return preview if preview.strip() else f'No content changes for "{file_path}".'


def parse_unified_diff(diff_text: str) -> ParsedDiff:
    lines: list[ParsedDiffLine] = []
    old_ln: int | None = None
    new_ln: int | None = None

    for raw in diff_text.splitlines():
        if raw.startswith("--- ") or raw.startswith("+++ "):
            lines.append(ParsedDiffLine(kind="meta", text=raw))
            continue

        match = HUNK_RE.match(raw)
        if match:
            old_start, _, new_start, _ = match.groups()
            old_ln = int(old_start)
            new_ln = int(new_start)
            lines.append(ParsedDiffLine(kind="hunk", text=raw))
            continue

        if raw.startswith("-"):
            lines.append(
                ParsedDiffLine(
                    kind="remove",
                    text=raw[1:],
                    old_lineno=old_ln,
                    new_lineno=None,
                )
            )
            if old_ln is not None:
                old_ln += 1
            continue

        if raw.startswith("+"):
            lines.append(
                ParsedDiffLine(
                    kind="add",
                    text=raw[1:],
                    old_lineno=None,
                    new_lineno=new_ln,
                )
            )
            if new_ln is not None:
                new_ln += 1
            continue

        text = raw[1:] if raw.startswith(" ") else raw
        lines.append(
            ParsedDiffLine(
                kind="context",
                text=text,
                old_lineno=old_ln,
                new_lineno=new_ln,
            )
        )
        if old_ln is not None:
            old_ln += 1
        if new_ln is not None:
            new_ln += 1

    return ParsedDiff(lines=lines)


def is_unified_diff_preview(preview: str) -> bool:
    lines = preview.splitlines()
    return len(lines) >= 2 and lines[0].startswith("--- ") and lines[1].startswith("+++ ")


def summarize_diff(diff_text: str) -> tuple[int, int]:
    additions = 0
    removals = 0
    for line in diff_text.splitlines():
        if line.startswith("+++ ") or line.startswith("--- "):
            continue
        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            removals += 1
    return additions, removals


def build_connector_write_preview(
    tool_name: str,
    args: dict[str, object],
) -> str | None:
    if tool_name == "servicedesk_add_request_draft":
        request_id = args.get("request_id", "")
        subject = args.get("subject", "")
        draft_type = args.get("draft_type", "reply")
        description = args.get("description", "")

        return "\n".join(
            [
                "# ServiceDesk draft reply",
                "",
                f"**Action:** Save draft reply",
                f"**Ticket:** {request_id}",
                f"**Type:** {draft_type}",
                "",
                "## Subject",
                "",
                str(subject),
                "",
                "## Draft body",
                "",
                str(description),
                "",
                "---",
                "",
                "## Safety",
                "",
                "This will save a draft in ServiceDesk Plus.",
                "It will not send the reply to the requester.",
            ]
        )

    return None
