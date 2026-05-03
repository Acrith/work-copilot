"""Local-only persistence of ServiceDesk skill-plan validation results.

Writes a small JSON sidecar next to `latest_skill_plan.md` so the TUI's
advisory validation output also lives on disk for later inspection,
debugging, or future tooling. No ServiceDesk, AD, or Exchange writes.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from draft_exports import build_servicedesk_latest_skill_plan_validation_path
from servicedesk_skill_plan.parser import parse_servicedesk_skill_plan
from servicedesk_skill_plan.validation import (
    SkillPlanValidationFinding,
    format_skill_plan_validation_findings,
    validate_servicedesk_skill_plan,
)


@dataclass(frozen=True)
class SkillPlanValidationPersistenceResult:
    """Bundled result for the persisting validator.

    `lines` are the formatted advisory log lines (compatible with the
    existing TUI logger). `payload` is the JSON-serializable validation
    record that is also written to disk.
    """

    lines: list[str]
    payload: dict[str, object]


def validate_skill_plan_text_for_persistence(
    text: str,
) -> SkillPlanValidationPersistenceResult:
    """Parse + validate a saved skill plan and return both the existing
    advisory log lines and a JSON-serializable payload. Never raises.

    On unexpected parse/validate failure, returns a payload with
    `has_errors=True` and a single synthetic `validation_unavailable`
    finding so the persisted record stays honest about why validation
    could not be completed.
    """
    try:
        plan = parse_servicedesk_skill_plan(text)
        findings = validate_servicedesk_skill_plan(plan)
    except Exception as exc:  # noqa: BLE001 - persistence path must not raise
        message = f"Skill plan validation unavailable: {exc}"
        return SkillPlanValidationPersistenceResult(
            lines=[message],
            payload={
                "has_errors": True,
                "findings": [
                    {
                        "severity": "error",
                        "code": "validation_unavailable",
                        "message": message,
                    }
                ],
            },
        )

    lines = format_skill_plan_validation_findings(findings)
    has_errors = any(finding.severity == "error" for finding in findings)

    return SkillPlanValidationPersistenceResult(
        lines=lines,
        payload={
            "has_errors": has_errors,
            "findings": [_finding_to_dict(finding) for finding in findings],
        },
    )


def _finding_to_dict(finding: SkillPlanValidationFinding) -> dict[str, str]:
    return {
        "severity": finding.severity,
        "code": finding.code,
        "message": finding.message,
    }


def persist_skill_plan_validation_payload(
    *,
    workspace: str,
    request_id: str,
    payload: dict[str, object],
) -> Path:
    """Write the validation payload as a JSON sidecar.

    Creates parent directories as needed. Returns the written path.
    """
    path = build_servicedesk_latest_skill_plan_validation_path(
        workspace=workspace,
        request_id=request_id,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return path


def persist_and_format_skill_plan_validation(
    *,
    workspace: str,
    request_id: str,
    text: str,
) -> list[str]:
    """Validate `text`, persist the JSON sidecar, and return advisory
    log lines for the TUI.

    If JSON persistence itself fails, the validation lines are returned
    unchanged plus an extra advisory line describing the persistence
    failure. The validation lines themselves are unaffected so the TUI
    flow is preserved.
    """
    result = validate_skill_plan_text_for_persistence(text)

    try:
        persist_skill_plan_validation_payload(
            workspace=workspace,
            request_id=request_id,
            payload=result.payload,
        )
    except Exception as exc:  # noqa: BLE001 - persistence is advisory
        return [
            *result.lines,
            f"Skill plan validation persistence unavailable: {exc}",
        ]

    return result.lines


def build_persisting_validation_callback(
    *,
    workspace: str,
    request_id: str,
) -> Callable[[str], list[str]]:
    """Return a `post_save_callback` for the model-turn worker that
    validates the saved skill plan, persists the JSON sidecar, and
    returns the advisory log lines.
    """

    def _callback(text: str) -> list[str]:
        return persist_and_format_skill_plan_validation(
            workspace=workspace,
            request_id=request_id,
            text=text,
        )

    return _callback
