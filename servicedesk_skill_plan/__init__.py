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
from servicedesk_skill_plan.persistence import (
    SkillPlanValidationPersistenceResult,
    build_persisting_validation_callback,
    persist_and_format_skill_plan_validation,
    persist_skill_plan_validation_payload,
    validate_skill_plan_text_for_persistence,
)
from servicedesk_skill_plan.validation import (
    INSPECTOR_BOUND_FIELD_NAMES,
    SUPPORTED_INSPECTOR_TOOL_IDS,
    UNSUPPORTED_HYPOTHETICAL_EXECUTE_TOOL_IDS,
    SkillPlanValidationDisplayResult,
    SkillPlanValidationFinding,
    format_skill_plan_validation_findings,
    validate_servicedesk_skill_plan,
    validate_skill_plan_text_as_lines,
    validate_skill_plan_text_for_inspection,
)

__all__ = [
    "ExtractedInput",
    "INSPECTOR_BOUND_FIELD_NAMES",
    "ParsedServiceDeskSkillPlan",
    "SUPPORTED_INSPECTOR_TOOL_IDS",
    "SkillPlanAutomationHandoff",
    "SkillPlanValidationDisplayResult",
    "SkillPlanValidationFinding",
    "SkillPlanValidationPersistenceResult",
    "UNSUPPORTED_HYPOTHETICAL_EXECUTE_TOOL_IDS",
    "build_persisting_validation_callback",
    "format_skill_plan_validation_findings",
    "parse_servicedesk_skill_plan",
    "persist_and_format_skill_plan_validation",
    "persist_skill_plan_validation_payload",
    "validate_servicedesk_skill_plan",
    "validate_skill_plan_text_as_lines",
    "validate_skill_plan_text_for_inspection",
    "validate_skill_plan_text_for_persistence",
]
