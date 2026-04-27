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