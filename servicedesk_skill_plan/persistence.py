"""Local-only persistence of ServiceDesk skill-plan validation results.

Writes a small JSON sidecar next to `latest_skill_plan.md` so the TUI's
advisory validation output also lives on disk for later inspection,
debugging, or future tooling. No ServiceDesk, AD, or Exchange writes.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from draft_exports import (
    build_servicedesk_latest_skill_plan_json_path,
    build_servicedesk_latest_skill_plan_validation_path,
)
from servicedesk_skill_plan.models import (
    ExtractedInput,
    ParsedServiceDeskSkillPlan,
    SkillPlanAutomationHandoff,
)
from servicedesk_skill_plan.parser import parse_servicedesk_skill_plan
from servicedesk_skill_plan.validation import (
    SkillPlanValidationFinding,
    format_skill_plan_validation_findings,
    validate_servicedesk_skill_plan,
)

SKILL_PLAN_JSON_SCHEMA_VERSION = 1


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


def serialize_parsed_skill_plan(
    plan: ParsedServiceDeskSkillPlan,
    *,
    request_id: str,
) -> dict[str, object]:
    """Convert a `ParsedServiceDeskSkillPlan` into a stable JSON-ready
    dict using the parser's existing field shapes.

    Stays close to the parser models: status / needed_now /
    ready_for_inspection / ready_for_execution remain strings, and
    suggested tool lists remain lists of strings.
    """
    return {
        "schema_version": SKILL_PLAN_JSON_SCHEMA_VERSION,
        "request_id": request_id,
        "metadata": dict(plan.metadata),
        "extracted_inputs": [
            _extracted_input_to_dict(item) for item in plan.extracted_inputs
        ],
        "missing_information_needed_now": list(
            plan.missing_information_needed_now
        ),
        "current_blocker": plan.current_blocker,
        "automation_handoff": _automation_handoff_to_dict(
            plan.automation_handoff
        ),
    }


def _extracted_input_to_dict(item: ExtractedInput) -> dict[str, str]:
    return {
        "field": item.field,
        "status": item.status,
        "value": item.value,
        "evidence": item.evidence,
        "needed_now": item.needed_now,
    }


def _automation_handoff_to_dict(
    handoff: SkillPlanAutomationHandoff,
) -> dict[str, object]:
    return {
        "ready_for_inspection": handoff.ready_for_inspection,
        "ready_for_execution": handoff.ready_for_execution,
        "suggested_inspector_tools": list(handoff.suggested_inspector_tools),
        "suggested_execute_tools": list(handoff.suggested_execute_tools),
        "automation_blocker": handoff.automation_blocker,
    }


def persist_skill_plan_json_sidecar(
    *,
    workspace: str,
    request_id: str,
    text: str,
) -> list[str]:
    """Parse `text` and write the structured `latest_skill_plan.json`
    sidecar. Never raises.

    Returns advisory log lines (empty on a clean success). On parse
    failure, removes any stale `latest_skill_plan.json` so future
    workflow code does not trust outdated structured data, and returns
    a single advisory line. On write failure, also makes a best-effort
    attempt to remove any stale `latest_skill_plan.json` for the same
    reason, and returns a single advisory line.
    """
    path = build_servicedesk_latest_skill_plan_json_path(
        workspace=workspace,
        request_id=request_id,
    )

    try:
        plan = parse_servicedesk_skill_plan(text)
    except Exception as exc:  # noqa: BLE001 - persistence path must not raise
        _best_effort_unlink(path)
        return [f"Skill plan JSON sidecar unavailable: {exc}"]

    payload = serialize_parsed_skill_plan(plan, request_id=request_id)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001 - persistence is advisory
        # latest_skill_plan.json is intended to become trusted workflow
        # input. If we cannot write the fresh payload, do not leave an
        # older version in place that future workflow code might trust.
        _best_effort_unlink(path)
        return [f"Skill plan JSON sidecar unavailable: {exc}"]

    return []


def _best_effort_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:  # noqa: BLE001 - best-effort cleanup
        pass


def build_persisting_validation_callback(
    *,
    workspace: str,
    request_id: str,
) -> Callable[[str], list[str]]:
    """Return a `post_save_callback` for the model-turn worker that
    validates the saved skill plan, persists the validation JSON
    sidecar and the structured skill-plan JSON sidecar, and returns the
    advisory log lines.
    """

    def _callback(text: str) -> list[str]:
        validation_lines = persist_and_format_skill_plan_validation(
            workspace=workspace,
            request_id=request_id,
            text=text,
        )
        json_lines = persist_skill_plan_json_sidecar(
            workspace=workspace,
            request_id=request_id,
            text=text,
        )
        return [*validation_lines, *json_lines]

    return _callback
