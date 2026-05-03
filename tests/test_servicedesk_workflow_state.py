import json
from pathlib import Path

from draft_exports import (
    build_servicedesk_draft_note_path,
    build_servicedesk_latest_context_path,
    build_servicedesk_latest_skill_plan_json_path,
    build_servicedesk_latest_skill_plan_path,
    build_servicedesk_latest_skill_plan_validation_path,
)
from inspectors.inspection_report import build_servicedesk_inspection_report_path
from inspectors.storage import build_inspector_result_path
from servicedesk_workflow_state import (
    ServiceDeskWorkflowNextAction,
    ServiceDeskWorkflowStage,
    read_servicedesk_workflow_state,
)

REQUEST_ID = "55948"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_context(workspace: Path) -> None:
    _write(
        build_servicedesk_latest_context_path(
            workspace=str(workspace), request_id=REQUEST_ID
        ),
        "# ServiceDesk request context\n",
    )


def _seed_skill_plan(workspace: Path) -> None:
    _write(
        build_servicedesk_latest_skill_plan_path(
            workspace=str(workspace), request_id=REQUEST_ID
        ),
        "# ServiceDesk skill plan\n",
    )


def _seed_validation(workspace: Path, payload: dict) -> None:
    _write(
        build_servicedesk_latest_skill_plan_validation_path(
            workspace=str(workspace), request_id=REQUEST_ID
        ),
        json.dumps(payload, indent=2) + "\n",
    )


def _seed_clean_validation(workspace: Path) -> None:
    _seed_validation(workspace, {"has_errors": False, "findings": []})


def _seed_skill_plan_json(workspace: Path, payload: dict) -> None:
    _write(
        build_servicedesk_latest_skill_plan_json_path(
            workspace=str(workspace), request_id=REQUEST_ID
        ),
        json.dumps(payload, indent=2) + "\n",
    )


def _seed_skill_plan_json_raw(workspace: Path, raw: str) -> None:
    _write(
        build_servicedesk_latest_skill_plan_json_path(
            workspace=str(workspace), request_id=REQUEST_ID
        ),
        raw,
    )


_CLEAN_STRUCTURED_PAYLOAD = {
    "schema_version": 1,
    "request_id": REQUEST_ID,
    "metadata": {
        "Skill match": (
            "active_directory.user.update_profile_attributes"
        ),
        "Capability classification": "draft_only_manual_now",
    },
    "extracted_inputs": [],
    "missing_information_needed_now": [],
    "current_blocker": None,
    "automation_handoff": {
        "ready_for_inspection": "yes",
        "ready_for_execution": "no",
        "suggested_inspector_tools": ["active_directory.user.inspect"],
        "suggested_execute_tools": [],
        "automation_blocker": None,
    },
}


def _seed_clean_skill_plan_json(workspace: Path) -> None:
    _seed_skill_plan_json(workspace, _CLEAN_STRUCTURED_PAYLOAD)


def _seed_error_validation(workspace: Path) -> None:
    _seed_validation(
        workspace,
        {
            "has_errors": True,
            "findings": [
                {
                    "severity": "error",
                    "code": "ready_for_execution_must_be_no",
                    "message": (
                        "Automation handoff `Ready for execution` must be "
                        "`no`; got `yes`."
                    ),
                }
            ],
        },
    )


def _seed_inspector_output(workspace: Path) -> None:
    _write(
        build_inspector_result_path(
            workspace=str(workspace),
            request_id=REQUEST_ID,
            inspector_id="active_directory.user.inspect",
        ),
        json.dumps(
            {
                "inspector": "active_directory.user.inspect",
                "status": "ok",
                "facts": [],
            }
        ),
    )


def _seed_inspection_report(workspace: Path) -> None:
    _write(
        build_servicedesk_inspection_report_path(
            workspace=str(workspace), request_id=REQUEST_ID
        ),
        "# Inspection report for ServiceDesk request 55948\n",
    )


_VALID_DRAFT_NOTE = """\
# ServiceDesk internal note draft

## Note body

Read-only inspection summary for the request.
"""


def _seed_draft_note(workspace: Path) -> None:
    _write(
        build_servicedesk_draft_note_path(
            workspace=str(workspace), request_id=REQUEST_ID
        ),
        _VALID_DRAFT_NOTE,
    )


def _seed_draft_note_with_text(workspace: Path, text: str) -> None:
    _write(
        build_servicedesk_draft_note_path(
            workspace=str(workspace), request_id=REQUEST_ID
        ),
        text,
    )


# --------------------- Stage progression --------------------------------


def test_no_artifacts_returns_missing_context_stage(tmp_path):
    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.context_exists is False
    assert state.skill_plan_exists is False
    assert state.validation_exists is False
    assert state.validation_has_errors is None
    assert state.validation_findings == []
    assert state.inspector_outputs_exist is False
    assert state.inspection_report_exists is False
    assert state.draft_note_exists is False
    assert state.stage == ServiceDeskWorkflowStage.MISSING_CONTEXT
    assert state.next_action == ServiceDeskWorkflowNextAction.RUN_CONTEXT
    assert state.blocked is False
    assert state.blocker is None
    assert any(
        line.startswith("ServiceDesk workflow state for request ")
        for line in state.status_lines
    )


def test_context_only_recommends_run_skill_plan(tmp_path):
    _seed_context(tmp_path)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.context_exists is True
    assert state.skill_plan_exists is False
    assert state.stage == ServiceDeskWorkflowStage.MISSING_SKILL_PLAN
    assert state.next_action == ServiceDeskWorkflowNextAction.RUN_SKILL_PLAN
    assert state.blocked is False


def test_validation_with_errors_blocks_and_recommends_repair(tmp_path):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_error_validation(tmp_path)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.validation_exists is True
    assert state.validation_has_errors is True
    assert state.blocked is True
    assert state.stage == ServiceDeskWorkflowStage.SKILL_PLAN_INVALID
    assert state.next_action == ServiceDeskWorkflowNextAction.REPAIR_SKILL_PLAN
    assert state.blocker is not None
    assert "Skill plan validation has errors" in state.blocker
    assert "ready_for_execution_must_be_no" in state.blocker

    # Validation findings preserve severity/code/message.
    assert len(state.validation_findings) == 1
    finding = state.validation_findings[0]
    assert finding.severity == "error"
    assert finding.code == "ready_for_execution_must_be_no"
    assert "Ready for execution" in finding.message


def test_clean_validation_without_inspector_outputs_recommends_inspection(
    tmp_path,
):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_clean_skill_plan_json(tmp_path)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.validation_exists is True
    assert state.validation_has_errors is False
    assert state.inspector_outputs_exist is False
    assert state.stage == ServiceDeskWorkflowStage.READY_FOR_INSPECTION
    assert state.next_action == ServiceDeskWorkflowNextAction.RUN_INSPECTION
    assert state.blocked is False


def test_inspector_outputs_without_report_recommends_build_report(tmp_path):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_clean_skill_plan_json(tmp_path)
    _seed_inspector_output(tmp_path)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.inspector_outputs_exist is True
    assert state.inspection_report_exists is False
    assert state.stage == ServiceDeskWorkflowStage.INSPECTION_REPORT_MISSING
    assert state.next_action == (
        ServiceDeskWorkflowNextAction.BUILD_INSPECTION_REPORT
    )
    assert state.blocked is False


def test_inspection_report_without_draft_note_recommends_draft_note(tmp_path):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_clean_skill_plan_json(tmp_path)
    _seed_inspector_output(tmp_path)
    _seed_inspection_report(tmp_path)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.inspection_report_exists is True
    assert state.draft_note_exists is False
    assert state.stage == ServiceDeskWorkflowStage.DRAFT_NOTE_MISSING
    assert state.next_action == ServiceDeskWorkflowNextAction.DRAFT_NOTE
    assert state.blocked is False


def test_draft_note_present_recommends_save_note(tmp_path):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_clean_skill_plan_json(tmp_path)
    _seed_inspector_output(tmp_path)
    _seed_inspection_report(tmp_path)
    _seed_draft_note(tmp_path)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.draft_note_exists is True
    assert state.stage in {
        ServiceDeskWorkflowStage.READY_TO_SAVE_NOTE,
        ServiceDeskWorkflowStage.READY_FOR_REVIEW,
    }
    assert state.next_action in {
        ServiceDeskWorkflowNextAction.SAVE_NOTE,
        ServiceDeskWorkflowNextAction.REVIEW_DRAFT_NOTE,
    }
    assert state.blocked is False


# --------------------- Sidecar robustness -------------------------------


def test_malformed_validation_sidecar_blocks_without_raising(tmp_path):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _write(
        build_servicedesk_latest_skill_plan_validation_path(
            workspace=str(tmp_path), request_id=REQUEST_ID
        ),
        "{ this is not valid json",
    )

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.validation_exists is True
    assert state.validation_has_errors is True
    assert state.blocked is True

    codes = {finding.code for finding in state.validation_findings}
    assert "validation_sidecar_unreadable" in codes

    # Unreadable sidecars must NOT route to repair-skill-plan, because
    # /sdp repair-skill-plan validates the Markdown itself and can
    # short-circuit without rewriting the sidecar — that would loop
    # /sdp work forever. Refresh sidecars from the existing
    # latest_skill_plan.md so manual edits are preserved.
    assert state.stage == ServiceDeskWorkflowStage.SKILL_PLAN_SIDECARS_STALE
    assert state.next_action == (
        ServiceDeskWorkflowNextAction.REFRESH_SKILL_PLAN_SIDECARS
    )
    assert state.blocker is not None
    assert "Skill plan validation sidecar is unreadable" in state.blocker


def test_validation_sidecar_with_non_object_payload_is_treated_as_unreadable(
    tmp_path,
):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _write(
        build_servicedesk_latest_skill_plan_validation_path(
            workspace=str(tmp_path), request_id=REQUEST_ID
        ),
        json.dumps(["not", "an", "object"]),
    )

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.validation_has_errors is True
    assert state.blocked is True
    codes = {finding.code for finding in state.validation_findings}
    assert "validation_sidecar_unreadable" in codes
    # Same routing as malformed JSON: refresh sidecars locally.
    assert state.stage == ServiceDeskWorkflowStage.SKILL_PLAN_SIDECARS_STALE
    assert state.next_action == (
        ServiceDeskWorkflowNextAction.REFRESH_SKILL_PLAN_SIDECARS
    )


def test_validation_sidecar_without_explicit_has_errors_infers_from_findings(
    tmp_path,
):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_validation(
        tmp_path,
        {
            "findings": [
                {
                    "severity": "warning",
                    "code": "clean_identifier_values",
                    "message": "Inspector-bound field looks dirty.",
                }
            ]
        },
    )
    _seed_clean_skill_plan_json(tmp_path)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    # Warning-only findings + missing has_errors flag should not block.
    assert state.validation_exists is True
    assert state.validation_has_errors is False
    assert state.blocked is False
    assert state.stage == ServiceDeskWorkflowStage.READY_FOR_INSPECTION
    assert state.next_action == ServiceDeskWorkflowNextAction.RUN_INSPECTION
    assert any(
        finding.code == "clean_identifier_values"
        for finding in state.validation_findings
    )


# --------------------- Status lines -------------------------------------


def test_status_lines_summarize_artifacts_and_decision(tmp_path):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_error_validation(tmp_path)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    joined = "\n".join(state.status_lines)
    assert (
        f"ServiceDesk workflow state for request {REQUEST_ID}" in joined
    )
    assert "- context: yes" in joined
    assert "- skill plan: yes" in joined
    assert "- skill plan validation: yes (errors" in joined
    assert "- stage: skill_plan_invalid" in joined
    assert "- next action: repair_skill_plan" in joined
    assert "- blocked: yes" in joined
    assert "- blocker:" in joined


# --------------------- Missing-validation safety gate -------------------


def test_skill_plan_without_validation_blocks_and_does_not_run_inspection(
    tmp_path,
):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    # Intentionally do not seed latest_skill_plan_validation.json.

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.context_exists is True
    assert state.skill_plan_exists is True
    assert state.validation_exists is False
    assert state.validation_has_errors is None
    assert state.blocked is True
    assert (
        state.next_action != ServiceDeskWorkflowNextAction.RUN_INSPECTION
    )
    # Skill plan Markdown exists; refresh sidecars locally rather than
    # re-prompting the model so manual edits are preserved.
    assert state.next_action == (
        ServiceDeskWorkflowNextAction.REFRESH_SKILL_PLAN_SIDECARS
    )
    assert state.stage == ServiceDeskWorkflowStage.SKILL_PLAN_SIDECARS_STALE
    assert state.blocker is not None
    assert "validation sidecar is missing" in state.blocker


# --------------------- Status label polish ------------------------------


def test_status_lines_label_warning_only_validation_as_warnings(tmp_path):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_validation(
        tmp_path,
        {
            "has_errors": False,
            "findings": [
                {
                    "severity": "warning",
                    "code": "clean_identifier_values",
                    "message": "Inspector-bound field looks dirty.",
                }
            ],
        },
    )

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    joined = "\n".join(state.status_lines)
    assert "- skill plan validation: yes (warnings, 1 finding(s))" in joined
    assert "yes (clean" not in joined


# --------------------- Suggested-command mapping ------------------------


def test_suggested_next_command_maps_known_actions():
    from servicedesk_workflow_state import (
        suggested_next_command_for_next_action,
    )

    request_id = "56050"

    cases = {
        ServiceDeskWorkflowNextAction.RUN_CONTEXT: f"/sdp context {request_id}",
        ServiceDeskWorkflowNextAction.RUN_SKILL_PLAN: (
            f"/sdp skill-plan {request_id}"
        ),
        ServiceDeskWorkflowNextAction.REPAIR_SKILL_PLAN: (
            f"/sdp repair-skill-plan {request_id}"
        ),
        ServiceDeskWorkflowNextAction.RUN_INSPECTION: (
            f"/sdp inspect-skill {request_id}"
        ),
        ServiceDeskWorkflowNextAction.BUILD_INSPECTION_REPORT: (
            f"/sdp inspection-report {request_id}"
        ),
        ServiceDeskWorkflowNextAction.DRAFT_NOTE: (
            f"/sdp draft-note {request_id}"
        ),
        ServiceDeskWorkflowNextAction.SAVE_NOTE: (
            f"/sdp save-note {request_id}"
        ),
    }

    for next_action, expected in cases.items():
        assert (
            suggested_next_command_for_next_action(
                next_action=next_action,
                request_id=request_id,
            )
            == expected
        )


def test_suggested_next_command_returns_none_for_review_only_or_none():
    from servicedesk_workflow_state import (
        suggested_next_command_for_next_action,
    )

    assert (
        suggested_next_command_for_next_action(
            next_action=ServiceDeskWorkflowNextAction.REVIEW_DRAFT_NOTE,
            request_id="56050",
        )
        is None
    )
    assert (
        suggested_next_command_for_next_action(
            next_action=ServiceDeskWorkflowNextAction.NONE,
            request_id="56050",
        )
        is None
    )


# --------------------- Structured skill-plan sidecar --------------------


def test_missing_structured_skill_plan_routes_to_refresh_sidecars(
    tmp_path,
):
    """With clean fresh validation but missing latest_skill_plan.json,
    workflow now routes to local sidecar refresh from the existing
    latest_skill_plan.md instead of recommending inspection. /sdp
    inspect-skill's Markdown fallback is unchanged — this only affects
    /sdp status / /sdp work recommendations.
    """
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    # Intentionally do not seed latest_skill_plan.json.

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.skill_plan_summary.exists is False
    assert state.skill_plan_summary.readable is False
    assert state.skill_plan_summary.error is None
    assert state.skill_plan_summary.suggested_inspector_tools == []
    assert state.skill_plan_summary.suggested_execute_tools == []

    joined = "\n".join(state.status_lines)
    # Missing structured sidecar still displays "no" (no error/stale
    # qualifier) — the blocker explains the refresh recommendation.
    assert "- structured skill plan: no" in joined

    assert state.stage == ServiceDeskWorkflowStage.SKILL_PLAN_SIDECARS_STALE
    assert state.next_action == (
        ServiceDeskWorkflowNextAction.REFRESH_SKILL_PLAN_SIDECARS
    )
    assert state.blocked is True
    assert state.blocker is not None
    assert "Structured skill plan sidecar is missing" in state.blocker
    assert "refresh sidecars from latest_skill_plan.md" in state.blocker


def test_readable_structured_skill_plan_populates_summary_and_status_lines(
    tmp_path,
):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_skill_plan_json(tmp_path, _CLEAN_STRUCTURED_PAYLOAD)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    summary = state.skill_plan_summary
    assert summary.exists is True
    assert summary.readable is True
    assert summary.error is None
    assert summary.schema_version == 1
    assert (
        summary.skill_match
        == "active_directory.user.update_profile_attributes"
    )
    assert summary.capability_classification == "draft_only_manual_now"
    assert summary.ready_for_inspection == "yes"
    assert summary.ready_for_execution == "no"
    assert summary.suggested_inspector_tools == [
        "active_directory.user.inspect"
    ]
    assert summary.suggested_execute_tools == []

    joined = "\n".join(state.status_lines)
    assert "- structured skill plan: yes" in joined
    assert (
        "- skill match: active_directory.user.update_profile_attributes"
        in joined
    )
    assert "- capability classification: draft_only_manual_now" in joined
    assert "- ready for inspection: yes" in joined
    assert "- ready for execution: no" in joined
    assert (
        "- suggested inspectors: active_directory.user.inspect" in joined
    )
    assert "- suggested execute tools: none" in joined


def test_structured_skill_plan_accepts_snake_case_metadata_keys(tmp_path):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_skill_plan_json(
        tmp_path,
        {
            "schema_version": 1,
            "request_id": REQUEST_ID,
            "metadata": {
                "skill_match": "active_directory.user.inspect_only",
                "capability_classification": "read_only_inspection_now",
            },
            "automation_handoff": {
                "ready_for_inspection": "yes",
                "ready_for_execution": "no",
                "suggested_inspector_tools": [
                    "active_directory.user.inspect"
                ],
                "suggested_execute_tools": [],
            },
        },
    )

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    summary = state.skill_plan_summary
    assert summary.skill_match == "active_directory.user.inspect_only"
    assert summary.capability_classification == "read_only_inspection_now"

    joined = "\n".join(state.status_lines)
    assert "- skill match: active_directory.user.inspect_only" in joined
    assert (
        "- capability classification: read_only_inspection_now" in joined
    )


def test_structured_skill_plan_unknown_when_metadata_missing(tmp_path):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_skill_plan_json(
        tmp_path,
        {
            "schema_version": 1,
            "request_id": REQUEST_ID,
            "metadata": {},
            "automation_handoff": {},
        },
    )

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    summary = state.skill_plan_summary
    assert summary.exists is True
    assert summary.readable is True
    assert summary.skill_match is None
    assert summary.capability_classification is None
    assert summary.ready_for_inspection is None
    assert summary.ready_for_execution is None

    joined = "\n".join(state.status_lines)
    assert "- skill match: unknown" in joined
    assert "- capability classification: unknown" in joined
    assert "- ready for inspection: unknown" in joined
    assert "- ready for execution: unknown" in joined
    assert "- suggested inspectors: none" in joined
    assert "- suggested execute tools: none" in joined


def test_unreadable_structured_skill_plan_routes_to_refresh_sidecars(
    tmp_path,
):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_skill_plan_json_raw(tmp_path, "{this is not valid json")

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    summary = state.skill_plan_summary
    assert summary.exists is True
    assert summary.readable is False
    assert summary.error is not None
    assert "could not be read" in summary.error

    joined = "\n".join(state.status_lines)
    assert "- structured skill plan: yes (unreadable:" in joined

    # An unreadable structured sidecar (with fresh clean validation) is
    # not a content problem; refresh both sidecars locally from the
    # existing latest_skill_plan.md so display layers and inspectors
    # see consistent structured data.
    assert state.stage == ServiceDeskWorkflowStage.SKILL_PLAN_SIDECARS_STALE
    assert state.next_action == (
        ServiceDeskWorkflowNextAction.REFRESH_SKILL_PLAN_SIDECARS
    )
    assert state.blocked is True
    assert state.blocker is not None
    assert "Structured skill plan sidecar is unreadable" in state.blocker


def test_non_object_structured_skill_plan_is_treated_as_unreadable(tmp_path):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_skill_plan_json_raw(tmp_path, json.dumps([1, 2, 3]))

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    summary = state.skill_plan_summary
    assert summary.exists is True
    assert summary.readable is False
    assert summary.error == (
        "Structured skill plan sidecar is not a JSON object."
    )

    joined = "\n".join(state.status_lines)
    assert "- structured skill plan: yes (unreadable:" in joined


def test_stale_structured_skill_plan_routes_to_refresh_sidecars(tmp_path):
    """latest_skill_plan.md newer than latest_skill_plan.json triggers
    the loader's freshness check. Workflow now refreshes the sidecars
    locally so display and inspectors see consistent structured data
    without re-prompting the model.

    Note: clean fresh validation is required to land in this branch —
    a stale validation sidecar would route to REFRESH first via the
    earlier branch.
    """
    import os

    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_skill_plan_json(tmp_path, _CLEAN_STRUCTURED_PAYLOAD)

    json_path = build_servicedesk_latest_skill_plan_json_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    validation_path = build_servicedesk_latest_skill_plan_validation_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    md_path = build_servicedesk_latest_skill_plan_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    md_mtime = md_path.stat().st_mtime
    older = md_mtime - 60.0
    # Roll only the JSON sidecar back; keep the validation sidecar
    # ahead of the Markdown so the validation-side branch does not
    # win first.
    os.utime(json_path, (older, older))
    newer = md_mtime + 60.0
    os.utime(validation_path, (newer, newer))

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    summary = state.skill_plan_summary
    assert summary.exists is True
    assert summary.readable is False
    assert summary.stale is True
    assert summary.error is not None
    assert (
        "older" in summary.error.lower()
        or "stale" in summary.error.lower()
    )

    joined = "\n".join(state.status_lines)
    assert "- structured skill plan: yes (stale:" in joined
    assert "older than latest_skill_plan.md" in joined

    # Stale structured sidecar (with fresh clean validation) routes to
    # local refresh.
    assert state.stage == ServiceDeskWorkflowStage.SKILL_PLAN_SIDECARS_STALE
    assert state.next_action == (
        ServiceDeskWorkflowNextAction.REFRESH_SKILL_PLAN_SIDECARS
    )
    assert state.blocked is True
    assert state.blocker is not None
    assert "Structured skill plan sidecar is older" in state.blocker


def test_workflow_state_module_uses_typed_loader_not_raw_json_for_skill_plan():
    """Source-level guard: servicedesk_workflow_state must build the
    skill-plan summary via load_skill_plan_json_sidecar(...). It must
    not independently json.loads latest_skill_plan.json or build the
    sidecar path on its own — that would risk display drift from the
    /sdp inspect-skill path that already uses the typed loader.

    `json` is still used to read the *validation* sidecar elsewhere in
    the module, so this guard targets only the structured skill-plan
    sidecar pieces.
    """
    from pathlib import Path

    source = Path("servicedesk_workflow_state.py").read_text(encoding="utf-8")

    # Typed loader is imported and called.
    assert "from servicedesk_skill_plan import" in source
    assert "load_skill_plan_json_sidecar" in source
    assert "load_skill_plan_json_sidecar(" in source

    # The skill-plan sidecar path helper is no longer used here;
    # filesystem location is owned by the typed loader.
    assert "build_servicedesk_latest_skill_plan_json_path" not in source

    # No raw structured-sidecar JSON parsing remains for the skill plan
    # — checked indirectly: the old raw helper name is gone.
    assert "_read_skill_plan_json_summary" not in source


# --------------------- Stale validation sidecar -------------------------


def test_stale_validation_sidecar_blocks_and_routes_to_refresh_sidecars(
    tmp_path,
):
    """latest_skill_plan_validation.json older than latest_skill_plan.md
    cannot be trusted to describe the current Markdown plan. The
    workflow must surface a synthetic `validation_sidecar_stale`
    finding, block the workflow, and route to local sidecar refresh
    (not RUN_SKILL_PLAN — that would re-prompt the model and discard
    manual edits to the Markdown).
    """
    import os

    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)

    md_path = build_servicedesk_latest_skill_plan_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    validation_path = build_servicedesk_latest_skill_plan_validation_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    md_mtime = md_path.stat().st_mtime
    older = md_mtime - 60.0
    os.utime(validation_path, (older, older))

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.validation_exists is True
    assert state.validation_has_errors is True
    assert state.blocked is True
    assert state.stage == ServiceDeskWorkflowStage.SKILL_PLAN_SIDECARS_STALE
    assert state.next_action == (
        ServiceDeskWorkflowNextAction.REFRESH_SKILL_PLAN_SIDECARS
    )

    assert len(state.validation_findings) == 1
    finding = state.validation_findings[0]
    assert finding.severity == "error"
    assert finding.code == "validation_sidecar_stale"
    assert "older than latest_skill_plan.md" in finding.message

    assert state.blocker is not None
    blocker_lower = state.blocker.lower()
    assert "older" in blocker_lower or "stale" in blocker_lower
    assert "latest_skill_plan.md" in state.blocker

    joined = "\n".join(state.status_lines)
    assert "- skill plan validation: yes (stale, 1 finding(s))" in joined
    assert "- blocker:" in joined
    # Validation sidecar is not modified by workflow state.
    assert validation_path.exists()


def test_fresh_validation_sidecar_keeps_running_inspection_recommendation(
    tmp_path,
):
    """Pristine fresh sidecar (validation written after Markdown) must
    keep behaving exactly like before: clean validation + no inspector
    outputs → RUN_INSPECTION.
    """
    import os

    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_clean_skill_plan_json(tmp_path)

    md_path = build_servicedesk_latest_skill_plan_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    validation_path = build_servicedesk_latest_skill_plan_validation_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    json_path = build_servicedesk_latest_skill_plan_json_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    md_mtime = md_path.stat().st_mtime
    newer = md_mtime + 60.0
    os.utime(validation_path, (newer, newer))
    os.utime(json_path, (newer, newer))

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.validation_exists is True
    assert state.validation_has_errors is False
    assert state.stage == ServiceDeskWorkflowStage.READY_FOR_INSPECTION
    assert state.next_action == ServiceDeskWorkflowNextAction.RUN_INSPECTION
    assert state.blocked is False
    # No stale-finding leakage when fresh.
    assert all(
        finding.code != "validation_sidecar_stale"
        for finding in state.validation_findings
    )


# --------------------- Refresh routing -----------------------------------


def test_no_skill_plan_md_still_routes_to_run_skill_plan(tmp_path):
    """When latest_skill_plan.md is missing entirely, refresh has
    nothing to do. The workflow must still recommend RUN_SKILL_PLAN.
    """
    _seed_context(tmp_path)
    # Intentionally do not seed latest_skill_plan.md.

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.skill_plan_exists is False
    assert state.next_action == ServiceDeskWorkflowNextAction.RUN_SKILL_PLAN
    assert state.stage == ServiceDeskWorkflowStage.MISSING_SKILL_PLAN


def test_fresh_real_validation_error_still_routes_to_repair(tmp_path):
    """A fresh validation sidecar with real errors must continue to
    route to REPAIR_SKILL_PLAN; the refresh path is only for stale /
    missing / unreadable sidecars.
    """
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_error_validation(tmp_path)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.validation_has_errors is True
    assert state.next_action == (
        ServiceDeskWorkflowNextAction.REPAIR_SKILL_PLAN
    )
    assert state.stage == ServiceDeskWorkflowStage.SKILL_PLAN_INVALID


def test_refresh_skill_plan_sidecars_maps_to_sdp_work():
    """REFRESH_SKILL_PLAN_SIDECARS has no separate user-facing command;
    its suggested mapping must be `/sdp work <id>` so /sdp status
    points users at the right entrypoint.
    """
    from servicedesk_workflow_state import (
        suggested_next_command_for_next_action,
    )

    suggested = suggested_next_command_for_next_action(
        next_action=ServiceDeskWorkflowNextAction.REFRESH_SKILL_PLAN_SIDECARS,
        request_id="56050",
    )

    assert suggested == "/sdp work 56050"


def test_workflow_state_with_refresh_is_new_stage_label(tmp_path):
    """SKILL_PLAN_SIDECARS_STALE stage value must be visible in
    /sdp status output so the operator can see why /sdp work picks
    refresh instead of inspection.
    """
    import os

    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)

    md_path = build_servicedesk_latest_skill_plan_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    validation_path = build_servicedesk_latest_skill_plan_validation_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    md_mtime = md_path.stat().st_mtime
    os.utime(validation_path, (md_mtime - 60.0, md_mtime - 60.0))

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    joined = "\n".join(state.status_lines)
    assert "- stage: skill_plan_sidecars_stale" in joined
    assert "- next action: refresh_skill_plan_sidecars" in joined


def test_warning_only_validation_with_missing_structured_routes_to_refresh(
    tmp_path,
):
    """Warnings do not block the workflow on their own, but a missing
    structured sidecar must still route to local refresh so /sdp work
    rebuilds it from the existing latest_skill_plan.md.
    """
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_validation(
        tmp_path,
        {
            "has_errors": False,
            "findings": [
                {
                    "severity": "warning",
                    "code": "clean_identifier_values",
                    "message": "Inspector-bound field looks dirty.",
                }
            ],
        },
    )
    # Intentionally do not seed latest_skill_plan.json.

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.validation_has_errors is False
    assert state.skill_plan_summary.exists is False
    assert state.stage == ServiceDeskWorkflowStage.SKILL_PLAN_SIDECARS_STALE
    assert state.next_action == (
        ServiceDeskWorkflowNextAction.REFRESH_SKILL_PLAN_SIDECARS
    )
    assert state.blocked is True
    assert state.blocker is not None
    assert "Structured skill plan sidecar is missing" in state.blocker


def test_real_validation_error_with_missing_structured_still_routes_to_repair(
    tmp_path,
):
    """A real fresh validation error must still route to
    REPAIR_SKILL_PLAN even when latest_skill_plan.json is missing —
    the plan content needs repair before sidecar refresh is meaningful.
    """
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_error_validation(tmp_path)
    # Intentionally do not seed latest_skill_plan.json.

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.validation_has_errors is True
    assert state.skill_plan_summary.exists is False
    assert state.stage == ServiceDeskWorkflowStage.SKILL_PLAN_INVALID
    assert state.next_action == (
        ServiceDeskWorkflowNextAction.REPAIR_SKILL_PLAN
    )


# --------------------- Stale downstream artifacts -----------------------


def _set_mtime(path: Path, mtime: float) -> None:
    import os

    os.utime(path, (mtime, mtime))


def test_inspection_report_older_than_inspector_output_is_stale(tmp_path):
    """If a supported inspector output JSON is newer than the
    inspection report, the workflow must recommend rebuilding the
    report (BUILD_INSPECTION_REPORT) and surface a stale advisory.
    """
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_clean_skill_plan_json(tmp_path)
    _seed_inspector_output(tmp_path)
    _seed_inspection_report(tmp_path)

    report_path = build_servicedesk_inspection_report_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    inspector_path = build_inspector_result_path(
        workspace=str(tmp_path),
        request_id=REQUEST_ID,
        inspector_id="active_directory.user.inspect",
    )
    base = report_path.stat().st_mtime
    _set_mtime(report_path, base - 60.0)
    _set_mtime(inspector_path, base + 60.0)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.inspection_report_exists is True
    assert state.inspection_report_stale is True
    assert state.next_action == (
        ServiceDeskWorkflowNextAction.BUILD_INSPECTION_REPORT
    )
    assert state.stage == ServiceDeskWorkflowStage.INSPECTION_REPORT_MISSING
    assert state.blocker is not None
    assert "Inspection report is stale" in state.blocker

    joined = "\n".join(state.status_lines)
    assert "- inspection report: yes (stale)" in joined


def test_fresh_inspection_report_still_advances_to_draft_note(tmp_path):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_clean_skill_plan_json(tmp_path)
    _seed_inspector_output(tmp_path)
    _seed_inspection_report(tmp_path)

    report_path = build_servicedesk_inspection_report_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    inspector_path = build_inspector_result_path(
        workspace=str(tmp_path),
        request_id=REQUEST_ID,
        inspector_id="active_directory.user.inspect",
    )
    base = report_path.stat().st_mtime
    _set_mtime(inspector_path, base - 60.0)
    _set_mtime(report_path, base + 60.0)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.inspection_report_stale is False
    assert state.draft_note_exists is False
    assert state.stage == ServiceDeskWorkflowStage.DRAFT_NOTE_MISSING
    assert state.next_action == ServiceDeskWorkflowNextAction.DRAFT_NOTE


def test_inspection_report_newer_than_draft_note_routes_to_draft_note(
    tmp_path,
):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_clean_skill_plan_json(tmp_path)
    _seed_inspector_output(tmp_path)
    _seed_inspection_report(tmp_path)
    _seed_draft_note(tmp_path)

    report_path = build_servicedesk_inspection_report_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    draft_path = build_servicedesk_draft_note_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    inspector_path = build_inspector_result_path(
        workspace=str(tmp_path),
        request_id=REQUEST_ID,
        inspector_id="active_directory.user.inspect",
    )
    base = draft_path.stat().st_mtime
    # Keep inspector output older than the report so report-stale
    # check does not preempt the draft-stale check.
    _set_mtime(inspector_path, base - 120.0)
    _set_mtime(draft_path, base - 60.0)
    _set_mtime(report_path, base + 60.0)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.draft_note_exists is True
    assert state.draft_note_stale is True
    assert state.inspection_report_stale is False
    assert state.stage == ServiceDeskWorkflowStage.DRAFT_NOTE_MISSING
    assert state.next_action == ServiceDeskWorkflowNextAction.DRAFT_NOTE
    assert state.blocker is not None
    assert "Draft note is stale" in state.blocker
    assert "inspection_report.md is newer" in state.blocker

    joined = "\n".join(state.status_lines)
    assert "- draft note: yes (stale)" in joined


def test_fresh_draft_note_still_routes_to_save_note(tmp_path):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_clean_skill_plan_json(tmp_path)
    _seed_inspector_output(tmp_path)
    _seed_inspection_report(tmp_path)
    _seed_draft_note(tmp_path)

    report_path = build_servicedesk_inspection_report_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    draft_path = build_servicedesk_draft_note_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    inspector_path = build_inspector_result_path(
        workspace=str(tmp_path),
        request_id=REQUEST_ID,
        inspector_id="active_directory.user.inspect",
    )
    base = draft_path.stat().st_mtime
    _set_mtime(inspector_path, base - 120.0)
    _set_mtime(report_path, base - 60.0)
    _set_mtime(draft_path, base + 60.0)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.inspection_report_stale is False
    assert state.draft_note_stale is False
    # Save-note routing is unchanged for the all-fresh case (the
    # actual SAVE_NOTE / REVIEW_DRAFT_NOTE choice is up to existing
    # logic; we just assert it is in the save-note family and that no
    # stale finding was injected).
    assert state.next_action in {
        ServiceDeskWorkflowNextAction.SAVE_NOTE,
        ServiceDeskWorkflowNextAction.REVIEW_DRAFT_NOTE,
    }


def test_inspection_report_stat_failure_treated_as_stale(
    tmp_path, monkeypatch
):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_clean_skill_plan_json(tmp_path)
    _seed_inspector_output(tmp_path)
    _seed_inspection_report(tmp_path)

    import servicedesk_workflow_state as workflow_state_module

    real_stat = Path.stat
    # `Path.exists()` calls `Path.stat()` internally and re-raises
    # OSError that is not in its ignored-errno set, so the existence
    # probe at the start of read_servicedesk_workflow_state would
    # also blow up. Let the first call through (the existence probe)
    # and only blow up on the helper's `path.stat().st_mtime` call.
    counter = {"calls": 0}

    def _boom_stat(self, *args, **kwargs):
        if self.name == "inspection_report.md":
            counter["calls"] += 1
            if counter["calls"] >= 2:
                raise OSError("synthetic stat failure")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(
        workflow_state_module.Path, "stat", _boom_stat
    )

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.inspection_report_exists is True
    assert state.inspection_report_stale is True
    assert state.next_action == (
        ServiceDeskWorkflowNextAction.BUILD_INSPECTION_REPORT
    )

    joined = "\n".join(state.status_lines)
    assert "- inspection report: yes (stale)" in joined


# --------------------- Draft-note validation routing --------------------


_DRAFT_NOTE_WITH_TODO = """\
# ServiceDesk internal note draft

## Note body

Inspection summary.

TODO: rewrite this section before saving.
"""


_DRAFT_NOTE_MISSING_BODY = """\
# ServiceDesk internal note draft

## Local draft metadata

- Not posted to ServiceDesk yet.
"""


def _seed_full_chain_through_draft(tmp_path):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_clean_skill_plan_json(tmp_path)
    _seed_inspector_output(tmp_path)
    _seed_inspection_report(tmp_path)


def test_valid_fresh_draft_note_routes_to_save_note(tmp_path):
    _seed_full_chain_through_draft(tmp_path)
    _seed_draft_note(tmp_path)  # uses _VALID_DRAFT_NOTE

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.draft_note_exists is True
    assert state.draft_note_stale is False
    assert state.draft_note_validation_findings == []
    assert state.next_action in {
        ServiceDeskWorkflowNextAction.SAVE_NOTE,
        ServiceDeskWorkflowNextAction.REVIEW_DRAFT_NOTE,
    }

    joined = "\n".join(state.status_lines)
    assert "- draft note validation: no issues found" in joined


def test_fresh_draft_note_with_todo_routes_to_draft_note(tmp_path):
    _seed_full_chain_through_draft(tmp_path)
    _seed_draft_note_with_text(tmp_path, _DRAFT_NOTE_WITH_TODO)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    codes = {
        finding.code for finding in state.draft_note_validation_findings
    }
    assert "placeholder_text_present" in codes

    assert state.next_action == ServiceDeskWorkflowNextAction.DRAFT_NOTE
    assert state.stage == ServiceDeskWorkflowStage.DRAFT_NOTE_MISSING
    assert state.blocker is not None
    assert "Draft note has validation errors" in state.blocker
    assert "placeholder_text_present" in state.blocker
    assert "Regenerate the draft" in state.blocker

    joined = "\n".join(state.status_lines)
    assert "- draft note validation: errors, " in joined
    assert "finding(s)" in joined


def test_fresh_draft_note_with_missing_body_routes_to_draft_note(tmp_path):
    _seed_full_chain_through_draft(tmp_path)
    _seed_draft_note_with_text(tmp_path, _DRAFT_NOTE_MISSING_BODY)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    codes = {
        finding.code for finding in state.draft_note_validation_findings
    }
    assert "note_body_missing" in codes

    assert state.next_action == ServiceDeskWorkflowNextAction.DRAFT_NOTE
    assert state.stage == ServiceDeskWorkflowStage.DRAFT_NOTE_MISSING
    assert state.blocker is not None
    assert "note_body_missing" in state.blocker


def test_stale_draft_note_skips_validation_and_keeps_stale_routing(tmp_path):
    """When the draft is stale, the existing stale-routing wins and
    draft-note validation is skipped — the user is going to regenerate
    the draft anyway, and validating an outdated draft would be noise.
    """
    import os

    _seed_full_chain_through_draft(tmp_path)
    _seed_draft_note_with_text(tmp_path, _DRAFT_NOTE_WITH_TODO)

    # Force the draft mtime behind the inspection report so it is
    # treated as stale.
    report_path = build_servicedesk_inspection_report_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    draft_path = build_servicedesk_draft_note_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    inspector_path = build_inspector_result_path(
        workspace=str(tmp_path),
        request_id=REQUEST_ID,
        inspector_id="active_directory.user.inspect",
    )
    base = draft_path.stat().st_mtime
    os.utime(inspector_path, (base - 120.0, base - 120.0))
    os.utime(draft_path, (base - 60.0, base - 60.0))
    os.utime(report_path, (base + 60.0, base + 60.0))

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.draft_note_stale is True
    # Validation is skipped for stale drafts.
    assert state.draft_note_validation_findings == []
    assert state.next_action == ServiceDeskWorkflowNextAction.DRAFT_NOTE
    assert state.stage == ServiceDeskWorkflowStage.DRAFT_NOTE_MISSING
    assert state.blocker is not None
    assert "Draft note is stale" in state.blocker

    joined = "\n".join(state.status_lines)
    assert (
        "- draft note validation: skipped (no fresh draft note)"
        in joined
    )


def test_missing_draft_note_skips_validation_and_keeps_existing_routing(
    tmp_path,
):
    _seed_full_chain_through_draft(tmp_path)
    # Intentionally do not seed draft_note.md.

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    assert state.draft_note_exists is False
    assert state.draft_note_validation_findings == []
    assert state.next_action == ServiceDeskWorkflowNextAction.DRAFT_NOTE
    assert state.stage == ServiceDeskWorkflowStage.DRAFT_NOTE_MISSING

    joined = "\n".join(state.status_lines)
    assert (
        "- draft note validation: skipped (no fresh draft note)"
        in joined
    )


# --------------------- Executor preview planning -----------------------


_EXCHANGE_FULL_ACCESS_STRUCTURED_PAYLOAD = {
    "schema_version": 1,
    "request_id": REQUEST_ID,
    "metadata": {
        "Skill match": "exchange.shared_mailbox.grant_full_access",
        "Capability classification": "draft_only_manual_now",
    },
    "extracted_inputs": [
        {
            "field": "shared_mailbox_address",
            "status": "present",
            "value": "shared@example.com",
            "evidence": "from request body",
            "needed_now": "yes",
        },
        {
            "field": "target_user",
            "status": "present",
            "value": "alice@example.com",
            "evidence": "from request body",
            "needed_now": "yes",
        },
    ],
    "missing_information_needed_now": [],
    "current_blocker": None,
    "automation_handoff": {
        "ready_for_inspection": "no",
        "ready_for_execution": "no",
        "suggested_inspector_tools": [],
        "suggested_execute_tools": [],
        "automation_blocker": None,
    },
}


def _exchange_payload_without_input(field_name: str) -> dict:
    payload = {
        **_EXCHANGE_FULL_ACCESS_STRUCTURED_PAYLOAD,
        "extracted_inputs": [
            item
            for item in _EXCHANGE_FULL_ACCESS_STRUCTURED_PAYLOAD[
                "extracted_inputs"
            ]
            if item["field"] != field_name
        ],
    }
    return payload


def test_exchange_full_access_preview_summary_when_inputs_present(tmp_path):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_skill_plan_json(
        tmp_path, _EXCHANGE_FULL_ACCESS_STRUCTURED_PAYLOAD
    )

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    summary = state.executor_preview_summary
    assert summary.applicable is True
    assert summary.preview_available is True
    assert summary.executor_id == (
        "exchange.mailbox_permission.grant_full_access"
    )
    assert summary.title == "Grant Full Access mailbox permission"
    assert summary.summary is not None
    assert "shared@example.com" in summary.summary
    assert "alice@example.com" in summary.summary
    assert summary.missing_inputs == []
    assert any("Mock/no-op executor" in w for w in summary.warnings)

    joined = "\n".join(state.status_lines)
    assert "- executor preview: available" in joined
    assert (
        "- executor: exchange.mailbox_permission.grant_full_access"
        in joined
    )
    assert (
        "- executor preview title: Grant Full Access mailbox permission"
        in joined
    )
    assert "- executor preview summary: " in joined
    assert "- executor requires approval: yes" in joined
    assert "- executor warning: Mock/no-op executor" in joined

    # Workflow stage / next_action are not affected by the executor
    # preview planner. With clean validation, missing structured-
    # sidecar suggested-inspectors is fine because the structured
    # sidecar IS present and readable; route to RUN_INSPECTION.
    assert state.stage == ServiceDeskWorkflowStage.READY_FOR_INSPECTION
    assert state.next_action == ServiceDeskWorkflowNextAction.RUN_INSPECTION


def test_exchange_full_access_preview_summary_missing_mailbox(tmp_path):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_skill_plan_json(
        tmp_path,
        _exchange_payload_without_input("shared_mailbox_address"),
    )

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    summary = state.executor_preview_summary
    assert summary.applicable is True
    assert summary.preview_available is False
    assert summary.executor_id is None
    assert "mailbox" in summary.missing_inputs

    joined = "\n".join(state.status_lines)
    assert "- executor preview: missing inputs" in joined
    assert "- executor missing inputs: mailbox" in joined


def test_exchange_full_access_preview_summary_missing_trustee(tmp_path):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_skill_plan_json(
        tmp_path,
        _exchange_payload_without_input("target_user"),
    )

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    summary = state.executor_preview_summary
    assert summary.applicable is True
    assert summary.preview_available is False
    assert "trustee" in summary.missing_inputs

    joined = "\n".join(state.status_lines)
    assert "- executor preview: missing inputs" in joined
    assert "- executor missing inputs: trustee" in joined


def test_executor_preview_summary_unsupported_skill_emits_concise_none(
    tmp_path,
):
    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    # _CLEAN_STRUCTURED_PAYLOAD has Skill match
    # = "active_directory.user.update_profile_attributes" — not
    # supported by the Exchange Full Access planner.
    _seed_clean_skill_plan_json(tmp_path)

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    summary = state.executor_preview_summary
    assert summary.applicable is False
    assert summary.preview_available is False
    assert summary.executor_id is None

    joined = "\n".join(state.status_lines)
    # Concise single line for the not-applicable case.
    assert "- executor preview: none" in joined
    # And no "available"/"missing inputs" wording leaks in.
    assert "- executor preview: available" not in joined
    assert "- executor preview: missing inputs" not in joined


def test_executor_preview_summary_skipped_when_sidecar_stale(tmp_path):
    """A stale structured sidecar must not be trusted by the executor
    planner. The planner is skipped and no preview is produced.
    """
    import os

    _seed_context(tmp_path)
    _seed_skill_plan(tmp_path)
    _seed_clean_validation(tmp_path)
    _seed_skill_plan_json(
        tmp_path, _EXCHANGE_FULL_ACCESS_STRUCTURED_PAYLOAD
    )

    md_path = build_servicedesk_latest_skill_plan_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    json_path = build_servicedesk_latest_skill_plan_json_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    md_mtime = md_path.stat().st_mtime
    # Roll the structured sidecar back behind the Markdown so the
    # loader marks it stale, but keep the validation sidecar fresh
    # so the validation-side branch doesn't preempt.
    os.utime(json_path, (md_mtime - 60.0, md_mtime - 60.0))
    validation_path = build_servicedesk_latest_skill_plan_validation_path(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )
    os.utime(validation_path, (md_mtime + 60.0, md_mtime + 60.0))

    state = read_servicedesk_workflow_state(
        workspace=str(tmp_path), request_id=REQUEST_ID
    )

    # Existing stale-structured-sidecar routing is preserved.
    assert state.skill_plan_summary.stale is True
    assert state.next_action == (
        ServiceDeskWorkflowNextAction.REFRESH_SKILL_PLAN_SIDECARS
    )

    summary = state.executor_preview_summary
    assert summary.applicable is False
    assert summary.preview_available is False
    assert summary.executor_id is None

    joined = "\n".join(state.status_lines)
    assert "- executor preview: none" in joined


def test_workflow_state_module_does_not_execute_executors_or_call_writes():
    """Source-level guard: servicedesk_workflow_state must remain
    read-only. It must not call the executor execute handler, must
    not import Exchange command runners, and must not import
    ServiceDesk write helpers. The planner is the only executor-side
    surface allowed.
    """
    from pathlib import Path

    source = Path("servicedesk_workflow_state.py").read_text(
        encoding="utf-8"
    )

    forbidden = [
        # Real PowerShell write tokens
        "Add-MailboxPermission",
        "Remove-MailboxPermission",
        "Set-Mailbox",
        "Enable-Mailbox",
        "Set-ADUser",
        "New-ADUser",
        "powershell.exe",
        # Real Exchange runners / scripts
        "exchange_command_runner",
        "exchange_powershell_runner",
        "exchange_powershell_script",
        # ServiceDesk write helpers
        "servicedesk_add_request_note",
        "servicedesk_update_request",
        # Executor execute paths — only the planner is allowed.
        "execute_exchange_grant_full_access_mock",
        "build_persisting_validation_callback",
        # Save workers
        "_save_servicedesk_note_worker",
        "_save_servicedesk_draft_worker",
    ]
    for needle in forbidden:
        assert needle not in source, (
            f"servicedesk_workflow_state must not reference {needle!r}"
        )

    # The planner is referenced (positive guard).
    assert (
        "plan_exchange_grant_full_access_preview_from_skill_plan"
        in source
    )
