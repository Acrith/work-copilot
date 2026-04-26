from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path


def safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("_") or "draft"


def build_servicedesk_draft_path(
    *,
    workspace: str,
    request_id: str,
    now: datetime | None = None,
) -> Path:
    timestamp = (now or datetime.now(UTC)).strftime("%Y%m%d_%H%M%S")
    safe_request_id = safe_filename_part(request_id)

    return (
        Path(workspace)
        / ".work_copilot"
        / "drafts"
        / f"servicedesk_{safe_request_id}_reply_{timestamp}.md"
    )


def save_text_draft(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path