from servicedesk_skill_plan import (
    ExtractedInput,
    ParsedServiceDeskSkillPlan,
    SkillPlanAutomationHandoff,
    validate_servicedesk_skill_plan,
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
