import pytest

from inspectors.models import InspectorRequest
from inspectors.skill_plan import (
    SkillPlanInput,
    SkillPlanInspectorSelection,
    build_inspector_request_from_parsed_skill_plan,
    build_inspector_request_from_skill_plan,
    normalize_inspector_id,
    parse_extracted_inputs,
    parse_skill_match,
    parse_suggested_inspector_tools,
    select_inspector_for_skill_plan,
    select_inspectors_for_parsed_skill_plan,
    select_inspectors_for_skill_plan,
    select_supported_inspector_tool,
    select_supported_inspector_tools,
)
from servicedesk_skill_plan import (
    ExtractedInput,
    ParsedServiceDeskSkillPlan,
    SkillPlanAutomationHandoff,
    parse_servicedesk_skill_plan,
)


def test_parse_suggested_inspector_tools():
    skill_plan = """
# ServiceDesk skill plan

## Automation handoff

- Ready for inspection: yes
- Ready for execution: no
- Suggested inspector tools: exchange.mailbox.inspect, active_directory.user.lookup
- Suggested execute tools: none
"""

    assert parse_suggested_inspector_tools(skill_plan) == [
        "exchange.mailbox.inspect",
        "active_directory.user.lookup",
    ]


def test_parse_suggested_inspector_tools_returns_empty_for_none():
    skill_plan = """
## Automation handoff

- Suggested inspector tools: none
"""

    assert parse_suggested_inspector_tools(skill_plan) == []


def test_parse_suggested_inspector_tools_strips_backticks():
    skill_plan = """
## Automation handoff

- Suggested inspector tools: `exchange.mailbox.inspect`
"""

    assert parse_suggested_inspector_tools(skill_plan) == [
        "exchange.mailbox.inspect",
    ]


def test_parse_extracted_inputs():
    skill_plan = """
## Extracted inputs

- field: mailbox_address
  status: present
  value: user@example.com
  evidence: requester provided mailbox address
  needed_now: yes

- field: approval_status
  status: unclear
  value:
  evidence: no explicit approval visible
  needed_now: yes

- field: effective_date
  status: not_needed_now
  value:
  evidence: no effective date needed
  needed_now: no
"""

    parsed = parse_extracted_inputs(skill_plan)

    assert parsed == {
        "mailbox_address": SkillPlanInput(
            field="mailbox_address",
            status="present",
            value="user@example.com",
            evidence="requester provided mailbox address",
            needed_now=True,
        ),
        "approval_status": SkillPlanInput(
            field="approval_status",
            status="unclear",
            value="",
            evidence="no explicit approval visible",
            needed_now=True,
        ),
        "effective_date": SkillPlanInput(
            field="effective_date",
            status="not_needed_now",
            value="",
            evidence="no effective date needed",
            needed_now=False,
        ),
    }


def test_build_exchange_mailbox_inspector_request_from_mailbox_address():
    skill_plan = """
## Extracted inputs

- field: mailbox_address
  status: present
  value: user@example.com
  evidence: saved context
  needed_now: yes

## Automation handoff

- Suggested inspector tools: exchange.mailbox.inspect
"""

    request = build_inspector_request_from_skill_plan(
        request_id="55948",
        skill_plan_text=skill_plan,
        inspector_id="exchange.mailbox.inspect",
    )

    assert isinstance(request, InspectorRequest)
    assert request.inspector == "exchange.mailbox.inspect"
    assert request.request_id == "55948"
    assert request.target.type == "mailbox"
    assert request.target.id == "user@example.com"
    assert request.target.metadata == {"source": "skill_plan"}
    assert request.inputs["mailbox_address"] == "user@example.com"
    assert request.inputs["skill_plan_inputs"] == {
        "mailbox_address": {
            "field": "mailbox_address",
            "status": "present",
            "value": "user@example.com",
            "evidence": "saved context",
            "needed_now": True,
        }
    }


def test_build_exchange_mailbox_inspector_request_from_target_user_fallback():
    skill_plan = """
## Extracted inputs

- field: target_user
  status: present
  value: user@example.com
  evidence: saved context
  needed_now: yes
"""

    request = build_inspector_request_from_skill_plan(
        request_id="55948",
        skill_plan_text=skill_plan,
        inspector_id="exchange.mailbox.inspect",
    )

    assert request.target.id == "user@example.com"
    assert request.inputs["mailbox_address"] == "user@example.com"


def test_build_inspector_request_rejects_unsupported_inspector():
    with pytest.raises(ValueError, match="Unsupported inspector"):
        build_inspector_request_from_skill_plan(
            request_id="55948",
            skill_plan_text="",
            inspector_id="exchange.shared_mailbox.get_full_access_permissions",
        )


def test_build_exchange_mailbox_inspector_request_requires_mailbox_input():
    skill_plan = """
## Extracted inputs

- field: mailbox_address
  status: missing
  value:
  evidence: none
  needed_now: yes
"""

    with pytest.raises(ValueError, match="missing mailbox_address"):
        build_inspector_request_from_skill_plan(
            request_id="55948",
            skill_plan_text=skill_plan,
            inspector_id="exchange.mailbox.inspect",
        )


def test_select_supported_inspector_tool_returns_first_supported_tool():
    selected = select_supported_inspector_tool(
        [
            "exchange.shared_mailbox.get_full_access_permissions",
            "exchange.mailbox.inspect",
        ]
    )

    assert selected == "exchange.mailbox.inspect"


def test_select_supported_inspector_tool_returns_none_when_no_supported_tool():
    selected = select_supported_inspector_tool(
        [
            "exchange.shared_mailbox.get_full_access_permissions",
            "exchange.shared_mailbox.grant_full_access",
        ]
    )

    assert selected is None


@pytest.mark.parametrize(
    "granular_id",
    [
        "exchange.mailbox.get_properties",
        "exchange.mailbox.get_statistics",
        "exchange.mailbox.get_archive_status",
        "exchange.mailbox.get_retention_policy",
        "exchange.mailbox.prepare_inspection_report_parameters",
    ],
)
def test_normalize_inspector_id_maps_granular_mailbox_ids_to_inspect(granular_id):
    assert normalize_inspector_id(granular_id) == "exchange.mailbox.inspect"


def test_normalize_inspector_id_strips_backticks():
    assert normalize_inspector_id("`exchange.mailbox.get_properties`") == (
        "exchange.mailbox.inspect"
    )


def test_normalize_inspector_id_passes_through_unknown_ids():
    assert normalize_inspector_id(
        "exchange.shared_mailbox.get_full_access_permissions"
    ) == "exchange.shared_mailbox.get_full_access_permissions"


def test_select_supported_inspector_tool_normalizes_granular_ids():
    selected = select_supported_inspector_tool(
        [
            "exchange.mailbox.get_properties",
            "exchange.mailbox.get_statistics",
        ]
    )

    assert selected == "exchange.mailbox.inspect"


def test_build_inspector_request_normalizes_granular_inspector_id():
    skill_plan = """
## Extracted inputs

- field: mailbox_address
  status: present
  value: user@example.com
  evidence: saved context
  needed_now: yes
"""

    request = build_inspector_request_from_skill_plan(
        request_id="55948",
        skill_plan_text=skill_plan,
        inspector_id="exchange.mailbox.get_statistics",
    )

    assert request.inspector == "exchange.mailbox.inspect"


def test_parse_skill_match_returns_value():
    skill_plan = """
## Metadata

- Ticket: 55948
- Skill match: exchange.mailbox.inspect
- Skill relevance: primary
"""

    assert parse_skill_match(skill_plan) == "exchange.mailbox.inspect"


def test_parse_skill_match_strips_backticks():
    skill_plan = """
- Skill match: `exchange.mailbox.inspect`
"""

    assert parse_skill_match(skill_plan) == "exchange.mailbox.inspect"


def test_parse_skill_match_returns_none_for_none_value():
    skill_plan = """
- Skill match: none
"""

    assert parse_skill_match(skill_plan) is None


def test_parse_skill_match_returns_none_when_missing():
    assert parse_skill_match("") is None


def test_select_inspector_for_skill_plan_prefers_suggested_tools():
    skill_plan = """
- Skill match: exchange.mailbox.inspect

## Automation handoff

- Suggested inspector tools: exchange.mailbox.inspect
"""

    selection = select_inspector_for_skill_plan(skill_plan)

    assert selection == SkillPlanInspectorSelection(
        inspector_id="exchange.mailbox.inspect",
        source="suggested_inspector_tools",
    )


def test_select_inspector_for_skill_plan_falls_back_to_skill_match():
    skill_plan = """
- Skill match: exchange.mailbox.inspect

## Automation handoff

- Suggested inspector tools: exchange.mailbox.get_unknown_thing
"""

    selection = select_inspector_for_skill_plan(skill_plan)

    assert selection == SkillPlanInspectorSelection(
        inspector_id="exchange.mailbox.inspect",
        source="skill_match",
    )


def test_select_inspector_for_skill_plan_returns_none_when_skill_match_unsupported():
    skill_plan = """
- Skill match: active_directory.user.provision_standard_account

## Automation handoff

- Suggested inspector tools: none
"""

    assert select_inspector_for_skill_plan(skill_plan) is None


@pytest.mark.parametrize(
    "ad_id",
    [
        "active_directory.user.inspect",
        "active_directory.group.inspect",
        "active_directory.group_membership.inspect",
    ],
)
def test_select_inspector_for_skill_plan_accepts_active_directory_ids(ad_id):
    skill_plan = f"""
- Skill match: none

## Automation handoff

- Suggested inspector tools: {ad_id}
"""

    selection = select_inspector_for_skill_plan(skill_plan)

    assert selection == SkillPlanInspectorSelection(
        inspector_id=ad_id,
        source="suggested_inspector_tools",
    )


@pytest.mark.parametrize(
    "granular_id, expected",
    [
        ("active_directory.user.lookup", "active_directory.user.inspect"),
        (
            "active_directory.user.get_properties",
            "active_directory.user.inspect",
        ),
        ("active_directory.group.lookup", "active_directory.group.inspect"),
        (
            "active_directory.group_membership.lookup",
            "active_directory.group_membership.inspect",
        ),
        (
            "active_directory.group_membership.check",
            "active_directory.group_membership.inspect",
        ),
    ],
)
def test_normalize_inspector_id_maps_active_directory_aliases(
    granular_id, expected
):
    assert normalize_inspector_id(granular_id) == expected


def test_normalize_inspector_id_does_not_map_group_get_members_to_membership_inspect():
    # `group.get_members` implies enumerating all members, which the
    # group_membership inspector does not do. Keep it un-aliased so the skill
    # plan does not falsely promise full member listing.
    assert normalize_inspector_id("active_directory.group.get_members") == (
        "active_directory.group.get_members"
    )


def test_build_inspector_request_for_active_directory_user_uses_upn():
    skill_plan = """
## Extracted inputs

- field: user_principal_name
  status: present
  value: user@example.com
  evidence: saved context
  needed_now: yes
"""

    request = build_inspector_request_from_skill_plan(
        request_id="55948",
        skill_plan_text=skill_plan,
        inspector_id="active_directory.user.inspect",
    )

    assert request.inspector == "active_directory.user.inspect"
    assert request.target.type == "active_directory_user"
    assert request.target.id == "user@example.com"
    assert request.inputs["user_identifier"] == "user@example.com"


def test_build_inspector_request_for_active_directory_group_uses_group_name():
    skill_plan = """
## Extracted inputs

- field: group_name
  status: present
  value: Engineers
  evidence: saved context
  needed_now: yes
"""

    request = build_inspector_request_from_skill_plan(
        request_id="55948",
        skill_plan_text=skill_plan,
        inspector_id="active_directory.group.inspect",
    )

    assert request.inspector == "active_directory.group.inspect"
    assert request.target.type == "active_directory_group"
    assert request.target.id == "Engineers"
    assert request.inputs["group_identifier"] == "Engineers"


def test_build_inspector_request_for_group_membership_requires_user_and_group():
    skill_plan = """
## Extracted inputs

- field: user_principal_name
  status: present
  value: user@example.com
  evidence: saved context
  needed_now: yes

- field: group_name
  status: present
  value: Engineers
  evidence: saved context
  needed_now: yes
"""

    request = build_inspector_request_from_skill_plan(
        request_id="55948",
        skill_plan_text=skill_plan,
        inspector_id="active_directory.group_membership.inspect",
    )

    assert request.inspector == "active_directory.group_membership.inspect"
    assert request.target.type == "active_directory_group_membership"
    assert request.target.id == "user@example.com@Engineers"
    assert request.inputs["user_identifier"] == "user@example.com"
    assert request.inputs["group_identifier"] == "Engineers"


def test_build_inspector_request_group_membership_rejects_when_inputs_missing():
    skill_plan = """
## Extracted inputs

- field: user_principal_name
  status: missing
  value:
  evidence: none
  needed_now: yes
"""

    with pytest.raises(
        ValueError,
        match="missing user and/or group identifier",
    ):
        build_inspector_request_from_skill_plan(
            request_id="55948",
            skill_plan_text=skill_plan,
            inspector_id="active_directory.group_membership.inspect",
        )


def test_select_inspector_for_skill_plan_normalizes_suggested_granular_ids():
    skill_plan = """
- Skill match: none

## Automation handoff

- Suggested inspector tools: exchange.mailbox.get_properties, exchange.mailbox.get_statistics
"""

    selection = select_inspector_for_skill_plan(skill_plan)

    assert selection == SkillPlanInspectorSelection(
        inspector_id="exchange.mailbox.inspect",
        source="suggested_inspector_tools",
    )


def test_select_supported_inspector_tools_preserves_order_and_dedupes():
    selected = select_supported_inspector_tools(
        [
            "active_directory.user.inspect",
            "active_directory.group.inspect",
            "active_directory.group_membership.inspect",
            "active_directory.user.lookup",  # alias of user.inspect
            "exchange.mailbox.get_statistics",  # alias of mailbox.inspect
            "exchange.mailbox.inspect",
            "active_directory.group.inspect",  # duplicate
        ]
    )

    assert selected == [
        "active_directory.user.inspect",
        "active_directory.group.inspect",
        "active_directory.group_membership.inspect",
        "exchange.mailbox.inspect",
    ]


def test_select_supported_inspector_tools_returns_empty_when_none_supported():
    selected = select_supported_inspector_tools(
        [
            "exchange.shared_mailbox.get_full_access_permissions",
            "exchange.shared_mailbox.grant_full_access",
        ]
    )

    assert selected == []


def test_select_inspectors_for_skill_plan_returns_all_supported_in_order():
    skill_plan = """
- Skill match: none

## Automation handoff

- Suggested inspector tools: active_directory.user.inspect, active_directory.group.inspect, active_directory.group_membership.inspect
"""

    selections = select_inspectors_for_skill_plan(skill_plan)

    assert [selection.inspector_id for selection in selections] == [
        "active_directory.user.inspect",
        "active_directory.group.inspect",
        "active_directory.group_membership.inspect",
    ]
    assert all(
        selection.source == "suggested_inspector_tools" for selection in selections
    )


def test_select_inspectors_for_skill_plan_dedupes_aliases():
    skill_plan = """
- Skill match: none

## Automation handoff

- Suggested inspector tools: active_directory.user.lookup, active_directory.user.inspect, exchange.mailbox.get_statistics, exchange.mailbox.inspect
"""

    selections = select_inspectors_for_skill_plan(skill_plan)

    assert [selection.inspector_id for selection in selections] == [
        "active_directory.user.inspect",
        "exchange.mailbox.inspect",
    ]


def test_select_inspectors_for_skill_plan_falls_back_to_skill_match_when_none_supported():
    skill_plan = """
- Skill match: exchange.mailbox.inspect

## Automation handoff

- Suggested inspector tools: exchange.shared_mailbox.get_full_access_permissions
"""

    selections = select_inspectors_for_skill_plan(skill_plan)

    assert selections == [
        SkillPlanInspectorSelection(
            inspector_id="exchange.mailbox.inspect",
            source="skill_match",
        )
    ]


def test_select_inspectors_for_skill_plan_returns_empty_when_no_supported_anywhere():
    skill_plan = """
- Skill match: active_directory.user.provision_standard_account

## Automation handoff

- Suggested inspector tools: none
"""

    assert select_inspectors_for_skill_plan(skill_plan) == []


def test_inspection_only_no_match_plan_can_build_all_three_ad_inspector_requests():
    """No-match AD inspection plan with target_user + target_group must
    produce buildable requests for all three AD inspectors."""

    skill_plan = """
## Metadata

- Skill match: none
- Skill relevance: no_match

## Extracted inputs

- field: target_user
  status: present
  value: name.surname@example.com
  evidence: saved context
  needed_now: yes

- field: target_group
  status: present
  value: usr.podpis.test
  evidence: saved context
  needed_now: yes

## Automation handoff

- Ready for inspection: yes
- Suggested inspector tools: active_directory.user.inspect, active_directory.group.inspect, active_directory.group_membership.inspect
"""

    selections = select_inspectors_for_skill_plan(skill_plan)

    assert [s.inspector_id for s in selections] == [
        "active_directory.user.inspect",
        "active_directory.group.inspect",
        "active_directory.group_membership.inspect",
    ]

    user_request = build_inspector_request_from_skill_plan(
        request_id="55948",
        skill_plan_text=skill_plan,
        inspector_id="active_directory.user.inspect",
    )
    group_request = build_inspector_request_from_skill_plan(
        request_id="55948",
        skill_plan_text=skill_plan,
        inspector_id="active_directory.group.inspect",
    )
    membership_request = build_inspector_request_from_skill_plan(
        request_id="55948",
        skill_plan_text=skill_plan,
        inspector_id="active_directory.group_membership.inspect",
    )

    assert user_request.target.id == "name.surname@example.com"
    assert group_request.target.id == "usr.podpis.test"
    assert membership_request.inputs["user_identifier"] == "name.surname@example.com"
    assert membership_request.inputs["group_identifier"] == "usr.podpis.test"


def test_build_inspector_request_reports_per_inspector_failure_when_inputs_missing():
    skill_plan_user_only = """
## Extracted inputs

- field: target_user
  status: present
  value: name.surname@example.com
  evidence: saved context
  needed_now: yes
"""

    # User inspector: builds because user identifier is present.
    user_request = build_inspector_request_from_skill_plan(
        request_id="55948",
        skill_plan_text=skill_plan_user_only,
        inspector_id="active_directory.user.inspect",
    )

    assert user_request.target.id == "name.surname@example.com"

    # Group inspector: missing target_group must surface a clear error
    # naming the missing input rather than crashing the whole flow.
    with pytest.raises(ValueError, match="missing group_name"):
        build_inspector_request_from_skill_plan(
            request_id="55948",
            skill_plan_text=skill_plan_user_only,
            inspector_id="active_directory.group.inspect",
        )

    # Membership inspector: missing group identifier must surface the
    # combined "user and/or group" error.
    with pytest.raises(ValueError, match="user and/or group identifier"):
        build_inspector_request_from_skill_plan(
            request_id="55948",
            skill_plan_text=skill_plan_user_only,
            inspector_id="active_directory.group_membership.inspect",
        )


# --------------------- Parsed-plan inspector selection ------------------


def _make_parsed_plan(
    *,
    metadata: dict[str, str] | None = None,
    suggested_inspector_tools: list[str] | None = None,
) -> ParsedServiceDeskSkillPlan:
    return ParsedServiceDeskSkillPlan(
        metadata=metadata or {},
        automation_handoff=SkillPlanAutomationHandoff(
            ready_for_inspection="yes",
            ready_for_execution="no",
            suggested_inspector_tools=list(suggested_inspector_tools or []),
            suggested_execute_tools=[],
            automation_blocker=None,
        ),
    )


def test_select_inspectors_for_parsed_skill_plan_returns_supported_in_order():
    plan = _make_parsed_plan(
        suggested_inspector_tools=[
            "active_directory.user.inspect",
            "active_directory.group.inspect",
            "active_directory.group_membership.inspect",
        ],
    )

    selections = select_inspectors_for_parsed_skill_plan(plan)

    assert [selection.inspector_id for selection in selections] == [
        "active_directory.user.inspect",
        "active_directory.group.inspect",
        "active_directory.group_membership.inspect",
    ]
    assert all(
        selection.source == "suggested_inspector_tools"
        for selection in selections
    )


def test_select_inspectors_for_parsed_skill_plan_normalizes_and_dedupes():
    plan = _make_parsed_plan(
        suggested_inspector_tools=[
            "active_directory.user.lookup",
            "active_directory.user.inspect",
            "exchange.mailbox.get_statistics",
            "exchange.mailbox.inspect",
        ],
    )

    selections = select_inspectors_for_parsed_skill_plan(plan)

    assert [selection.inspector_id for selection in selections] == [
        "active_directory.user.inspect",
        "exchange.mailbox.inspect",
    ]


def test_select_inspectors_for_parsed_skill_plan_falls_back_to_skill_match():
    plan = _make_parsed_plan(
        metadata={"Skill match": "exchange.mailbox.inspect"},
        suggested_inspector_tools=[
            "exchange.shared_mailbox.get_full_access_permissions",
        ],
    )

    selections = select_inspectors_for_parsed_skill_plan(plan)

    assert selections == [
        SkillPlanInspectorSelection(
            inspector_id="exchange.mailbox.inspect",
            source="skill_match",
        )
    ]


def test_select_inspectors_for_parsed_skill_plan_accepts_snake_case_skill_match():
    plan = _make_parsed_plan(
        metadata={"skill_match": "active_directory.user.inspect"},
        suggested_inspector_tools=[],
    )

    selections = select_inspectors_for_parsed_skill_plan(plan)

    assert selections == [
        SkillPlanInspectorSelection(
            inspector_id="active_directory.user.inspect",
            source="skill_match",
        )
    ]


def test_select_inspectors_for_parsed_skill_plan_returns_empty_when_no_supported():
    plan = _make_parsed_plan(
        metadata={"Skill match": "active_directory.user.provision_standard_account"},
        suggested_inspector_tools=[],
    )

    assert select_inspectors_for_parsed_skill_plan(plan) == []


def test_select_inspectors_for_parsed_skill_plan_unsupported_tool_falls_back_or_empty():
    """An unsupported suggested tool must not be returned. With a
    supported skill_match, fall back; without one, return empty.
    """
    plan_with_match = _make_parsed_plan(
        metadata={"Skill match": "active_directory.user.inspect"},
        suggested_inspector_tools=[
            "exchange.shared_mailbox.update_full_access_permissions",
        ],
    )

    selections = select_inspectors_for_parsed_skill_plan(plan_with_match)
    assert selections == [
        SkillPlanInspectorSelection(
            inspector_id="active_directory.user.inspect",
            source="skill_match",
        )
    ]

    plan_no_match = _make_parsed_plan(
        metadata={},
        suggested_inspector_tools=[
            "exchange.shared_mailbox.update_full_access_permissions",
        ],
    )

    assert select_inspectors_for_parsed_skill_plan(plan_no_match) == []


# --------------------- Parsed-plan request building ---------------------


def _matches_markdown_request(
    *,
    request_id: str,
    skill_plan_text: str,
    inspector_id: str,
):
    """Build the same request via Markdown and parsed-plan paths and
    assert they are equal. Returns the parsed-plan request for further
    assertions.
    """
    markdown_request = build_inspector_request_from_skill_plan(
        request_id=request_id,
        skill_plan_text=skill_plan_text,
        inspector_id=inspector_id,
    )

    plan = parse_servicedesk_skill_plan(skill_plan_text)
    parsed_request = build_inspector_request_from_parsed_skill_plan(
        request_id=request_id,
        plan=plan,
        inspector_id=inspector_id,
    )

    assert parsed_request == markdown_request
    return parsed_request


def test_parsed_request_matches_markdown_for_exchange_mailbox():
    skill_plan = """
## Extracted inputs

- field: mailbox_address
  status: present
  value: user@example.com
  evidence: saved context
  needed_now: yes

## Automation handoff

- Suggested inspector tools: exchange.mailbox.inspect
"""

    request = _matches_markdown_request(
        request_id="55948",
        skill_plan_text=skill_plan,
        inspector_id="exchange.mailbox.inspect",
    )

    assert isinstance(request, InspectorRequest)
    assert request.target.id == "user@example.com"
    assert request.inputs["mailbox_address"] == "user@example.com"


def test_parsed_request_matches_markdown_for_exchange_target_user_fallback():
    skill_plan = """
## Extracted inputs

- field: target_user
  status: present
  value: user@example.com
  evidence: saved context
  needed_now: yes
"""

    request = _matches_markdown_request(
        request_id="55948",
        skill_plan_text=skill_plan,
        inspector_id="exchange.mailbox.inspect",
    )
    assert request.target.id == "user@example.com"


def test_parsed_request_matches_markdown_for_ad_user_with_upn():
    skill_plan = """
## Extracted inputs

- field: user_principal_name
  status: present
  value: name.surname@example.com
  evidence: saved context
  needed_now: yes
"""

    request = _matches_markdown_request(
        request_id="56050",
        skill_plan_text=skill_plan,
        inspector_id="active_directory.user.inspect",
    )
    assert request.target.type == "active_directory_user"
    assert request.target.id == "name.surname@example.com"
    assert request.inputs["user_identifier"] == "name.surname@example.com"


def test_parsed_request_matches_markdown_for_ad_user_with_target_user_email():
    skill_plan = """
## Extracted inputs

- field: target_user_email
  status: present
  value: name.surname@example.com
  evidence: saved context
  needed_now: yes
"""

    request = _matches_markdown_request(
        request_id="56050",
        skill_plan_text=skill_plan,
        inspector_id="active_directory.user.inspect",
    )
    assert request.target.id == "name.surname@example.com"
    assert request.inputs["user_identifier"] == "name.surname@example.com"


def test_parsed_request_matches_markdown_for_ad_group():
    skill_plan = """
## Extracted inputs

- field: group_name
  status: present
  value: usr.podpis.test
  evidence: saved context
  needed_now: yes
"""

    request = _matches_markdown_request(
        request_id="56050",
        skill_plan_text=skill_plan,
        inspector_id="active_directory.group.inspect",
    )
    assert request.target.type == "active_directory_group"
    assert request.target.id == "usr.podpis.test"
    assert request.inputs["group_identifier"] == "usr.podpis.test"


def test_parsed_request_matches_markdown_for_ad_group_membership():
    skill_plan = """
## Extracted inputs

- field: target_user
  status: present
  value: name.surname@example.com
  evidence: saved context
  needed_now: yes

- field: target_group
  status: present
  value: usr.podpis.test
  evidence: saved context
  needed_now: yes
"""

    request = _matches_markdown_request(
        request_id="56050",
        skill_plan_text=skill_plan,
        inspector_id="active_directory.group_membership.inspect",
    )
    assert request.target.type == "active_directory_group_membership"
    assert request.target.id == "name.surname@example.com@usr.podpis.test"
    assert request.inputs["user_identifier"] == "name.surname@example.com"
    assert request.inputs["group_identifier"] == "usr.podpis.test"


def test_parsed_request_raises_when_required_input_missing_for_exchange():
    plan = parse_servicedesk_skill_plan(
        """
## Extracted inputs

- field: mailbox_address
  status: missing
  value:
  evidence: none
  needed_now: yes
"""
    )

    with pytest.raises(ValueError, match="missing mailbox_address"):
        build_inspector_request_from_parsed_skill_plan(
            request_id="55948",
            plan=plan,
            inspector_id="exchange.mailbox.inspect",
        )


def test_parsed_request_raises_when_required_input_missing_for_ad_user():
    plan = parse_servicedesk_skill_plan(
        """
## Extracted inputs

- field: target_user
  status: missing
  value:
  evidence: none
  needed_now: yes
"""
    )

    with pytest.raises(ValueError, match="missing user_principal_name"):
        build_inspector_request_from_parsed_skill_plan(
            request_id="56050",
            plan=plan,
            inspector_id="active_directory.user.inspect",
        )


def test_parsed_request_raises_when_inspector_unsupported():
    plan = parse_servicedesk_skill_plan("")

    with pytest.raises(ValueError, match="Unsupported inspector"):
        build_inspector_request_from_parsed_skill_plan(
            request_id="55948",
            plan=plan,
            inspector_id="exchange.shared_mailbox.get_full_access_permissions",
        )


def test_parsed_request_raises_when_group_membership_missing_inputs():
    user_only_plan = parse_servicedesk_skill_plan(
        """
## Extracted inputs

- field: target_user
  status: present
  value: name.surname@example.com
  evidence: saved context
  needed_now: yes
"""
    )

    with pytest.raises(
        ValueError, match="missing user and/or group identifier"
    ):
        build_inspector_request_from_parsed_skill_plan(
            request_id="56050",
            plan=user_only_plan,
            inspector_id="active_directory.group_membership.inspect",
        )


def test_parsed_request_strips_backticks_in_values_like_markdown_path():
    """Markdown parser strips backticks from values; the parser feeding
    the parsed-plan path also strips backticks. The two paths must
    produce identical requests for backtick-quoted values.
    """
    skill_plan = """
## Extracted inputs

- field: target_user_email
  status: present
  value: `name.surname@example.com`
  evidence: saved context
  needed_now: yes
"""

    request = _matches_markdown_request(
        request_id="56050",
        skill_plan_text=skill_plan,
        inspector_id="active_directory.user.inspect",
    )
    assert request.inputs["user_identifier"] == "name.surname@example.com"


def test_parsed_request_skill_plan_inputs_match_markdown_serialization():
    """The `skill_plan_inputs` payload serialized inside `inputs` must
    match the Markdown path exactly so downstream consumers cannot tell
    the two sources apart.
    """
    skill_plan = """
## Extracted inputs

- field: mailbox_address
  status: present
  value: user@example.com
  evidence: saved context
  needed_now: yes

- field: approval_status
  status: unclear
  value:
  evidence: no explicit approval visible
  needed_now: yes

- field: effective_date
  status: not_needed_now
  value:
  evidence: no effective date needed
  needed_now: no
"""

    parsed_request = _matches_markdown_request(
        request_id="55948",
        skill_plan_text=skill_plan,
        inspector_id="exchange.mailbox.inspect",
    )

    assert parsed_request.inputs["skill_plan_inputs"] == {
        "mailbox_address": {
            "field": "mailbox_address",
            "status": "present",
            "value": "user@example.com",
            "evidence": "saved context",
            "needed_now": True,
        },
        "approval_status": {
            "field": "approval_status",
            "status": "unclear",
            "value": "",
            "evidence": "no explicit approval visible",
            "needed_now": True,
        },
        "effective_date": {
            "field": "effective_date",
            "status": "not_needed_now",
            "value": "",
            "evidence": "no effective date needed",
            "needed_now": False,
        },
    }


def test_parsed_request_handles_directly_constructed_plan():
    """Directly constructed ParsedServiceDeskSkillPlan (no Markdown
    parsing) should also produce a valid request, using the existing
    `ExtractedInput` shape with string `needed_now`.
    """
    plan = ParsedServiceDeskSkillPlan(
        metadata={},
        extracted_inputs=[
            ExtractedInput(
                field="user_principal_name",
                status="present",
                value="name.surname@example.com",
                evidence="from request body",
                needed_now="yes",
            )
        ],
        automation_handoff=SkillPlanAutomationHandoff(
            ready_for_inspection="yes",
            ready_for_execution="no",
            suggested_inspector_tools=["active_directory.user.inspect"],
            suggested_execute_tools=[],
        ),
    )

    request = build_inspector_request_from_parsed_skill_plan(
        request_id="56050",
        plan=plan,
        inspector_id="active_directory.user.inspect",
    )

    assert request.inspector == "active_directory.user.inspect"
    assert request.target.id == "name.surname@example.com"
    assert request.inputs["user_identifier"] == "name.surname@example.com"
    assert request.inputs["skill_plan_inputs"]["user_principal_name"][
        "needed_now"
    ] is True
