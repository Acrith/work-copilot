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
            inspector_id="active_directory.user.lookup",
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
            "active_directory.user.lookup",
            "exchange.mailbox.inspect",
        ]
    )

    assert selected == "exchange.mailbox.inspect"


def test_select_supported_inspector_tool_returns_none_when_no_supported_tool():
    selected = select_supported_inspector_tool(
        [
            "active_directory.user.lookup",
            "exchange.shared_mailbox.get_full_access_permissions",
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
    assert normalize_inspector_id("active_directory.user.lookup") == (
        "active_directory.user.lookup"
    )


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