from servicedesk_skill_plan import (
    ExtractedInput,
    ParsedServiceDeskSkillPlan,
    SkillPlanAutomationHandoff,
    SkillPlanValidationFinding,
    format_skill_plan_validation_findings,
    parse_servicedesk_skill_plan,
    validate_parsed_skill_plan_for_inspection,
    validate_servicedesk_skill_plan,
    validate_skill_plan_text_as_lines,
    validate_skill_plan_text_for_inspection,
)


def _make_plan(
    *,
    metadata: dict[str, str] | None = None,
    extracted_inputs: list[ExtractedInput] | None = None,
    handoff: SkillPlanAutomationHandoff | None = None,
) -> ParsedServiceDeskSkillPlan:
    return ParsedServiceDeskSkillPlan(
        metadata=metadata or {"Capability classification": "read_only_inspection_now"},
        extracted_inputs=extracted_inputs or [],
        automation_handoff=handoff or SkillPlanAutomationHandoff(),
    )


def _codes(findings) -> list[str]:
    return [finding.code for finding in findings]


def test_rejects_non_no_ready_for_execution():
    plan = _make_plan(
        handoff=SkillPlanAutomationHandoff(
            ready_for_inspection="no",
            ready_for_execution="yes",
        ),
    )

    findings = validate_servicedesk_skill_plan(plan)

    codes = _codes(findings)
    assert "ready_for_execution_must_be_no" in codes
    assert any(
        finding.severity == "error"
        and finding.code == "ready_for_execution_must_be_no"
        for finding in findings
    )


def test_rejects_unsupported_hypothetical_execute_tool():
    plan = _make_plan(
        metadata={"Capability classification": "draft_only_manual_now"},
        handoff=SkillPlanAutomationHandoff(
            ready_for_inspection="no",
            ready_for_execution="no",
            suggested_execute_tools=[
                "active_directory.user.update_attributes",
            ],
        ),
    )

    findings = validate_servicedesk_skill_plan(plan)

    matching = [
        finding
        for finding in findings
        if finding.code == "suggested_execute_tools_must_be_none"
    ]
    assert matching
    assert any(
        "active_directory.user.update_attributes" in finding.message
        for finding in matching
    )
    assert all(finding.severity == "error" for finding in matching)


def test_rejects_unsupported_inspector_tool():
    plan = _make_plan(
        metadata={"Capability classification": "read_only_inspection_now"},
        handoff=SkillPlanAutomationHandoff(
            ready_for_inspection="yes",
            ready_for_execution="no",
            suggested_inspector_tools=[
                "active_directory.user.get_properties",
            ],
        ),
    )

    findings = validate_servicedesk_skill_plan(plan)

    matching = [
        finding
        for finding in findings
        if finding.code == "supported_inspector_tools_only"
    ]
    assert matching
    assert any(
        "active_directory.user.get_properties" in finding.message
        for finding in matching
    )
    assert all(finding.severity == "error" for finding in matching)


def test_rejects_inspectors_for_future_automation_candidate():
    plan = _make_plan(
        metadata={"Capability classification": "future_automation_candidate"},
        handoff=SkillPlanAutomationHandoff(
            ready_for_inspection="no",
            ready_for_execution="no",
            suggested_inspector_tools=["active_directory.user.inspect"],
        ),
    )

    findings = validate_servicedesk_skill_plan(plan)

    codes = _codes(findings)
    assert "no_inspectors_for_future_or_unsupported" in codes


def test_rejects_inspectors_for_unsupported_no_safe_capability():
    plan = _make_plan(
        metadata={"Capability classification": "unsupported_no_safe_capability"},
        handoff=SkillPlanAutomationHandoff(
            ready_for_inspection="no",
            ready_for_execution="no",
            suggested_inspector_tools=["active_directory.group.inspect"],
        ),
    )

    findings = validate_servicedesk_skill_plan(plan)

    codes = _codes(findings)
    assert "no_inspectors_for_future_or_unsupported" in codes


def test_warns_on_dirty_identifier_with_display_name_and_email():
    plan = _make_plan(
        extracted_inputs=[
            ExtractedInput(
                field="target_user",
                status="present",
                value="Agata Piątek (agata.piatek@example.com)",
                evidence="request body",
                needed_now="yes",
            )
        ],
        handoff=SkillPlanAutomationHandoff(
            ready_for_inspection="yes",
            ready_for_execution="no",
            suggested_inspector_tools=["active_directory.user.inspect"],
        ),
    )

    findings = validate_servicedesk_skill_plan(plan)

    matching = [
        finding
        for finding in findings
        if finding.code == "clean_identifier_values"
    ]
    assert matching
    assert all(finding.severity == "warning" for finding in matching)
    assert any(
        "Agata Piątek (agata.piatek@example.com)" in finding.message
        for finding in matching
    )


def test_warns_on_prefixed_identifier():
    plan = _make_plan(
        extracted_inputs=[
            ExtractedInput(
                field="target_user_email",
                status="present",
                value="user: agata.piatek@example.com",
                evidence="request body",
                needed_now="yes",
            )
        ],
        handoff=SkillPlanAutomationHandoff(
            ready_for_inspection="yes",
            ready_for_execution="no",
            suggested_inspector_tools=["active_directory.user.inspect"],
        ),
    )

    findings = validate_servicedesk_skill_plan(plan)

    matching = [
        finding
        for finding in findings
        if finding.code == "clean_identifier_values"
    ]
    assert matching
    assert all(finding.severity == "warning" for finding in matching)
    assert any(
        "prefixed with a label" in finding.message for finding in matching
    )


def test_read_only_inspection_now_without_inspectors_errors():
    plan = _make_plan(
        metadata={"Capability classification": "read_only_inspection_now"},
        handoff=SkillPlanAutomationHandoff(
            ready_for_inspection="no",
            ready_for_execution="no",
            suggested_inspector_tools=[],
        ),
    )

    findings = validate_servicedesk_skill_plan(plan)

    codes = _codes(findings)
    assert "read_only_inspection_now_requires_inspector" in codes
    assert any(
        finding.severity == "error"
        and finding.code == "read_only_inspection_now_requires_inspector"
        for finding in findings
    )


def test_ready_for_inspection_yes_without_inspectors_warns():
    plan = _make_plan(
        metadata={"Capability classification": "draft_only_manual_now"},
        handoff=SkillPlanAutomationHandoff(
            ready_for_inspection="yes",
            ready_for_execution="no",
            suggested_inspector_tools=[],
        ),
    )

    findings = validate_servicedesk_skill_plan(plan)

    matching = [
        finding
        for finding in findings
        if finding.code == "ready_for_inspection_requires_inspector"
    ]
    assert matching
    assert all(finding.severity == "warning" for finding in matching)


def test_validation_requires_user_and_group_for_ad_membership_inspector():
    plan = _make_plan(
        metadata={"Capability classification": "read_only_inspection_now"},
        extracted_inputs=[
            ExtractedInput(
                field="target_user",
                status="present",
                value="name.surname",
                evidence="from request body",
                needed_now="yes",
            )
        ],
        handoff=SkillPlanAutomationHandoff(
            ready_for_inspection="yes",
            ready_for_execution="no",
            suggested_inspector_tools=[
                "active_directory.group_membership.inspect",
            ],
        ),
    )

    findings = validate_servicedesk_skill_plan(plan)

    matching = [
        finding
        for finding in findings
        if finding.code == "selected_inspectors_require_present_inputs"
    ]
    assert matching
    assert all(finding.severity == "error" for finding in matching)
    assert any(
        "active_directory.group_membership.inspect" in finding.message
        and "both a present user identifier and a present group identifier"
        in finding.message
        for finding in matching
    )


def test_validation_requires_present_value_not_just_present_status():
    plan = _make_plan(
        metadata={"Capability classification": "read_only_inspection_now"},
        extracted_inputs=[
            ExtractedInput(
                field="target_user",
                status="present",
                value="",
                evidence="",
                needed_now="yes",
            )
        ],
        handoff=SkillPlanAutomationHandoff(
            ready_for_inspection="yes",
            ready_for_execution="no",
            suggested_inspector_tools=[
                "active_directory.user.inspect",
            ],
        ),
    )

    findings = validate_servicedesk_skill_plan(plan)

    matching = [
        finding
        for finding in findings
        if finding.code == "selected_inspectors_require_present_inputs"
    ]
    assert matching
    assert all(finding.severity == "error" for finding in matching)
    assert any(
        "active_directory.user.inspect" in finding.message
        and "user identifier" in finding.message
        for finding in matching
    )


def test_validation_requires_mailbox_identifier_for_exchange_inspector():
    plan = _make_plan(
        metadata={"Capability classification": "read_only_inspection_now"},
        extracted_inputs=[
            ExtractedInput(
                field="target_group",
                status="present",
                value="usr.podpis.test",
                evidence="from request body",
                needed_now="yes",
            )
        ],
        handoff=SkillPlanAutomationHandoff(
            ready_for_inspection="yes",
            ready_for_execution="no",
            suggested_inspector_tools=[
                "exchange.mailbox.inspect",
            ],
        ),
    )

    findings = validate_servicedesk_skill_plan(plan)

    matching = [
        finding
        for finding in findings
        if finding.code == "selected_inspectors_require_present_inputs"
    ]
    assert matching
    assert all(finding.severity == "error" for finding in matching)
    assert any(
        "exchange.mailbox.inspect" in finding.message
        and "mailbox identifier" in finding.message
        for finding in matching
    )


def test_valid_ad_inspection_plan_has_no_findings():
    plan = _make_plan(
        metadata={"Capability classification": "read_only_inspection_now"},
        extracted_inputs=[
            ExtractedInput(
                field="target_user",
                status="present",
                value="name.surname",
                evidence="from request body",
                needed_now="yes",
            ),
            ExtractedInput(
                field="target_group",
                status="present",
                value="usr.podpis.test",
                evidence="from request body",
                needed_now="yes",
            ),
        ],
        handoff=SkillPlanAutomationHandoff(
            ready_for_inspection="yes",
            ready_for_execution="no",
            suggested_inspector_tools=[
                "active_directory.user.inspect",
                "active_directory.group.inspect",
                "active_directory.group_membership.inspect",
            ],
            suggested_execute_tools=[],
        ),
    )

    findings = validate_servicedesk_skill_plan(plan)

    assert findings == []


# --------------------- Formatter + advisory helper ----------------------


def test_format_skill_plan_validation_findings_no_findings():
    assert format_skill_plan_validation_findings([]) == [
        "Skill plan validation: no issues found.",
    ]


def test_format_skill_plan_validation_findings_one_warning():
    findings = [
        SkillPlanValidationFinding(
            severity="warning",
            code="clean_identifier_values",
            message="Inspector-bound field `target_user` value `user: x` is prefixed.",
        )
    ]

    assert format_skill_plan_validation_findings(findings) == [
        "Skill plan validation: found 1 issue(s).",
        (
            "- WARNING [clean_identifier_values]: Inspector-bound field "
            "`target_user` value `user: x` is prefixed."
        ),
    ]


def test_format_skill_plan_validation_findings_one_error():
    findings = [
        SkillPlanValidationFinding(
            severity="error",
            code="ready_for_execution_must_be_no",
            message="Automation handoff `Ready for execution` must be `no`; got `yes`.",
        )
    ]

    assert format_skill_plan_validation_findings(findings) == [
        "Skill plan validation: found 1 issue(s).",
        (
            "- ERROR [ready_for_execution_must_be_no]: Automation handoff "
            "`Ready for execution` must be `no`; got `yes`."
        ),
    ]


def test_format_skill_plan_validation_findings_mixed():
    findings = [
        SkillPlanValidationFinding(
            severity="error",
            code="supported_inspector_tools_only",
            message="Suggested inspector tool `bogus` is not a registered inspector ID.",
        ),
        SkillPlanValidationFinding(
            severity="warning",
            code="ready_for_inspection_requires_inspector",
            message="`Ready for inspection: yes` but `Suggested inspector tools` is empty.",
        ),
    ]

    lines = format_skill_plan_validation_findings(findings)

    assert lines[0] == "Skill plan validation: found 2 issue(s)."
    assert lines[1].startswith("- ERROR [supported_inspector_tools_only]:")
    assert lines[2].startswith("- WARNING [ready_for_inspection_requires_inspector]:")


def test_validate_skill_plan_text_as_lines_clean_plan():
    plan_text = """\
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

    assert validate_skill_plan_text_as_lines(plan_text) == [
        "Skill plan validation: no issues found.",
    ]


def test_validate_skill_plan_text_as_lines_plan_with_issues():
    plan_text = """\
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
- Ready for execution: yes
- Suggested inspector tools: active_directory.user.inspect
- Suggested execute tools: active_directory.user.update_attributes
- Automation blocker: none
"""

    lines = validate_skill_plan_text_as_lines(plan_text)

    assert lines[0].startswith("Skill plan validation: found ")
    joined = "\n".join(lines)
    assert "ERROR [ready_for_execution_must_be_no]" in joined
    assert "ERROR [suggested_execute_tools_must_be_none]" in joined
    assert "WARNING [clean_identifier_values]" in joined


def test_validate_skill_plan_text_as_lines_handles_unexpected_error(monkeypatch):
    # Force the parser to raise to confirm the helper wraps it instead of
    # propagating, so the TUI never crashes from a bad plan file.
    import servicedesk_skill_plan.validation as validation_module

    def _boom(_text: str):
        raise RuntimeError("synthetic parser failure")

    monkeypatch.setattr(
        validation_module,
        "parse_servicedesk_skill_plan",
        _boom,
    )

    lines = validate_skill_plan_text_as_lines("ignored")

    assert lines == [
        "Skill plan validation unavailable: synthetic parser failure",
    ]


# --------------------- Inspection safety gate ---------------------------


_CLEAN_PLAN_FOR_INSPECTION = """\
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


_WARNING_ONLY_PLAN_FOR_INSPECTION = """\
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


_ERROR_PLAN_FOR_INSPECTION = """\
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


def test_validate_skill_plan_text_for_inspection_clean_plan_does_not_block():
    result = validate_skill_plan_text_for_inspection(_CLEAN_PLAN_FOR_INSPECTION)

    assert result.has_errors is False
    assert result.lines == ["Skill plan validation: no issues found."]


def test_validate_skill_plan_text_for_inspection_warning_only_does_not_block():
    result = validate_skill_plan_text_for_inspection(
        _WARNING_ONLY_PLAN_FOR_INSPECTION
    )

    assert result.has_errors is False
    assert result.lines[0].startswith("Skill plan validation: found ")
    joined = "\n".join(result.lines)
    assert "WARNING [clean_identifier_values]" in joined
    assert "ERROR " not in joined


def test_validate_skill_plan_text_for_inspection_blocks_on_errors():
    result = validate_skill_plan_text_for_inspection(_ERROR_PLAN_FOR_INSPECTION)

    assert result.has_errors is True
    assert result.lines[0].startswith("Skill plan validation: found ")
    joined = "\n".join(result.lines)
    assert "ERROR [ready_for_execution_must_be_no]" in joined
    assert "ERROR [suggested_execute_tools_must_be_none]" in joined


def test_validate_skill_plan_text_for_inspection_blocks_on_unexpected_error(
    monkeypatch,
):
    import servicedesk_skill_plan.validation as validation_module

    def _boom(_text: str):
        raise RuntimeError("synthetic parser failure")

    monkeypatch.setattr(
        validation_module,
        "parse_servicedesk_skill_plan",
        _boom,
    )

    result = validate_skill_plan_text_for_inspection("ignored")

    assert result.has_errors is True
    assert result.lines == [
        "Skill plan validation unavailable: synthetic parser failure",
    ]


def test_validate_parsed_skill_plan_for_inspection_clean_plan_does_not_block():
    plan = parse_servicedesk_skill_plan(_CLEAN_PLAN_FOR_INSPECTION)

    result = validate_parsed_skill_plan_for_inspection(plan)

    assert result.has_errors is False
    assert result.lines == ["Skill plan validation: no issues found."]


def test_validate_parsed_skill_plan_for_inspection_blocks_on_execute_tools():
    plan = parse_servicedesk_skill_plan(_ERROR_PLAN_FOR_INSPECTION)

    result = validate_parsed_skill_plan_for_inspection(plan)

    assert result.has_errors is True
    joined = "\n".join(result.lines)
    assert "ERROR [ready_for_execution_must_be_no]" in joined
    assert "ERROR [suggested_execute_tools_must_be_none]" in joined


def test_validate_parsed_skill_plan_for_inspection_warning_only_does_not_block():
    plan = parse_servicedesk_skill_plan(_WARNING_ONLY_PLAN_FOR_INSPECTION)

    result = validate_parsed_skill_plan_for_inspection(plan)

    assert result.has_errors is False
    joined = "\n".join(result.lines)
    assert "WARNING [clean_identifier_values]" in joined
    assert "ERROR " not in joined


def test_validate_parsed_skill_plan_for_inspection_handles_unexpected_error(
    monkeypatch,
):
    import servicedesk_skill_plan.validation as validation_module

    def _boom(_plan):
        raise RuntimeError("synthetic validator failure")

    monkeypatch.setattr(
        validation_module,
        "validate_servicedesk_skill_plan",
        _boom,
    )

    plan = parse_servicedesk_skill_plan(_CLEAN_PLAN_FOR_INSPECTION)
    result = validate_parsed_skill_plan_for_inspection(plan)

    assert result.has_errors is True
    assert result.lines == [
        "Skill plan validation unavailable: synthetic validator failure",
    ]
