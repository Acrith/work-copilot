"""Code-backed parser and validator for generated ServiceDesk skill plans.

These modules consume the Markdown plans produced by
build_servicedesk_skill_plan_prompt(...) and surface findings without
depending on prompt wording alone for correctness. They are not yet
wired into the TUI or runtime — this layer is currently for tests and
future guardrails only.
"""

from servicedesk_skill_plan.models import (
    ExtractedInput,
    ParsedServiceDeskSkillPlan,
    SkillPlanAutomationHandoff,
)
from servicedesk_skill_plan.parser import parse_servicedesk_skill_plan
from servicedesk_skill_plan.validation import (
    INSPECTOR_BOUND_FIELD_NAMES,
    SUPPORTED_INSPECTOR_TOOL_IDS,
    UNSUPPORTED_HYPOTHETICAL_EXECUTE_TOOL_IDS,
    SkillPlanValidationFinding,
    validate_servicedesk_skill_plan,
)

__all__ = [
    "ExtractedInput",
    "INSPECTOR_BOUND_FIELD_NAMES",
    "ParsedServiceDeskSkillPlan",
    "SUPPORTED_INSPECTOR_TOOL_IDS",
    "SkillPlanAutomationHandoff",
    "SkillPlanValidationFinding",
    "UNSUPPORTED_HYPOTHETICAL_EXECUTE_TOOL_IDS",
    "parse_servicedesk_skill_plan",
    "validate_servicedesk_skill_plan",
]
