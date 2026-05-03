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


def _seed_draft_note(workspace: Path) -> None:
    _write(
        build_servicedesk_draft_note_path(
            workspace=str(workspace), request_id=REQUEST_ID
        ),
        "# ServiceDesk internal note draft\n",
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
    # /sdp work forever. Recommend regenerating the skill plan /
    # validation state instead.
    assert state.stage == ServiceDeskWorkflowStage.UNKNOWN
    assert state.next_action == ServiceDeskWorkflowNextAction.RUN_SKILL_PLAN
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
    # Same routing as malformed JSON: regenerate, do not repair Markdown.
    assert state.stage == ServiceDeskWorkflowStage.UNKNOWN
    assert state.next_action == ServiceDeskWorkflowNextAction.RUN_SKILL_PLAN


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
    assert state.next_action == ServiceDeskWorkflowNextAction.RUN_SKILL_PLAN
    assert state.stage == ServiceDeskWorkflowStage.UNKNOWN
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


def test_missing_structured_skill_plan_does_not_block_and_status_says_no(
    tmp_path,
):
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
    assert "- structured skill plan: no" in joined

    # Workflow decisions still come from existing artifact + validation
    # checks. Clean validation with no inspector outputs recommends
    # inspection.
    assert state.stage == ServiceDeskWorkflowStage.READY_FOR_INSPECTION
    assert state.next_action == ServiceDeskWorkflowNextAction.RUN_INSPECTION
    assert state.blocked is False


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


def test_unreadable_structured_skill_plan_does_not_change_workflow_decision(
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

    # Workflow decisions are not changed only because the structured
    # sidecar is unreadable. With clean validation and no inspector
    # outputs, /sdp work should still recommend inspection.
    assert state.stage == ServiceDeskWorkflowStage.READY_FOR_INSPECTION
    assert state.next_action == ServiceDeskWorkflowNextAction.RUN_INSPECTION
    assert state.blocked is False


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
        "Local skill plan JSON sidecar is not a JSON object."
    )

    joined = "\n".join(state.status_lines)
    assert "- structured skill plan: yes (unreadable:" in joined
