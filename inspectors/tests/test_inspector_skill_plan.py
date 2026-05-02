import pytest

from inspectors.models import InspectorRequest
from inspectors.skill_plan import (
    SkillPlanInput,
    SkillPlanInspectorSelection,
    build_inspector_request_from_skill_plan,
    normalize_inspector_id,
    parse_extracted_inputs,
    parse_skill_match,
    parse_suggested_inspector_tools,
    select_inspector_for_skill_plan,
    select_supported_inspector_tool,
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