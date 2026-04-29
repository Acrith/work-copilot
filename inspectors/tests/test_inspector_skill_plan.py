import pytest

from inspectors.models import InspectorRequest
from inspectors.skill_plan import (
    SkillPlanInput,
    build_inspector_request_from_skill_plan,
    parse_extracted_inputs,
    parse_suggested_inspector_tools,
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