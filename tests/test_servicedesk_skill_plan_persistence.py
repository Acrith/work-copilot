import json

from draft_exports import build_servicedesk_latest_skill_plan_validation_path
from servicedesk_skill_plan import (
    persist_and_format_skill_plan_validation,
    validate_skill_plan_text_for_persistence,
)

_CLEAN_PLAN = """\
## Metadata

- Capability classification: read_only_inspection_now

## Extracted inputs

- field: target_user
  status: present
  value: name.surname
  evidence: from request body
  needed_now: yes

## Automation handoff

- Ready for inspection: yes
- Ready for execution: no
- Suggested inspector tools: active_directory.user.inspect
- Suggested execute tools: none
- Automation blocker: none
"""


_WARNING_ONLY_PLAN = """\
## Metadata

- Capability classification: read_only_inspection_now

## Extracted inputs

- field: target_user
  status: present
  value: Agata Piątek (agata.piatek@example.com)
  evidence: from request body
  needed_now: yes

## Automation handoff

- Ready for inspection: yes
- Ready for execution: no
- Suggested inspector tools: active_directory.user.inspect
- Suggested execute tools: none
- Automation blocker: none
"""


_ERROR_PLAN = """\
## Metadata

- Capability classification: read_only_inspection_now

## Extracted inputs

- field: target_user
  status: present
  value: name.surname
  evidence: from request body
  needed_now: yes

## Automation handoff

- Ready for inspection: yes
- Ready for execution: yes
- Suggested inspector tools: active_directory.user.inspect
- Suggested execute tools: active_directory.user.update_attributes
- Automation blocker: none
"""


# --------------------- validate_skill_plan_text_for_persistence ---------


def test_clean_plan_serializes_no_errors_and_empty_findings():
    result = validate_skill_plan_text_for_persistence(_CLEAN_PLAN)

    assert result.payload == {"has_errors": False, "findings": []}
    assert result.lines == ["Skill plan validation: no issues found."]


def test_warning_only_plan_keeps_has_errors_false():
    result = validate_skill_plan_text_for_persistence(_WARNING_ONLY_PLAN)

    assert result.payload["has_errors"] is False
    assert isinstance(result.payload["findings"], list)
    assert result.payload["findings"], "expected at least one warning finding"
    severities = {finding["severity"] for finding in result.payload["findings"]}
    assert severities == {"warning"}


def test_error_plan_sets_has_errors_true_and_records_each_finding():
    result = validate_skill_plan_text_for_persistence(_ERROR_PLAN)

    assert result.payload["has_errors"] is True

    findings = result.payload["findings"]
    assert findings, "expected error findings"
    codes = {finding["code"] for finding in findings}
    assert "ready_for_execution_must_be_no" in codes
    assert "suggested_execute_tools_must_be_none" in codes

    # Each finding has the three documented keys.
    for finding in findings:
        assert set(finding.keys()) == {"severity", "code", "message"}


def test_validation_unavailable_payload_marks_has_errors_true(monkeypatch):
    import servicedesk_skill_plan.persistence as persistence_module

    def _boom(_text: str):
        raise RuntimeError("synthetic parser failure")

    monkeypatch.setattr(
        persistence_module, "parse_servicedesk_skill_plan", _boom
    )

    result = validate_skill_plan_text_for_persistence("ignored")

    assert result.payload["has_errors"] is True
    assert result.payload["findings"] == [
        {
            "severity": "error",
            "code": "validation_unavailable",
            "message": (
                "Skill plan validation unavailable: synthetic parser failure"
            ),
        }
    ]
    assert result.lines == [
        "Skill plan validation unavailable: synthetic parser failure",
    ]


# --------------------- persist_and_format_skill_plan_validation ---------


def _read_sidecar(workspace, request_id):
    path = build_servicedesk_latest_skill_plan_validation_path(
        workspace=str(workspace),
        request_id=request_id,
    )
    return path, json.loads(path.read_text(encoding="utf-8"))


def test_persist_writes_sidecar_for_clean_plan(tmp_path):
    lines = persist_and_format_skill_plan_validation(
        workspace=str(tmp_path),
        request_id="55948",
        text=_CLEAN_PLAN,
    )

    assert lines == ["Skill plan validation: no issues found."]

    path, payload = _read_sidecar(tmp_path, "55948")
    assert path.exists()
    assert path == (
        tmp_path
        / ".work_copilot"
        / "servicedesk"
        / "55948"
        / "latest_skill_plan_validation.json"
    )
    assert payload == {"has_errors": False, "findings": []}


def test_persist_writes_sidecar_for_error_plan(tmp_path):
    persist_and_format_skill_plan_validation(
        workspace=str(tmp_path),
        request_id="55948",
        text=_ERROR_PLAN,
    )

    _, payload = _read_sidecar(tmp_path, "55948")
    assert payload["has_errors"] is True
    codes = {finding["code"] for finding in payload["findings"]}
    assert "ready_for_execution_must_be_no" in codes
    assert "suggested_execute_tools_must_be_none" in codes


def test_persist_records_validation_unavailable_when_parser_fails(
    tmp_path, monkeypatch
):
    import servicedesk_skill_plan.persistence as persistence_module

    def _boom(_text: str):
        raise RuntimeError("synthetic parser failure")

    monkeypatch.setattr(
        persistence_module, "parse_servicedesk_skill_plan", _boom
    )

    lines = persist_and_format_skill_plan_validation(
        workspace=str(tmp_path),
        request_id="55948",
        text="ignored",
    )

    assert lines == [
        "Skill plan validation unavailable: synthetic parser failure",
    ]

    _, payload = _read_sidecar(tmp_path, "55948")
    assert payload["has_errors"] is True
    assert payload["findings"] == [
        {
            "severity": "error",
            "code": "validation_unavailable",
            "message": (
                "Skill plan validation unavailable: synthetic parser failure"
            ),
        }
    ]


# --------------------- /sdp skill-plan + /sdp repair wiring -------------


def test_textual_app_skill_plan_handlers_use_persisting_validation_callback():
    """Source-level guard: both /sdp skill-plan and /sdp repair-skill-plan
    must wire the persisting validation callback so the JSON sidecar is
    written after each save. The legacy `validate_skill_plan_text_as_lines`
    callback (which only logged advisory lines) must no longer be used.
    """
    from pathlib import Path

    source = Path("textual_app.py").read_text(encoding="utf-8")

    assert "build_persisting_validation_callback" in source

    # Both call sites pass workspace + request_id so the callback can
    # compute the sidecar path.
    assert source.count(
        "post_save_callback=build_persisting_validation_callback("
    ) >= 2
    assert "workspace=self.config.workspace" in source
    assert "request_id=request_id," in source

    # The legacy callback name must no longer appear as a post_save value.
    assert (
        "post_save_callback=validate_skill_plan_text_as_lines" not in source
    )

    # Sanity: skill-plan and repair-skill-plan branches both exist.
    assert 'if command == "sdp_skill_plan":' in source
    assert 'if command == "sdp_repair_skill_plan":' in source
