import json

from draft_exports import (
    build_servicedesk_latest_skill_plan_json_path,
    build_servicedesk_latest_skill_plan_path,
    build_servicedesk_latest_skill_plan_validation_path,
)
from servicedesk_skill_plan import (
    SKILL_PLAN_JSON_SCHEMA_VERSION,
    ExtractedInput,
    ParsedServiceDeskSkillPlan,
    SkillPlanAutomationHandoff,
    SkillPlanJsonLoadError,
    SkillPlanJsonLoadResult,
    build_persisting_validation_callback,
    deserialize_skill_plan_payload,
    load_skill_plan_json_sidecar,
    parse_servicedesk_skill_plan,
    persist_and_format_skill_plan_validation,
    persist_skill_plan_json_sidecar,
    serialize_parsed_skill_plan,
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


# --------------------- serialize_parsed_skill_plan ----------------------


def _read_json_sidecar(workspace, request_id):
    path = build_servicedesk_latest_skill_plan_json_path(
        workspace=str(workspace),
        request_id=request_id,
    )
    return path, json.loads(path.read_text(encoding="utf-8"))


def test_serialize_parsed_skill_plan_includes_schema_version_and_request_id():
    plan = parse_servicedesk_skill_plan(_CLEAN_PLAN)

    payload = serialize_parsed_skill_plan(plan, request_id="56050")

    assert payload["schema_version"] == SKILL_PLAN_JSON_SCHEMA_VERSION
    assert payload["request_id"] == "56050"


def test_serialize_parsed_skill_plan_preserves_parser_field_shapes():
    plan = parse_servicedesk_skill_plan(_CLEAN_PLAN)

    payload = serialize_parsed_skill_plan(plan, request_id="56050")

    assert payload["metadata"] == {
        "Capability classification": "read_only_inspection_now"
    }

    extracted_inputs = payload["extracted_inputs"]
    assert isinstance(extracted_inputs, list)
    assert extracted_inputs == [
        {
            "field": "target_user",
            "status": "present",
            "value": "name.surname",
            "evidence": "from request body",
            "needed_now": "yes",
        }
    ]

    assert payload["missing_information_needed_now"] == []
    assert payload["current_blocker"] is None

    handoff = payload["automation_handoff"]
    assert handoff == {
        "ready_for_inspection": "yes",
        "ready_for_execution": "no",
        "suggested_inspector_tools": ["active_directory.user.inspect"],
        "suggested_execute_tools": [],
        "automation_blocker": None,
    }


# --------------------- persist_skill_plan_json_sidecar ------------------


def test_persist_skill_plan_json_sidecar_writes_for_clean_plan(tmp_path):
    lines = persist_skill_plan_json_sidecar(
        workspace=str(tmp_path),
        request_id="56050",
        text=_CLEAN_PLAN,
    )

    assert lines == []

    path, payload = _read_json_sidecar(tmp_path, "56050")
    assert path.exists()
    assert payload["schema_version"] == SKILL_PLAN_JSON_SCHEMA_VERSION
    assert payload["request_id"] == "56050"
    assert payload["automation_handoff"]["suggested_inspector_tools"] == [
        "active_directory.user.inspect"
    ]


def test_persist_skill_plan_json_sidecar_writes_when_validation_has_errors(
    tmp_path,
):
    """Markdown parsing succeeds for `_ERROR_PLAN`; the JSON sidecar
    must still be written even though validation flags errors. The
    validation sidecar is responsible for capturing has_errors=True.
    """
    json_lines = persist_skill_plan_json_sidecar(
        workspace=str(tmp_path),
        request_id="56050",
        text=_ERROR_PLAN,
    )
    assert json_lines == []

    _, json_payload = _read_json_sidecar(tmp_path, "56050")
    assert json_payload["schema_version"] == SKILL_PLAN_JSON_SCHEMA_VERSION
    assert json_payload["automation_handoff"][
        "ready_for_execution"
    ] == "yes"
    assert json_payload["automation_handoff"][
        "suggested_execute_tools"
    ] == ["active_directory.user.update_attributes"]

    persist_and_format_skill_plan_validation(
        workspace=str(tmp_path),
        request_id="56050",
        text=_ERROR_PLAN,
    )
    validation_path = build_servicedesk_latest_skill_plan_validation_path(
        workspace=str(tmp_path),
        request_id="56050",
    )
    validation_payload = json.loads(
        validation_path.read_text(encoding="utf-8")
    )
    assert validation_payload["has_errors"] is True


def test_persist_skill_plan_json_sidecar_removes_stale_on_parse_failure(
    tmp_path, monkeypatch
):
    json_path = build_servicedesk_latest_skill_plan_json_path(
        workspace=str(tmp_path),
        request_id="56050",
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        '{"schema_version": 1, "request_id": "56050", "stale": true}\n',
        encoding="utf-8",
    )
    assert json_path.exists()

    import servicedesk_skill_plan.persistence as persistence_module

    def _boom(_text: str):
        raise RuntimeError("synthetic parser failure")

    monkeypatch.setattr(
        persistence_module, "parse_servicedesk_skill_plan", _boom
    )

    lines = persist_skill_plan_json_sidecar(
        workspace=str(tmp_path),
        request_id="56050",
        text="ignored",
    )

    assert lines == [
        "Skill plan JSON sidecar unavailable: synthetic parser failure",
    ]
    assert not json_path.exists()


def test_persist_skill_plan_json_sidecar_returns_advisory_on_write_failure(
    tmp_path, monkeypatch
):
    from pathlib import Path

    import servicedesk_skill_plan.persistence as persistence_module

    real_write_text = Path.write_text

    def _boom_write(self, *args, **kwargs):
        if self.name == "latest_skill_plan.json":
            raise OSError("synthetic write failure")
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(persistence_module.Path, "write_text", _boom_write)

    lines = persist_skill_plan_json_sidecar(
        workspace=str(tmp_path),
        request_id="56050",
        text=_CLEAN_PLAN,
    )

    assert lines == [
        "Skill plan JSON sidecar unavailable: synthetic write failure",
    ]


def test_persist_skill_plan_json_sidecar_removes_stale_on_write_failure(
    tmp_path, monkeypatch
):
    """If a previous successful run wrote latest_skill_plan.json, and a
    subsequent write fails, the stale sidecar must be removed (or at
    minimum must not contain the old payload). latest_skill_plan.json
    is intended to become trusted workflow input, so a stale file that
    looks valid would be worse than no file at all.
    """
    from pathlib import Path

    import servicedesk_skill_plan.persistence as persistence_module

    json_path = build_servicedesk_latest_skill_plan_json_path(
        workspace=str(tmp_path),
        request_id="56050",
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    stale_payload = {
        "schema_version": SKILL_PLAN_JSON_SCHEMA_VERSION,
        "request_id": "56050",
        "stale": True,
    }
    json_path.write_text(
        json.dumps(stale_payload) + "\n",
        encoding="utf-8",
    )
    assert json_path.exists()

    real_write_text = Path.write_text

    def _boom_write(self, *args, **kwargs):
        if self.name == "latest_skill_plan.json":
            raise OSError("synthetic write failure")
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(persistence_module.Path, "write_text", _boom_write)

    lines = persist_skill_plan_json_sidecar(
        workspace=str(tmp_path),
        request_id="56050",
        text=_CLEAN_PLAN,
    )

    assert lines == [
        "Skill plan JSON sidecar unavailable: synthetic write failure",
    ]

    if json_path.exists():
        remaining = json.loads(json_path.read_text(encoding="utf-8"))
        assert remaining != stale_payload, (
            "stale latest_skill_plan.json must not survive a write failure"
        )
    else:
        assert not json_path.exists()


# --------------------- build_persisting_validation_callback -------------


def test_persisting_validation_callback_writes_both_sidecars(tmp_path):
    callback = build_persisting_validation_callback(
        workspace=str(tmp_path),
        request_id="56050",
    )

    lines = callback(_CLEAN_PLAN)

    # The validation lines come first; on a clean success the JSON
    # sidecar adds no extra noise.
    assert lines == ["Skill plan validation: no issues found."]

    validation_path = build_servicedesk_latest_skill_plan_validation_path(
        workspace=str(tmp_path),
        request_id="56050",
    )
    json_path = build_servicedesk_latest_skill_plan_json_path(
        workspace=str(tmp_path),
        request_id="56050",
    )

    assert validation_path.exists()
    assert json_path.exists()

    json_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert json_payload["schema_version"] == SKILL_PLAN_JSON_SCHEMA_VERSION
    assert json_payload["request_id"] == "56050"


def test_persisting_validation_callback_keeps_validation_lines_on_json_failure(
    tmp_path, monkeypatch
):
    """If the JSON sidecar persistence fails, the validation lines must
    still be returned unchanged so the existing TUI flow is preserved.
    """
    from pathlib import Path

    import servicedesk_skill_plan.persistence as persistence_module

    real_write_text = Path.write_text

    def _boom_for_json(self, *args, **kwargs):
        if self.name == "latest_skill_plan.json":
            raise OSError("synthetic write failure")
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(
        persistence_module.Path, "write_text", _boom_for_json
    )

    callback = build_persisting_validation_callback(
        workspace=str(tmp_path),
        request_id="56050",
    )

    lines = callback(_CLEAN_PLAN)

    assert "Skill plan validation: no issues found." in lines
    assert (
        "Skill plan JSON sidecar unavailable: synthetic write failure"
        in lines
    )


# --------------------- deserialize_skill_plan_payload -------------------


_FULL_PAYLOAD = {
    "schema_version": SKILL_PLAN_JSON_SCHEMA_VERSION,
    "request_id": "56050",
    "metadata": {
        "Skill match": "active_directory.user.update_profile_attributes",
        "Capability classification": "draft_only_manual_now",
    },
    "extracted_inputs": [
        {
            "field": "target_user_email",
            "status": "present",
            "value": "agata.piatek@exactforestall.com",
            "evidence": "Email address from ticket context.",
            "needed_now": "yes",
        }
    ],
    "missing_information_needed_now": [
        "The Active Directory sam_account_name is not yet known.",
    ],
    "current_blocker": (
        "Canonical Active Directory identifier is not yet known."
    ),
    "automation_handoff": {
        "ready_for_inspection": "yes",
        "ready_for_execution": "no",
        "suggested_inspector_tools": ["active_directory.user.inspect"],
        "suggested_execute_tools": [],
        "automation_blocker": "Manual technician action is required.",
    },
}


def test_deserialize_skill_plan_payload_reconstructs_full_plan():
    plan = deserialize_skill_plan_payload(_FULL_PAYLOAD)

    assert isinstance(plan, ParsedServiceDeskSkillPlan)
    assert plan.metadata == {
        "Skill match": "active_directory.user.update_profile_attributes",
        "Capability classification": "draft_only_manual_now",
    }
    assert plan.extracted_inputs == [
        ExtractedInput(
            field="target_user_email",
            status="present",
            value="agata.piatek@exactforestall.com",
            evidence="Email address from ticket context.",
            needed_now="yes",
        )
    ]
    assert plan.missing_information_needed_now == [
        "The Active Directory sam_account_name is not yet known."
    ]
    assert plan.current_blocker == (
        "Canonical Active Directory identifier is not yet known."
    )
    assert plan.automation_handoff == SkillPlanAutomationHandoff(
        ready_for_inspection="yes",
        ready_for_execution="no",
        suggested_inspector_tools=["active_directory.user.inspect"],
        suggested_execute_tools=[],
        automation_blocker="Manual technician action is required.",
    )


def test_deserialize_skill_plan_payload_round_trips_with_serializer():
    """A plan parsed from clean Markdown -> serialized -> deserialized
    should round-trip into an equal ParsedServiceDeskSkillPlan.
    """
    parsed = parse_servicedesk_skill_plan(_CLEAN_PLAN)
    payload = serialize_parsed_skill_plan(parsed, request_id="56050")

    reloaded = deserialize_skill_plan_payload(payload)

    assert reloaded == parsed


def test_deserialize_skill_plan_payload_rejects_non_object():
    import pytest

    with pytest.raises(SkillPlanJsonLoadError):
        deserialize_skill_plan_payload([1, 2, 3])

    with pytest.raises(SkillPlanJsonLoadError):
        deserialize_skill_plan_payload("not a dict")


def test_deserialize_skill_plan_payload_rejects_unsupported_schema_version():
    import pytest

    with pytest.raises(SkillPlanJsonLoadError) as excinfo:
        deserialize_skill_plan_payload(
            {**_FULL_PAYLOAD, "schema_version": 999}
        )
    assert "schema_version" in str(excinfo.value)

    with pytest.raises(SkillPlanJsonLoadError):
        payload = dict(_FULL_PAYLOAD)
        payload.pop("schema_version", None)
        deserialize_skill_plan_payload(payload)


def test_deserialize_skill_plan_payload_rejects_non_list_inspector_tools():
    import pytest

    bad = {
        **_FULL_PAYLOAD,
        "automation_handoff": {
            **_FULL_PAYLOAD["automation_handoff"],
            "suggested_inspector_tools": "active_directory.user.inspect",
        },
    }

    with pytest.raises(SkillPlanJsonLoadError) as excinfo:
        deserialize_skill_plan_payload(bad)
    assert "suggested_inspector_tools" in str(excinfo.value)


def test_deserialize_skill_plan_payload_rejects_non_list_execute_tools():
    import pytest

    bad = {
        **_FULL_PAYLOAD,
        "automation_handoff": {
            **_FULL_PAYLOAD["automation_handoff"],
            "suggested_execute_tools": {"x": "y"},
        },
    }

    with pytest.raises(SkillPlanJsonLoadError) as excinfo:
        deserialize_skill_plan_payload(bad)
    assert "suggested_execute_tools" in str(excinfo.value)


def test_deserialize_skill_plan_payload_tolerates_missing_optional_sections():
    plan = deserialize_skill_plan_payload(
        {
            "schema_version": SKILL_PLAN_JSON_SCHEMA_VERSION,
            "request_id": "56050",
        }
    )

    assert plan == ParsedServiceDeskSkillPlan()


# --------------------- load_skill_plan_json_sidecar ---------------------


def test_load_skill_plan_json_sidecar_missing(tmp_path):
    result = load_skill_plan_json_sidecar(
        workspace=str(tmp_path),
        request_id="56050",
    )

    assert isinstance(result, SkillPlanJsonLoadResult)
    assert result.exists is False
    assert result.readable is False
    assert result.plan is None
    assert result.error is None
    assert result.stale is False


def test_load_skill_plan_json_sidecar_readable(tmp_path):
    persist_skill_plan_json_sidecar(
        workspace=str(tmp_path),
        request_id="56050",
        text=_CLEAN_PLAN,
    )

    result = load_skill_plan_json_sidecar(
        workspace=str(tmp_path),
        request_id="56050",
    )

    assert result.exists is True
    assert result.readable is True
    assert result.stale is False
    assert result.error is None
    assert result.plan is not None
    assert isinstance(result.plan, ParsedServiceDeskSkillPlan)
    assert result.plan == parse_servicedesk_skill_plan(_CLEAN_PLAN)


def test_load_skill_plan_json_sidecar_malformed(tmp_path):
    json_path = build_servicedesk_latest_skill_plan_json_path(
        workspace=str(tmp_path),
        request_id="56050",
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text("{this is not valid json", encoding="utf-8")

    result = load_skill_plan_json_sidecar(
        workspace=str(tmp_path),
        request_id="56050",
    )

    assert result.exists is True
    assert result.readable is False
    assert result.plan is None
    assert result.error is not None
    assert "could not be read" in result.error
    assert result.stale is False


def test_load_skill_plan_json_sidecar_unsupported_schema_version_is_unreadable(
    tmp_path,
):
    json_path = build_servicedesk_latest_skill_plan_json_path(
        workspace=str(tmp_path),
        request_id="56050",
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps({"schema_version": 999, "request_id": "56050"}) + "\n",
        encoding="utf-8",
    )

    result = load_skill_plan_json_sidecar(
        workspace=str(tmp_path),
        request_id="56050",
    )

    assert result.exists is True
    assert result.readable is False
    assert result.plan is None
    assert result.error is not None
    assert "schema_version" in result.error


def test_load_skill_plan_json_sidecar_stale_when_md_is_newer(tmp_path):
    persist_skill_plan_json_sidecar(
        workspace=str(tmp_path),
        request_id="56050",
        text=_CLEAN_PLAN,
    )
    json_path = build_servicedesk_latest_skill_plan_json_path(
        workspace=str(tmp_path),
        request_id="56050",
    )
    md_path = build_servicedesk_latest_skill_plan_path(
        workspace=str(tmp_path),
        request_id="56050",
    )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_CLEAN_PLAN, encoding="utf-8")

    # Force the JSON sidecar to look older than the Markdown.
    import os

    md_mtime = md_path.stat().st_mtime
    older = md_mtime - 60.0
    os.utime(json_path, (older, older))

    result = load_skill_plan_json_sidecar(
        workspace=str(tmp_path),
        request_id="56050",
    )

    assert result.exists is True
    assert result.readable is False
    assert result.stale is True
    assert result.plan is None
    assert result.error is not None
    assert (
        "older" in result.error.lower()
        or "stale" in result.error.lower()
    )

    # Loader does not delete the on-disk JSON sidecar.
    assert json_path.exists()


def test_load_skill_plan_json_sidecar_not_stale_when_json_is_newer(tmp_path):
    md_path = build_servicedesk_latest_skill_plan_path(
        workspace=str(tmp_path),
        request_id="56050",
    )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_CLEAN_PLAN, encoding="utf-8")

    persist_skill_plan_json_sidecar(
        workspace=str(tmp_path),
        request_id="56050",
        text=_CLEAN_PLAN,
    )
    json_path = build_servicedesk_latest_skill_plan_json_path(
        workspace=str(tmp_path),
        request_id="56050",
    )

    # Force the JSON sidecar to look newer than the Markdown.
    import os

    md_mtime = md_path.stat().st_mtime
    newer = md_mtime + 60.0
    os.utime(json_path, (newer, newer))

    result = load_skill_plan_json_sidecar(
        workspace=str(tmp_path),
        request_id="56050",
    )

    assert result.exists is True
    assert result.readable is True
    assert result.stale is False
    assert result.plan is not None


# --------------------- refresh_skill_plan_sidecars_from_markdown --------


def test_refresh_writes_both_sidecars_from_existing_markdown(tmp_path):
    from servicedesk_skill_plan import refresh_skill_plan_sidecars_from_markdown

    md_path = build_servicedesk_latest_skill_plan_path(
        workspace=str(tmp_path), request_id="56050"
    )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_CLEAN_PLAN, encoding="utf-8")

    lines = refresh_skill_plan_sidecars_from_markdown(
        workspace=str(tmp_path),
        request_id="56050",
    )

    # Validation lines come first; clean success adds no JSON-side
    # advisory.
    assert lines == ["Skill plan validation: no issues found."]

    validation_path = build_servicedesk_latest_skill_plan_validation_path(
        workspace=str(tmp_path),
        request_id="56050",
    )
    json_path = build_servicedesk_latest_skill_plan_json_path(
        workspace=str(tmp_path),
        request_id="56050",
    )
    assert validation_path.exists()
    assert json_path.exists()

    validation_payload = json.loads(
        validation_path.read_text(encoding="utf-8")
    )
    json_payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert validation_payload == {"has_errors": False, "findings": []}
    assert json_payload["request_id"] == "56050"


def test_refresh_returns_advisory_when_markdown_missing(tmp_path):
    from servicedesk_skill_plan import refresh_skill_plan_sidecars_from_markdown

    lines = refresh_skill_plan_sidecars_from_markdown(
        workspace=str(tmp_path),
        request_id="56050",
    )

    assert len(lines) == 1
    assert "No local skill plan found for request 56050" in lines[0]
    assert "cannot refresh sidecars" in lines[0]

    # Helper must not write either sidecar when the Markdown is missing.
    validation_path = build_servicedesk_latest_skill_plan_validation_path(
        workspace=str(tmp_path),
        request_id="56050",
    )
    json_path = build_servicedesk_latest_skill_plan_json_path(
        workspace=str(tmp_path),
        request_id="56050",
    )
    assert not validation_path.exists()
    assert not json_path.exists()


def test_refresh_handles_unparseable_markdown_without_raising(
    tmp_path, monkeypatch
):
    """If parsing the existing Markdown fails inside the persistence
    helpers, refresh must still return advisory lines and must not
    raise. The structured sidecar's existing parse-failure cleanup
    behavior (remove stale latest_skill_plan.json) is preserved.
    """
    import servicedesk_skill_plan.persistence as persistence_module
    from servicedesk_skill_plan import refresh_skill_plan_sidecars_from_markdown

    md_path = build_servicedesk_latest_skill_plan_path(
        workspace=str(tmp_path), request_id="56050"
    )
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_CLEAN_PLAN, encoding="utf-8")

    # Pre-create a stale latest_skill_plan.json so we can verify the
    # parse-failure cleanup still runs.
    json_path = build_servicedesk_latest_skill_plan_json_path(
        workspace=str(tmp_path), request_id="56050"
    )
    json_path.write_text(
        '{"schema_version": 1, "request_id": "56050", "stale": true}\n',
        encoding="utf-8",
    )

    def _boom(_text: str):
        raise RuntimeError("synthetic parser failure")

    monkeypatch.setattr(
        persistence_module, "parse_servicedesk_skill_plan", _boom
    )

    lines = refresh_skill_plan_sidecars_from_markdown(
        workspace=str(tmp_path),
        request_id="56050",
    )

    # Validation falls back to a "validation unavailable" advisory and
    # the structured-sidecar persistence falls back to a JSON sidecar
    # advisory. Both lines must be present.
    assert any(
        "Skill plan validation unavailable" in line for line in lines
    ), lines
    assert any(
        "Skill plan JSON sidecar unavailable" in line for line in lines
    ), lines

    # Stale structured sidecar must have been cleaned up by the
    # underlying helper.
    assert not json_path.exists()
