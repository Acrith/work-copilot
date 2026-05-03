"""Read local ServiceDesk workflow artifacts for a request and compute a
deterministic workflow state (current stage, recommended next action,
blocker info, status lines).

This module is read-only and side-effect-free except for reading local
files under `.work_copilot/servicedesk/<request_id>/`. It does not call
ServiceDesk, AD, Exchange, or any inspector. It does not regenerate or
modify any artifact. It is intended as a foundation for future
user-facing commands such as `/sdp work <id>` and `/sdp status <id>`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from draft_exports import (
    build_servicedesk_draft_note_path,
    build_servicedesk_latest_context_path,
    build_servicedesk_latest_skill_plan_json_path,
    build_servicedesk_latest_skill_plan_path,
    build_servicedesk_latest_skill_plan_validation_path,
)
from inspectors.inspection_report import (
    SUPPORTED_REPORT_INSPECTOR_IDS,
    build_servicedesk_inspection_report_path,
)
from inspectors.storage import (
    build_inspector_output_dir,
    build_inspector_result_path,
)


class ServiceDeskWorkflowStage(StrEnum):
    MISSING_CONTEXT = "missing_context"
    MISSING_SKILL_PLAN = "missing_skill_plan"
    SKILL_PLAN_INVALID = "skill_plan_invalid"
    READY_FOR_INSPECTION = "ready_for_inspection"
    INSPECTION_MISSING = "inspection_missing"
    INSPECTION_REPORT_MISSING = "inspection_report_missing"
    DRAFT_NOTE_MISSING = "draft_note_missing"
    READY_FOR_REVIEW = "ready_for_review"
    READY_TO_SAVE_NOTE = "ready_to_save_note"
    UNKNOWN = "unknown"


class ServiceDeskWorkflowNextAction(StrEnum):
    RUN_CONTEXT = "run_context"
    RUN_SKILL_PLAN = "run_skill_plan"
    REPAIR_SKILL_PLAN = "repair_skill_plan"
    RUN_INSPECTION = "run_inspection"
    BUILD_INSPECTION_REPORT = "build_inspection_report"
    DRAFT_NOTE = "draft_note"
    REVIEW_DRAFT_NOTE = "review_draft_note"
    SAVE_NOTE = "save_note"
    NONE = "none"


@dataclass(frozen=True)
class ServiceDeskWorkflowValidationFinding:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class ServiceDeskSkillPlanSummary:
    """Read-only display summary of `latest_skill_plan.json`.

    Display-only in this PR. Workflow stage/next-action decisions still
    use existing artifact checks and `latest_skill_plan_validation.json`.
    """

    exists: bool = False
    readable: bool = False
    schema_version: int | None = None
    skill_match: str | None = None
    capability_classification: str | None = None
    ready_for_inspection: str | None = None
    ready_for_execution: str | None = None
    suggested_inspector_tools: list[str] = field(default_factory=list)
    suggested_execute_tools: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class ServiceDeskWorkflowState:
    request_id: str
    context_exists: bool = False
    skill_plan_exists: bool = False
    validation_exists: bool = False
    validation_has_errors: bool | None = None
    validation_findings: list[ServiceDeskWorkflowValidationFinding] = field(
        default_factory=list
    )
    inspector_outputs_exist: bool = False
    inspection_report_exists: bool = False
    draft_note_exists: bool = False
    skill_plan_summary: ServiceDeskSkillPlanSummary = field(
        default_factory=ServiceDeskSkillPlanSummary
    )
    stage: ServiceDeskWorkflowStage = ServiceDeskWorkflowStage.UNKNOWN
    next_action: ServiceDeskWorkflowNextAction = (
        ServiceDeskWorkflowNextAction.NONE
    )
    blocked: bool = False
    blocker: str | None = None
    status_lines: list[str] = field(default_factory=list)


def read_servicedesk_workflow_state(
    *,
    workspace: str,
    request_id: str,
) -> ServiceDeskWorkflowState:
    """Inspect local artifacts and return a deterministic workflow state."""
    context_path = build_servicedesk_latest_context_path(
        workspace=workspace, request_id=request_id
    )
    skill_plan_path = build_servicedesk_latest_skill_plan_path(
        workspace=workspace, request_id=request_id
    )
    validation_path = build_servicedesk_latest_skill_plan_validation_path(
        workspace=workspace, request_id=request_id
    )
    inspection_report_path = build_servicedesk_inspection_report_path(
        workspace=workspace, request_id=request_id
    )
    draft_note_path = build_servicedesk_draft_note_path(
        workspace=workspace, request_id=request_id
    )

    context_exists = context_path.exists()
    skill_plan_exists = skill_plan_path.exists()
    validation_exists = validation_path.exists()

    validation_has_errors: bool | None
    validation_findings: list[ServiceDeskWorkflowValidationFinding]

    if validation_exists:
        (
            validation_has_errors,
            validation_findings,
        ) = _read_validation_sidecar(validation_path)
    else:
        validation_has_errors = None
        validation_findings = []

    inspector_outputs_exist = _any_supported_inspector_output_exists(
        workspace=workspace,
        request_id=request_id,
    )
    inspection_report_exists = inspection_report_path.exists()
    draft_note_exists = draft_note_path.exists()

    skill_plan_json_path = build_servicedesk_latest_skill_plan_json_path(
        workspace=workspace, request_id=request_id
    )
    skill_plan_summary = _read_skill_plan_json_summary(skill_plan_json_path)

    stage, next_action, blocked, blocker = _decide_stage_and_next_action(
        context_exists=context_exists,
        skill_plan_exists=skill_plan_exists,
        validation_exists=validation_exists,
        validation_has_errors=validation_has_errors,
        validation_findings=validation_findings,
        inspector_outputs_exist=inspector_outputs_exist,
        inspection_report_exists=inspection_report_exists,
        draft_note_exists=draft_note_exists,
    )

    status_lines = _format_status_lines(
        request_id=request_id,
        context_exists=context_exists,
        skill_plan_exists=skill_plan_exists,
        validation_exists=validation_exists,
        validation_has_errors=validation_has_errors,
        validation_findings=validation_findings,
        inspector_outputs_exist=inspector_outputs_exist,
        inspection_report_exists=inspection_report_exists,
        draft_note_exists=draft_note_exists,
        skill_plan_summary=skill_plan_summary,
        stage=stage,
        next_action=next_action,
        blocked=blocked,
        blocker=blocker,
    )

    return ServiceDeskWorkflowState(
        request_id=request_id,
        context_exists=context_exists,
        skill_plan_exists=skill_plan_exists,
        validation_exists=validation_exists,
        validation_has_errors=validation_has_errors,
        validation_findings=validation_findings,
        inspector_outputs_exist=inspector_outputs_exist,
        inspection_report_exists=inspection_report_exists,
        draft_note_exists=draft_note_exists,
        skill_plan_summary=skill_plan_summary,
        stage=stage,
        next_action=next_action,
        blocked=blocked,
        blocker=blocker,
        status_lines=status_lines,
    )


# ---- Private helpers ---------------------------------------------------


def _read_validation_sidecar(
    path: Path,
) -> tuple[bool, list[ServiceDeskWorkflowValidationFinding]]:
    """Read the JSON sidecar without raising. On any read/parse failure
    or shape mismatch, treat the sidecar as unreadable: report
    `has_errors=True` with a synthetic `validation_sidecar_unreadable`
    finding so the caller can block conservatively.
    """
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 - state read must not raise
        return True, [
            ServiceDeskWorkflowValidationFinding(
                severity="error",
                code="validation_sidecar_unreadable",
                message=(
                    "Local skill plan validation sidecar could not be read: "
                    f"{exc}"
                ),
            )
        ]

    if not isinstance(payload, dict):
        return True, [
            ServiceDeskWorkflowValidationFinding(
                severity="error",
                code="validation_sidecar_unreadable",
                message=(
                    "Local skill plan validation sidecar is not a JSON object."
                ),
            )
        ]

    raw_findings = payload.get("findings")
    findings: list[ServiceDeskWorkflowValidationFinding] = []

    if isinstance(raw_findings, list):
        for item in raw_findings:
            if not isinstance(item, dict):
                continue
            findings.append(
                ServiceDeskWorkflowValidationFinding(
                    severity=str(item.get("severity", "")),
                    code=str(item.get("code", "")),
                    message=str(item.get("message", "")),
                )
            )

    has_errors_raw = payload.get("has_errors")
    if isinstance(has_errors_raw, bool):
        has_errors = has_errors_raw
    else:
        has_errors = any(finding.severity == "error" for finding in findings)

    return has_errors, findings


_SKILL_MATCH_KEYS = ("skill_match", "Skill match")
_CAPABILITY_CLASSIFICATION_KEYS = (
    "capability_classification",
    "Capability classification",
)


def _read_skill_plan_json_summary(path: Path) -> ServiceDeskSkillPlanSummary:
    """Read `latest_skill_plan.json` for display only. Never raises.

    Missing → exists/readable false. Malformed/unreadable → exists true,
    readable false, error populated. This summary is display-only and is
    not used to decide workflow stage or next action in this PR.
    """
    if not path.exists():
        return ServiceDeskSkillPlanSummary()

    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 - state read must not raise
        return ServiceDeskSkillPlanSummary(
            exists=True,
            readable=False,
            error=f"Local skill plan JSON sidecar could not be read: {exc}",
        )

    if not isinstance(payload, dict):
        return ServiceDeskSkillPlanSummary(
            exists=True,
            readable=False,
            error="Local skill plan JSON sidecar is not a JSON object.",
        )

    schema_version_raw = payload.get("schema_version")
    schema_version = (
        schema_version_raw if isinstance(schema_version_raw, int) else None
    )

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    skill_match = _lookup_metadata_value(metadata, _SKILL_MATCH_KEYS)
    capability_classification = _lookup_metadata_value(
        metadata, _CAPABILITY_CLASSIFICATION_KEYS
    )

    handoff = payload.get("automation_handoff")
    if not isinstance(handoff, dict):
        handoff = {}

    return ServiceDeskSkillPlanSummary(
        exists=True,
        readable=True,
        schema_version=schema_version,
        skill_match=skill_match,
        capability_classification=capability_classification,
        ready_for_inspection=_optional_str_value(
            handoff.get("ready_for_inspection")
        ),
        ready_for_execution=_optional_str_value(
            handoff.get("ready_for_execution")
        ),
        suggested_inspector_tools=_string_list(
            handoff.get("suggested_inspector_tools")
        ),
        suggested_execute_tools=_string_list(
            handoff.get("suggested_execute_tools")
        ),
        error=None,
    )


def _lookup_metadata_value(
    metadata: dict, keys: tuple[str, ...]
) -> str | None:
    for key in keys:
        if key in metadata:
            return _optional_str_value(metadata[key])
    return None


def _optional_str_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                items.append(cleaned)
    return items


def _any_supported_inspector_output_exists(
    *,
    workspace: str,
    request_id: str,
) -> bool:
    inspector_dir = build_inspector_output_dir(
        workspace=workspace, request_id=request_id
    )

    if not inspector_dir.exists():
        return False

    for inspector_id in SUPPORTED_REPORT_INSPECTOR_IDS:
        candidate = build_inspector_result_path(
            workspace=workspace,
            request_id=request_id,
            inspector_id=inspector_id,
        )

        if candidate.exists():
            return True

    return False


def _decide_stage_and_next_action(
    *,
    context_exists: bool,
    skill_plan_exists: bool,
    validation_exists: bool,
    validation_has_errors: bool | None,
    validation_findings: list[ServiceDeskWorkflowValidationFinding],
    inspector_outputs_exist: bool,
    inspection_report_exists: bool,
    draft_note_exists: bool,
) -> tuple[
    ServiceDeskWorkflowStage,
    ServiceDeskWorkflowNextAction,
    bool,
    str | None,
]:
    if not context_exists:
        return (
            ServiceDeskWorkflowStage.MISSING_CONTEXT,
            ServiceDeskWorkflowNextAction.RUN_CONTEXT,
            False,
            None,
        )

    if not skill_plan_exists:
        return (
            ServiceDeskWorkflowStage.MISSING_SKILL_PLAN,
            ServiceDeskWorkflowNextAction.RUN_SKILL_PLAN,
            False,
            None,
        )

    # Skill plan exists. Honour validation sidecar if present.
    if not validation_exists:
        return (
            ServiceDeskWorkflowStage.UNKNOWN,
            ServiceDeskWorkflowNextAction.RUN_SKILL_PLAN,
            True,
            (
                "Skill plan validation sidecar is missing; regenerate "
                "the skill plan or validation state before inspection."
            ),
        )

    if validation_has_errors:
        # An unreadable validation sidecar is a state problem, not a
        # skill-plan-content problem. /sdp repair-skill-plan validates
        # the Markdown itself and can short-circuit without rewriting
        # the sidecar, which would loop /sdp work forever. Route the
        # caller to regenerate the skill plan / validation state.
        if any(
            finding.code == "validation_sidecar_unreadable"
            for finding in validation_findings
        ):
            return (
                ServiceDeskWorkflowStage.UNKNOWN,
                ServiceDeskWorkflowNextAction.RUN_SKILL_PLAN,
                True,
                (
                    "Skill plan validation sidecar is unreadable; "
                    "regenerate the skill plan or validation state "
                    "before inspection."
                ),
            )

        first_error = next(
            (
                finding
                for finding in validation_findings
                if finding.severity == "error"
            ),
            None,
        )

        if first_error is not None:
            blocker = (
                "Skill plan validation has errors: "
                f"[{first_error.code}] {first_error.message}"
            )
        else:
            blocker = "Skill plan validation has errors."

        return (
            ServiceDeskWorkflowStage.SKILL_PLAN_INVALID,
            ServiceDeskWorkflowNextAction.REPAIR_SKILL_PLAN,
            True,
            blocker,
        )

    if not inspector_outputs_exist:
        return (
            ServiceDeskWorkflowStage.READY_FOR_INSPECTION,
            ServiceDeskWorkflowNextAction.RUN_INSPECTION,
            False,
            None,
        )

    if not inspection_report_exists:
        return (
            ServiceDeskWorkflowStage.INSPECTION_REPORT_MISSING,
            ServiceDeskWorkflowNextAction.BUILD_INSPECTION_REPORT,
            False,
            None,
        )

    if not draft_note_exists:
        return (
            ServiceDeskWorkflowStage.DRAFT_NOTE_MISSING,
            ServiceDeskWorkflowNextAction.DRAFT_NOTE,
            False,
            None,
        )

    return (
        ServiceDeskWorkflowStage.READY_TO_SAVE_NOTE,
        ServiceDeskWorkflowNextAction.SAVE_NOTE,
        False,
        None,
    )


_NEXT_ACTION_TO_COMMAND_NAME: dict[ServiceDeskWorkflowNextAction, str] = {
    ServiceDeskWorkflowNextAction.RUN_CONTEXT: "context",
    ServiceDeskWorkflowNextAction.RUN_SKILL_PLAN: "skill-plan",
    ServiceDeskWorkflowNextAction.REPAIR_SKILL_PLAN: "repair-skill-plan",
    ServiceDeskWorkflowNextAction.RUN_INSPECTION: "inspect-skill",
    ServiceDeskWorkflowNextAction.BUILD_INSPECTION_REPORT: "inspection-report",
    ServiceDeskWorkflowNextAction.DRAFT_NOTE: "draft-note",
    ServiceDeskWorkflowNextAction.SAVE_NOTE: "save-note",
}


def suggested_next_command_for_next_action(
    *,
    next_action: ServiceDeskWorkflowNextAction,
    request_id: str,
) -> str | None:
    """Map a workflow next-action enum to a `/sdp <command> <id>` line.

    Returns None for actions that have no safe automatic command mapping
    (currently `review_draft_note` and `none`). The mapping never invents
    an action that the local state didn't already recommend.
    """
    command = _NEXT_ACTION_TO_COMMAND_NAME.get(next_action)

    if command is None:
        return None

    return f"/sdp {command} {request_id}"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _format_status_lines(
    *,
    request_id: str,
    context_exists: bool,
    skill_plan_exists: bool,
    validation_exists: bool,
    validation_has_errors: bool | None,
    validation_findings: list[ServiceDeskWorkflowValidationFinding],
    inspector_outputs_exist: bool,
    inspection_report_exists: bool,
    draft_note_exists: bool,
    skill_plan_summary: ServiceDeskSkillPlanSummary,
    stage: ServiceDeskWorkflowStage,
    next_action: ServiceDeskWorkflowNextAction,
    blocked: bool,
    blocker: str | None,
) -> list[str]:
    if validation_exists:
        finding_count = len(validation_findings)
        if validation_has_errors:
            validation_label = (
                f"yes (errors, {finding_count} finding(s))"
            )
        elif finding_count > 0:
            validation_label = (
                f"yes (warnings, {finding_count} finding(s))"
            )
        else:
            validation_label = (
                f"yes (clean, {finding_count} finding(s))"
            )
    else:
        validation_label = "no"

    lines = [
        f"ServiceDesk workflow state for request {request_id}",
        f"- context: {_yes_no(context_exists)}",
        f"- skill plan: {_yes_no(skill_plan_exists)}",
        f"- skill plan validation: {validation_label}",
        f"- inspector outputs: {_yes_no(inspector_outputs_exist)}",
        f"- inspection report: {_yes_no(inspection_report_exists)}",
        f"- draft note: {_yes_no(draft_note_exists)}",
    ]

    lines.extend(_format_skill_plan_summary_lines(skill_plan_summary))

    lines.extend(
        [
            f"- stage: {stage.value}",
            f"- next action: {next_action.value}",
            f"- blocked: {_yes_no(blocked)}",
        ]
    )

    if blocker:
        lines.append(f"- blocker: {blocker}")

    return lines


def _format_skill_plan_summary_lines(
    summary: ServiceDeskSkillPlanSummary,
) -> list[str]:
    if not summary.exists:
        return ["- structured skill plan: no"]

    if not summary.readable:
        message = summary.error or "unknown error"
        return [f"- structured skill plan: yes (unreadable: {message})"]

    return [
        "- structured skill plan: yes",
        f"- skill match: {summary.skill_match or 'unknown'}",
        (
            "- capability classification: "
            f"{summary.capability_classification or 'unknown'}"
        ),
        (
            "- ready for inspection: "
            f"{summary.ready_for_inspection or 'unknown'}"
        ),
        (
            "- ready for execution: "
            f"{summary.ready_for_execution or 'unknown'}"
        ),
        (
            "- suggested inspectors: "
            f"{_format_tool_list(summary.suggested_inspector_tools)}"
        ),
        (
            "- suggested execute tools: "
            f"{_format_tool_list(summary.suggested_execute_tools)}"
        ),
    ]


def _format_tool_list(tools: list[str]) -> str:
    if not tools:
        return "none"
    return ", ".join(tools)
