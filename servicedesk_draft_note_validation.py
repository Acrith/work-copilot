"""Local validation for ServiceDesk draft notes before /sdp save-note.

Read-only and side-effect-free. No model calls, no contact with
ServiceDesk, AD, or Exchange. Used as a safety gate inside the
/sdp save-note branch so obviously malformed or unsafe drafts cannot
reach the approval-gated write path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from draft_exports import (
    build_servicedesk_draft_note_path,
    extract_servicedesk_note_body,
)


@dataclass(frozen=True)
class DraftNoteValidationFinding:
    severity: str  # "error" or "warning"
    code: str
    message: str


_NOTE_BODY_HEADING_RE = re.compile(
    r"^\s*##\s+Note body\s*$", re.MULTILINE
)


_PLACEHOLDER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("TODO", re.compile(r"\bTODO\b", re.IGNORECASE)),
    ("TBD", re.compile(r"\bTBD\b", re.IGNORECASE)),
    ("<fill in>", re.compile(r"<\s*fill\s+in\s*>", re.IGNORECASE)),
    ("[fill in]", re.compile(r"\[\s*fill\s+in\s*\]", re.IGNORECASE)),
    ("lorem ipsum", re.compile(r"lorem\s+ipsum", re.IGNORECASE)),
)


_FORBIDDEN_WRITE_CLAIMS: tuple[re.Pattern[str], ...] = (
    re.compile(r"I\s+changed\s+Active\s+Directory", re.IGNORECASE),
    re.compile(r"I\s+updated\s+Active\s+Directory", re.IGNORECASE),
    re.compile(r"I\s+modified\s+the\s+mailbox", re.IGNORECASE),
    re.compile(r"I\s+enabled\s+archive", re.IGNORECASE),
)


def validate_servicedesk_draft_note_text(
    text: str,
) -> list[DraftNoteValidationFinding]:
    """Validate the raw draft-note Markdown text. Never raises.

    Errors block /sdp save-note before the approval-gated write path.
    """
    findings: list[DraftNoteValidationFinding] = []

    note_body = extract_servicedesk_note_body(text)

    if note_body is None:
        # `extract_servicedesk_note_body` returns None for both
        # "heading missing" and "heading present but body empty after
        # stripping". Distinguish so the user gets a precise error.
        if _NOTE_BODY_HEADING_RE.search(text):
            findings.append(
                DraftNoteValidationFinding(
                    severity="error",
                    code="note_body_empty",
                    message=(
                        "Draft note `## Note body` section is empty "
                        "after stripping whitespace."
                    ),
                )
            )
        else:
            findings.append(
                DraftNoteValidationFinding(
                    severity="error",
                    code="note_body_missing",
                    message=(
                        "Draft note has no `## Note body` section; "
                        "/sdp save-note posts only that section."
                    ),
                )
            )
        return findings

    for label, pattern in _PLACEHOLDER_PATTERNS:
        if pattern.search(note_body):
            findings.append(
                DraftNoteValidationFinding(
                    severity="error",
                    code="placeholder_text_present",
                    message=(
                        "Draft note `## Note body` contains placeholder "
                        f"text `{label}`; replace it before saving."
                    ),
                )
            )

    for pattern in _FORBIDDEN_WRITE_CLAIMS:
        match = pattern.search(note_body)
        if match:
            findings.append(
                DraftNoteValidationFinding(
                    severity="error",
                    code="forbidden_write_claim",
                    message=(
                        "Draft note `## Note body` claims an external "
                        f"write (`{match.group(0)}`); workflow runs "
                        "read-only inspection only. Reword before saving."
                    ),
                )
            )

    return findings


def validate_servicedesk_draft_note_file(
    *,
    workspace: str,
    request_id: str,
) -> list[DraftNoteValidationFinding]:
    """Locate and validate the on-disk draft note. Never raises."""
    path = build_servicedesk_draft_note_path(
        workspace=workspace, request_id=request_id
    )

    if not path.exists():
        return [
            DraftNoteValidationFinding(
                severity="error",
                code="draft_note_missing",
                message=f"No local draft note found at {path}.",
            )
        ]

    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - validator must not raise
        return [
            DraftNoteValidationFinding(
                severity="error",
                code="draft_note_unreadable",
                message=(
                    f"Local draft note at {path} could not be read: "
                    f"{exc}"
                ),
            )
        ]

    return validate_servicedesk_draft_note_text(text)


def format_draft_note_validation_findings(
    findings: list[DraftNoteValidationFinding],
) -> list[str]:
    """Format findings into advisory log lines for the TUI."""
    if not findings:
        return ["Draft note validation: no issues found."]

    lines = [
        f"Draft note validation: found {len(findings)} finding(s)."
    ]
    for finding in findings:
        lines.append(
            f"- {finding.severity.upper()} [{finding.code}] "
            f"{finding.message}"
        )
    return lines


def draft_note_findings_have_errors(
    findings: list[DraftNoteValidationFinding],
) -> bool:
    return any(finding.severity == "error" for finding in findings)


_DRAFT_NOTE_VALIDATION_ERROR_ADVISORY = (
    "Draft note has validation errors. Regenerate or edit the draft "
    "before saving."
)


def build_post_save_draft_note_validation_callback(
    *,
    workspace: str,
    request_id: str,
):
    """Build a `post_save_callback` for the /sdp draft-note model-turn
    worker that runs local draft-note validation against the
    just-saved file and returns advisory log lines for the TUI.

    The callback is filesystem-only: it never calls the model, never
    contacts ServiceDesk/AD/Exchange, and never raises. It does not
    auto-save anything; it only surfaces validation results so the
    operator can edit or regenerate the draft if needed.
    """

    def _callback(_saved_text: str) -> list[str]:
        # Validate the on-disk file rather than `_saved_text` so the
        # result is identical to /sdp save-note's later file-based
        # gate. The worker has already written `latest_skill_plan.md`-
        # style "latest" path (draft_note.md) before the post-save
        # callback runs.
        findings = validate_servicedesk_draft_note_file(
            workspace=workspace,
            request_id=request_id,
        )
        lines = format_draft_note_validation_findings(findings)
        if draft_note_findings_have_errors(findings):
            lines.append(_DRAFT_NOTE_VALIDATION_ERROR_ADVISORY)
        return lines

    return _callback


__all__ = [
    "DraftNoteValidationFinding",
    "build_post_save_draft_note_validation_callback",
    "draft_note_findings_have_errors",
    "format_draft_note_validation_findings",
    "validate_servicedesk_draft_note_file",
    "validate_servicedesk_draft_note_text",
]
