from servicedesk_skill_plan import (
    ExtractedInput,
    parse_servicedesk_skill_plan,
)


def _ad_inspection_plan() -> str:
    return """\
# ServiceDesk skill plan

## Metadata

- Ticket: 56104
- Skill match: none
- Skill relevance: no_match
- Match confidence: medium
- Work status: not_started
- Current unresolved issue: read-only AD inspection
- Automation status: draft_only
- Capability classification: read_only_inspection_now
- Risk level: low

## Why this skill matches

Read-only AD inspection requested.

## Extracted inputs

- field: target_user
  status: present
  value: name.surname
  evidence: from request body
  needed_now: yes

- field: target_group
  status: present
  value: usr.podpis.test
  evidence: from request body
  needed_now: yes

## Missing information needed now

- none

## Current blocker

none

## Proposed next action

Run `/sdp inspect-skill 56104`.

## Suggested requester reply

none

## Internal work plan

1. Run read-only inspectors.

## Automation handoff

- Ready for inspection: yes
- Ready for execution: no
- Suggested inspector tools: active_directory.user.inspect, active_directory.group.inspect, active_directory.group_membership.inspect
- Suggested execute tools: none
- Automation blocker: none

## Automation readiness

partial, with explanation

## Required approvals

- none

## Forbidden actions

- Do not execute commands.

## Safety notes

none
"""


def test_parses_metadata_capability_classification():
    plan = parse_servicedesk_skill_plan(_ad_inspection_plan())

    assert plan.metadata["Ticket"] == "56104"
    assert plan.metadata["Skill match"] == "none"
    assert plan.metadata["Capability classification"] == "read_only_inspection_now"
    assert plan.metadata["Risk level"] == "low"


def test_parses_extracted_inputs():
    plan = parse_servicedesk_skill_plan(_ad_inspection_plan())

    assert plan.extracted_inputs == [
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
    ]


def test_parses_automation_handoff_tool_lists():
    plan = parse_servicedesk_skill_plan(_ad_inspection_plan())

    handoff = plan.automation_handoff

    assert handoff.ready_for_inspection == "yes"
    assert handoff.ready_for_execution == "no"
    assert handoff.suggested_inspector_tools == [
        "active_directory.user.inspect",
        "active_directory.group.inspect",
        "active_directory.group_membership.inspect",
    ]
    assert handoff.suggested_execute_tools == []
    assert handoff.automation_blocker is None


def test_parses_none_tool_lists_as_empty():
    plan_text = """\
## Automation handoff

- Ready for inspection: no
- Ready for execution: no
- Suggested inspector tools: none
- Suggested execute tools: none
- Automation blocker: none
"""
    plan = parse_servicedesk_skill_plan(plan_text)
    handoff = plan.automation_handoff

    assert handoff.suggested_inspector_tools == []
    assert handoff.suggested_execute_tools == []
    assert handoff.automation_blocker is None
    assert handoff.ready_for_inspection == "no"
    assert handoff.ready_for_execution == "no"


def test_parses_missing_information_and_current_blocker():
    plan_text = """\
## Missing information needed now

- sam_account_name not provided
- distinguished_name not provided

## Current blocker

Need to resolve canonical AD identifier before any update.
"""
    plan = parse_servicedesk_skill_plan(plan_text)

    assert plan.missing_information_needed_now == [
        "sam_account_name not provided",
        "distinguished_name not provided",
    ]
    assert plan.current_blocker == (
        "Need to resolve canonical AD identifier before any update."
    )


def test_parses_tool_lists_with_backticks_and_whitespace():
    plan_text = """\
## Automation handoff

- Ready for inspection: yes
- Ready for execution: no
- Suggested inspector tools: `exchange.mailbox.inspect` ,  `active_directory.user.inspect`
- Suggested execute tools: none
- Automation blocker: none
"""
    plan = parse_servicedesk_skill_plan(plan_text)

    assert plan.automation_handoff.suggested_inspector_tools == [
        "exchange.mailbox.inspect",
        "active_directory.user.inspect",
    ]
