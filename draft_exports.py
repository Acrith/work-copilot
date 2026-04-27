from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path


def safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("_") or "draft"


def _timestamp(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y%m%d_%H%M%S")


def build_servicedesk_output_dir(
    *,
    workspace: str,
    request_id: str,
) -> Path:
    safe_request_id = safe_filename_part(request_id)

    return Path(workspace) / ".work_copilot" / "servicedesk" / safe_request_id


def build_servicedesk_draft_path(
    *,
    workspace: str,
    request_id: str,
    now: datetime | None = None,
) -> Path:
    return (
        build_servicedesk_output_dir(workspace=workspace, request_id=request_id)
        / f"reply_{_timestamp(now)}.md"
    )


def build_servicedesk_context_path(
    *,
    workspace: str,
    request_id: str,
    now: datetime | None = None,
) -> Path:
    return (
        build_servicedesk_output_dir(workspace=workspace, request_id=request_id)
        / f"context_{_timestamp(now)}.md"
    )


def build_servicedesk_latest_draft_path(
    *,
    workspace: str,
    request_id: str,
) -> Path:
    return (
        build_servicedesk_output_dir(workspace=workspace, request_id=request_id)
        / "latest_reply.md"
    )


def build_servicedesk_latest_context_path(
    *,
    workspace: str,
    request_id: str,
) -> Path:
    return (
        build_servicedesk_output_dir(workspace=workspace, request_id=request_id)
        / "latest_context.md"
    )


def save_text_draft(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def read_text_if_exists(path: Path) -> str | None:
    if not path.exists():
        return None

    return path.read_text(encoding="utf-8")


NO_REQUESTER_REPLY_RECOMMENDED = "No requester-facing reply recommended at this time."


def extract_markdown_section(markdown: str, heading: str) -> str | None:
    target = f"## {heading}".strip()
    lines = markdown.splitlines()

    in_section = False
    section_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        if stripped == target:
            in_section = True
            continue

        if in_section and stripped.startswith("## "):
            break

        if in_section:
            section_lines.append(line)

    section = "\n".join(section_lines).strip()
    return section or None


def extract_servicedesk_draft_reply(markdown: str) -> str | None:
    return extract_markdown_section(markdown, "Draft reply")


def is_no_requester_reply_recommended(text: str) -> bool:
    return text.strip().rstrip(".") == NO_REQUESTER_REPLY_RECOMMENDED.rstrip(".")


def build_servicedesk_draft_subject(request_id: str) -> str:
    return f"Re: ServiceDesk request {request_id}"