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
    build_servicedesk_latest_skill_plan_path,
    build_servicedesk_latest_skill_plan_validation_path,
)
from executors.exchange import (
    plan_exchange_grant_full_access_preview_from_skill_plan,
)
from inspectors.inspection_report import (
    SUPPORTED_REPORT_INSPECTOR_IDS,
    build_servicedesk_inspection_report_path,
)
from inspectors.storage import (
    build_inspector_output_dir,
    build_inspector_result_path,
)
from servicedesk_draft_note_validation import (
    DraftNoteValidationFinding,
    draft_note_findings_have_errors,
    validate_servicedesk_draft_note_file,
)
from servicedesk_skill_plan import (
    SKILL_PLAN_JSON_SCHEMA_VERSION,
    load_skill_plan_json_sidecar,
)


class ServiceDeskWorkflowStage(StrEnum):
    MISSING_CONTEXT = "missing_context"
    MISSING_SKILL_PLAN = "missing_skill_plan"
    SKILL_PLAN_SIDECARS_STALE = "skill_plan_sidecars_stale"
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
    REFRESH_SKILL_PLAN_SIDECARS = "refresh_skill_plan_sidecars"
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

    Display-only. Workflow stage/next-action decisions use existing
    artifact checks and `latest_skill_plan_validation.json`; this
    summary never blocks the workflow.

    `stale` is True when the JSON sidecar is older than
    `latest_skill_plan.md` (the loader's freshness check). Stale
    sidecars are surfaced as `readable=False` so display callers do
    not present possibly outdated structured fields as authoritative.
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
    stale: bool = False


@dataclass(frozen=True)
class ServiceDeskExecutorPreviewSummary:
    """Display-only summary of the preview-only executor planner.

    Built from a fresh, readable structured skill plan via the
    executor planner (`plan_exchange_grant_full_access_preview_from_skill_plan`).
    Never executes the executor and never affects workflow stage or
    next_action. Empty for unsupported skills, stale/unreadable
    sidecars, or when no plan exists.
    """

    applicable: bool = False
    preview_available: bool = False
    executor_id: str | None = None
    title: str | None = None
    summary: str | None = None
    missing_inputs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unsupported_reason: str | None = None


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
    inspection_report_stale: bool = False
    draft_note_exists: bool = False
    draft_note_stale: bool = False
    draft_note_validation_findings: list[DraftNoteValidationFinding] = field(
        default_factory=list
    )
    skill_plan_summary: ServiceDeskSkillPlanSummary = field(
        default_factory=ServiceDeskSkillPlanSummary
    )
    executor_preview_summary: ServiceDeskExecutorPreviewSummary = field(
        default_factory=ServiceDeskExecutorPreviewSummary
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
        stale_finding = _validation_sidecar_stale_finding(
            validation_path=validation_path,
            skill_plan_path=skill_plan_path,
        )
        if stale_finding is not None:
            validation_has_errors = True
            validation_findings = [stale_finding]
        else:
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

    inspection_report_stale = (
        inspection_report_exists
        and _inspection_report_is_stale_vs_inspector_outputs(
            workspace=workspace,
            request_id=request_id,
            inspection_report_path=inspection_report_path,
        )
    )
    draft_note_stale = (
        draft_note_exists
        and _draft_note_is_stale_vs_inspection_report(
            inspection_report_path=inspection_report_path,
            draft_note_path=draft_note_path,
        )
    )

    # Run local draft-note validation only when the draft exists and
    # is fresh; missing/stale drafts already route to DRAFT_NOTE so
    # validation findings would be redundant noise. Validation is
    # filesystem-only and never raises.
    if draft_note_exists and not draft_note_stale:
        draft_note_validation_findings = (
            validate_servicedesk_draft_note_file(
                workspace=workspace, request_id=request_id
            )
        )
    else:
        draft_note_validation_findings = []

    sidecar_load_result = load_skill_plan_json_sidecar(
        workspace=workspace, request_id=request_id
    )
    skill_plan_summary = _build_skill_plan_summary_from_loader_result(
        sidecar_load_result
    )
    executor_preview_summary = _build_executor_preview_summary_from_loader_result(
        sidecar_load_result, request_id=request_id
    )

    stage, next_action, blocked, blocker = _decide_stage_and_next_action(
        context_exists=context_exists,
        skill_plan_exists=skill_plan_exists,
        validation_exists=validation_exists,
        validation_has_errors=validation_has_errors,
        validation_findings=validation_findings,
        inspector_outputs_exist=inspector_outputs_exist,
        inspection_report_exists=inspection_report_exists,
        inspection_report_stale=inspection_report_stale,
        draft_note_exists=draft_note_exists,
        draft_note_stale=draft_note_stale,
        draft_note_validation_findings=draft_note_validation_findings,
        skill_plan_summary=skill_plan_summary,
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
        inspection_report_stale=inspection_report_stale,
        draft_note_exists=draft_note_exists,
        draft_note_stale=draft_note_stale,
        draft_note_validation_findings=draft_note_validation_findings,
        skill_plan_summary=skill_plan_summary,
        executor_preview_summary=executor_preview_summary,
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
        inspection_report_stale=inspection_report_stale,
        draft_note_exists=draft_note_exists,
        draft_note_stale=draft_note_stale,
        draft_note_validation_findings=draft_note_validation_findings,
        skill_plan_summary=skill_plan_summary,
        executor_preview_summary=executor_preview_summary,
        stage=stage,
        next_action=next_action,
        blocked=blocked,
        blocker=blocker,
        status_lines=status_lines,
    )


# ---- Private helpers ---------------------------------------------------


def _validation_sidecar_stale_finding(
    *,
    validation_path: Path,
    skill_plan_path: Path,
) -> ServiceDeskWorkflowValidationFinding | None:
    """Return a synthetic stale finding when the validation sidecar is
    older than `latest_skill_plan.md`, otherwise None. Never raises.

    Conservative: only flags stale when both files exist and the mtime
    comparison can be performed. If the freshness check itself fails
    (e.g. transient FS error), returns a synthetic stale finding so the
    caller blocks rather than trusting validation that may not match
    the current Markdown plan. Workflow state never modifies the
    validation sidecar on disk; the user must regenerate it via
    `/sdp skill-plan` or `/sdp repair-skill-plan`.
    """
    if not skill_plan_path.exists():
        return None

    try:
        validation_mtime = validation_path.stat().st_mtime
        skill_plan_mtime = skill_plan_path.stat().st_mtime
    except Exception as exc:  # noqa: BLE001 - state read must not raise
        return ServiceDeskWorkflowValidationFinding(
            severity="error",
            code="validation_sidecar_stale",
            message=(
                "Skill plan validation sidecar freshness check failed: "
                f"{exc}"
            ),
        )

    if validation_mtime < skill_plan_mtime:
        return ServiceDeskWorkflowValidationFinding(
            severity="error",
            code="validation_sidecar_stale",
            message=(
                "Skill plan validation sidecar is older than "
                "latest_skill_plan.md."
            ),
        )

    return None


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


def _build_skill_plan_summary_from_loader_result(
    result,
) -> ServiceDeskSkillPlanSummary:
    """Render a `SkillPlanJsonLoadResult` into a display summary.

    Never raises. The loader handles missing / unreadable /
    unsupported-schema / stale sidecars uniformly; this module's only
    responsibilities are to render the loader result into the display
    shape and to keep `metadata` key lookup tolerant for the labels
    the parser currently emits ("Skill match", "Capability
    classification") and possible future snake_case payloads.

    Stale sidecars are surfaced as `exists=True, readable=False,
    stale=True` with the loader's `error` string so the workflow
    status display does not present possibly outdated structured
    fields as authoritative.
    """
    if not result.exists:
        return ServiceDeskSkillPlanSummary()

    if not result.readable or result.plan is None:
        return ServiceDeskSkillPlanSummary(
            exists=True,
            readable=False,
            stale=result.stale,
            error=result.error,
        )

    plan = result.plan
    metadata = plan.metadata if isinstance(plan.metadata, dict) else {}
    handoff = plan.automation_handoff

    return ServiceDeskSkillPlanSummary(
        exists=True,
        readable=True,
        schema_version=SKILL_PLAN_JSON_SCHEMA_VERSION,
        skill_match=_lookup_parsed_metadata_value(metadata, _SKILL_MATCH_KEYS),
        capability_classification=_lookup_parsed_metadata_value(
            metadata, _CAPABILITY_CLASSIFICATION_KEYS
        ),
        ready_for_inspection=_clean_optional_str(handoff.ready_for_inspection),
        ready_for_execution=_clean_optional_str(handoff.ready_for_execution),
        suggested_inspector_tools=_clean_string_list(
            handoff.suggested_inspector_tools
        ),
        suggested_execute_tools=_clean_string_list(
            handoff.suggested_execute_tools
        ),
        error=None,
        stale=False,
    )


def _build_executor_preview_summary_from_loader_result(
    result,
    *,
    request_id: str,
) -> ServiceDeskExecutorPreviewSummary:
    """Display-only executor preview summary, built from a fresh and
    readable structured skill plan.

    Never executes the executor and never affects workflow stage or
    next_action. Returns an empty (`applicable=False`) summary when
    the sidecar is missing, stale, or unreadable. The planner itself
    is pure/local and never raises; this wrapper additionally swallows
    unexpected errors so workflow status display stays robust.
    """
    if not result.readable or result.plan is None:
        return ServiceDeskExecutorPreviewSummary()

    try:
        planning = (
            plan_exchange_grant_full_access_preview_from_skill_plan(
                result.plan, request_id=request_id
            )
        )
    except Exception as exc:  # noqa: BLE001 - state read must not raise
        return ServiceDeskExecutorPreviewSummary(
            applicable=False,
            unsupported_reason=(
                f"Executor preview planner failed: {exc}"
            ),
        )

    if not planning.applicable:
        return ServiceDeskExecutorPreviewSummary(
            applicable=False,
            unsupported_reason=planning.unsupported_reason,
        )

    if planning.preview is None:
        return ServiceDeskExecutorPreviewSummary(
            applicable=True,
            preview_available=False,
            missing_inputs=list(planning.missing_inputs),
            warnings=list(planning.warnings),
        )

    return ServiceDeskExecutorPreviewSummary(
        applicable=True,
        preview_available=True,
        executor_id=planning.preview.executor_id,
        title=planning.preview.title,
        summary=planning.preview.summary,
        warnings=list(planning.preview.warnings),
    )


def _lookup_parsed_metadata_value(
    metadata: dict[str, str], keys: tuple[str, ...]
) -> str | None:
    for key in keys:
        raw = metadata.get(key)
        if not isinstance(raw, str):
            continue
        cleaned = raw.strip()
        if cleaned:
            return cleaned
    return None


def _clean_optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _clean_string_list(value: list[str]) -> list[str]:
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


def _inspection_report_is_stale_vs_inspector_outputs(
    *,
    workspace: str,
    request_id: str,
    inspection_report_path: Path,
) -> bool:
    """Return True when any supported inspector output JSON has a
    newer mtime than the inspection report. Conservative: if the stat
    check itself fails for the report or any candidate inspector
    output, treat the report as stale so the workflow recommends
    rebuilding rather than trusting a possibly-outdated render.
    """
    try:
        report_mtime = inspection_report_path.stat().st_mtime
    except Exception:  # noqa: BLE001 - state read must not raise
        return True

    for inspector_id in SUPPORTED_REPORT_INSPECTOR_IDS:
        candidate = build_inspector_result_path(
            workspace=workspace,
            request_id=request_id,
            inspector_id=inspector_id,
        )
        if not candidate.exists():
            continue
        try:
            inspector_mtime = candidate.stat().st_mtime
        except Exception:  # noqa: BLE001 - state read must not raise
            return True
        if inspector_mtime > report_mtime:
            return True

    return False


def _draft_note_is_stale_vs_inspection_report(
    *,
    inspection_report_path: Path,
    draft_note_path: Path,
) -> bool:
    """Return True when the inspection report is newer than the draft
    note. The draft note is rendered from the inspection report, so a
    newer report means the draft no longer reflects the underlying
    facts. Conservative: stat failure on either side flags the draft
    as stale.
    """
    if not inspection_report_path.exists():
        return False
    try:
        report_mtime = inspection_report_path.stat().st_mtime
        draft_mtime = draft_note_path.stat().st_mtime
    except Exception:  # noqa: BLE001 - state read must not raise
        return True
    return report_mtime > draft_mtime


def _decide_stage_and_next_action(
    *,
    context_exists: bool,
    skill_plan_exists: bool,
    validation_exists: bool,
    validation_has_errors: bool | None,
    validation_findings: list[ServiceDeskWorkflowValidationFinding],
    inspector_outputs_exist: bool,
    inspection_report_exists: bool,
    inspection_report_stale: bool,
    draft_note_exists: bool,
    draft_note_stale: bool,
    draft_note_validation_findings: list[DraftNoteValidationFinding],
    skill_plan_summary: ServiceDeskSkillPlanSummary,
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

    # Skill plan exists. The validation sidecar may need refresh if
    # missing/stale/unreadable. We refresh from the existing Markdown
    # rather than re-prompting the model so manual edits to
    # latest_skill_plan.md are preserved.
    if not validation_exists:
        return (
            ServiceDeskWorkflowStage.SKILL_PLAN_SIDECARS_STALE,
            ServiceDeskWorkflowNextAction.REFRESH_SKILL_PLAN_SIDECARS,
            True,
            (
                "Skill plan validation sidecar is missing; refresh "
                "sidecars from latest_skill_plan.md before inspection."
            ),
        )

    if validation_has_errors:
        # An unreadable validation sidecar is a state problem, not a
        # skill-plan-content problem. Refresh the sidecars from the
        # existing Markdown so the user's edits are preserved.
        if any(
            finding.code == "validation_sidecar_unreadable"
            for finding in validation_findings
        ):
            return (
                ServiceDeskWorkflowStage.SKILL_PLAN_SIDECARS_STALE,
                ServiceDeskWorkflowNextAction.REFRESH_SKILL_PLAN_SIDECARS,
                True,
                (
                    "Skill plan validation sidecar is unreadable; "
                    "refresh sidecars from latest_skill_plan.md "
                    "before inspection."
                ),
            )

        # A stale validation sidecar describes an older Markdown plan,
        # so its has_errors / findings cannot be trusted to reflect the
        # current `latest_skill_plan.md`. Refresh the sidecars from the
        # existing Markdown.
        if any(
            finding.code == "validation_sidecar_stale"
            for finding in validation_findings
        ):
            return (
                ServiceDeskWorkflowStage.SKILL_PLAN_SIDECARS_STALE,
                ServiceDeskWorkflowNextAction.REFRESH_SKILL_PLAN_SIDECARS,
                True,
                (
                    "Skill plan validation sidecar is older than "
                    "latest_skill_plan.md; refresh sidecars from "
                    "latest_skill_plan.md before inspection."
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

    # Validation sidecar is fresh and clean (errors-or-warnings did not
    # block above). The structured skill-plan JSON sidecar must also be
    # present, fresh, and readable so /sdp status / /sdp work / and
    # downstream consumers see consistent structured data. Missing,
    # stale, or unreadable → refresh locally from the existing
    # latest_skill_plan.md.
    if not skill_plan_summary.exists:
        return (
            ServiceDeskWorkflowStage.SKILL_PLAN_SIDECARS_STALE,
            ServiceDeskWorkflowNextAction.REFRESH_SKILL_PLAN_SIDECARS,
            True,
            (
                "Structured skill plan sidecar is missing; refresh "
                "sidecars from latest_skill_plan.md before inspection."
            ),
        )

    if not skill_plan_summary.readable:
        if skill_plan_summary.stale:
            blocker = (
                "Structured skill plan sidecar is older than "
                "latest_skill_plan.md; refresh sidecars from "
                "latest_skill_plan.md before inspection."
            )
        else:
            blocker = (
                "Structured skill plan sidecar is unreadable; refresh "
                "sidecars from latest_skill_plan.md before inspection."
            )
        return (
            ServiceDeskWorkflowStage.SKILL_PLAN_SIDECARS_STALE,
            ServiceDeskWorkflowNextAction.REFRESH_SKILL_PLAN_SIDECARS,
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

    # Inspection report exists but is older than at least one inspector
    # output JSON. Rebuild the report so /sdp draft-note sees current
    # facts. Re-run is local-only and does not contact AD/Exchange.
    if inspection_report_stale:
        return (
            ServiceDeskWorkflowStage.INSPECTION_REPORT_MISSING,
            ServiceDeskWorkflowNextAction.BUILD_INSPECTION_REPORT,
            False,
            (
                "Inspection report is stale: at least one inspector "
                "output is newer than inspection_report.md. Rebuild "
                "the report before drafting the note."
            ),
        )

    if not draft_note_exists:
        return (
            ServiceDeskWorkflowStage.DRAFT_NOTE_MISSING,
            ServiceDeskWorkflowNextAction.DRAFT_NOTE,
            False,
            None,
        )

    # Draft note exists but the inspection report is newer, so the
    # draft no longer reflects the underlying facts. Regenerate the
    # draft locally before recommending /sdp save-note.
    if draft_note_stale:
        return (
            ServiceDeskWorkflowStage.DRAFT_NOTE_MISSING,
            ServiceDeskWorkflowNextAction.DRAFT_NOTE,
            False,
            (
                "Draft note is stale: inspection_report.md is newer "
                "than draft_note.md. Regenerate the draft before "
                "saving the note."
            ),
        )

    # Fresh draft note that fails local validation (placeholder text,
    # missing/empty body, forbidden write claim, …) must not be
    # recommended for save. Route back to DRAFT_NOTE so /sdp work
    # regenerates the draft. /sdp save-note's own validation gate
    # remains unchanged and is the final write-time check.
    if draft_note_findings_have_errors(draft_note_validation_findings):
        first_error = next(
            (
                finding
                for finding in draft_note_validation_findings
                if finding.severity == "error"
            ),
            None,
        )
        if first_error is not None:
            blocker = (
                "Draft note has validation errors: "
                f"[{first_error.code}] {first_error.message} "
                "Regenerate the draft before saving the note."
            )
        else:
            blocker = (
                "Draft note has validation errors. Regenerate the "
                "draft before saving the note."
            )
        return (
            ServiceDeskWorkflowStage.DRAFT_NOTE_MISSING,
            ServiceDeskWorkflowNextAction.DRAFT_NOTE,
            False,
            blocker,
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
    # Sidecar refresh has no separate user-facing command; it runs as
    # an internal step inside `/sdp work <id>`. Mapping it back to
    # `/sdp work <id>` lets `/sdp status` suggest the right command
    # without inventing a public refresh command.
    ServiceDeskWorkflowNextAction.REFRESH_SKILL_PLAN_SIDECARS: "work",
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


def _freshness_label(exists: bool, stale: bool) -> str:
    if not exists:
        return "no"
    if stale:
        return "yes (stale)"
    return "yes"


def _draft_note_validation_label(
    draft_note_exists: bool,
    draft_note_stale: bool,
    findings: list[DraftNoteValidationFinding],
) -> str:
    """Concise label for the draft-note validation line.

    Skipped when there is no fresh draft note to validate (the
    earlier missing/stale draft routing already explains the next
    step). Otherwise reports clean / errors / warnings + finding
    count, mirroring the skill-plan validation label style.
    """
    if not draft_note_exists or draft_note_stale:
        return "skipped (no fresh draft note)"

    finding_count = len(findings)
    if finding_count == 0:
        return "no issues found"

    error_count = sum(1 for f in findings if f.severity == "error")
    if error_count > 0:
        return f"errors, {finding_count} finding(s)"
    return f"warnings, {finding_count} finding(s)"


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
    inspection_report_stale: bool,
    draft_note_exists: bool,
    draft_note_stale: bool,
    draft_note_validation_findings: list[DraftNoteValidationFinding],
    skill_plan_summary: ServiceDeskSkillPlanSummary,
    executor_preview_summary: ServiceDeskExecutorPreviewSummary,
    stage: ServiceDeskWorkflowStage,
    next_action: ServiceDeskWorkflowNextAction,
    blocked: bool,
    blocker: str | None,
) -> list[str]:
    if validation_exists:
        finding_count = len(validation_findings)
        is_stale = any(
            finding.code == "validation_sidecar_stale"
            for finding in validation_findings
        )
        if is_stale:
            validation_label = (
                f"yes (stale, {finding_count} finding(s))"
            )
        elif validation_has_errors:
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
        f"- inspection report: {_freshness_label(inspection_report_exists, inspection_report_stale)}",
        f"- draft note: {_freshness_label(draft_note_exists, draft_note_stale)}",
        (
            "- draft note validation: "
            f"{_draft_note_validation_label(draft_note_exists, draft_note_stale, draft_note_validation_findings)}"
        ),
    ]

    lines.extend(_format_skill_plan_summary_lines(skill_plan_summary))
    lines.extend(
        _format_executor_preview_summary_lines(executor_preview_summary)
    )

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
        label = "stale" if summary.stale else "unreadable"
        return [f"- structured skill plan: yes ({label}: {message})"]

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


def _format_executor_preview_summary_lines(
    summary: ServiceDeskExecutorPreviewSummary,
) -> list[str]:
    """Render the executor preview summary as concise status lines.

    Display-only. Does not execute, does not contact Exchange, does
    not call ServiceDesk. Single `- executor preview: none` line for
    the unsupported / not-applicable case keeps `/sdp status` quiet.
    """
    if not summary.applicable:
        return ["- executor preview: none"]

    if not summary.preview_available:
        return [
            "- executor preview: missing inputs",
            (
                "- executor missing inputs: "
                f"{_format_missing_inputs(summary.missing_inputs)}"
            ),
        ]

    lines = [
        "- executor preview: available",
        f"- executor: {summary.executor_id or 'unknown'}",
        f"- executor preview title: {summary.title or 'unknown'}",
        f"- executor preview summary: {summary.summary or 'unknown'}",
        "- executor requires approval: yes",
    ]
    for warning in summary.warnings:
        lines.append(f"- executor warning: {warning}")
    return lines


def _format_missing_inputs(missing_inputs: list[str]) -> str:
    if not missing_inputs:
        return "none"
    return ", ".join(missing_inputs)
