"""Public surface for ServiceDesk prompt builders.

This package was extracted from interactive_commands.py as a mechanical
refactor; prompt wording and behavior are unchanged. interactive_commands.py
re-exports these symbols so existing imports keep working.
"""

from servicedesk_prompts.common import (
    SERVICEDESK_CHRONOLOGY_RULES,
    SERVICEDESK_CONTEXT_WORKFLOW,
    SERVICEDESK_DRAFT_REPLY_LANGUAGE_GUIDANCE,
    SERVICEDESK_DRAFT_REPLY_TONE_GUIDANCE,
    SERVICEDESK_READ_ONLY_RULES,
    format_allowed_label_section,
    format_allowed_labels,
)
from servicedesk_prompts.context_prompt import build_servicedesk_context_prompt
from servicedesk_prompts.labels import (
    AUTOMATION_CANDIDATE_LABELS,
    CAPABILITY_CLASSIFICATION_LABELS,
    CONFIDENCE_LABELS,
    CURRENT_STATE_LABELS,
    REPLY_INTENT_LABELS,
    REPLY_RECOMMENDED_LABELS,
    RISK_LEVEL_LABELS,
)
from servicedesk_prompts.note_prompt import build_servicedesk_draft_note_prompt
from servicedesk_prompts.reply_prompt import build_servicedesk_draft_reply_prompt
from servicedesk_prompts.skill_plan_prompt import (
    build_servicedesk_skill_plan_prompt,
    build_servicedesk_skill_plan_repair_prompt,
)

__all__ = [
    "AUTOMATION_CANDIDATE_LABELS",
    "CAPABILITY_CLASSIFICATION_LABELS",
    "CONFIDENCE_LABELS",
    "CURRENT_STATE_LABELS",
    "REPLY_INTENT_LABELS",
    "REPLY_RECOMMENDED_LABELS",
    "RISK_LEVEL_LABELS",
    "SERVICEDESK_CHRONOLOGY_RULES",
    "SERVICEDESK_CONTEXT_WORKFLOW",
    "SERVICEDESK_DRAFT_REPLY_LANGUAGE_GUIDANCE",
    "SERVICEDESK_DRAFT_REPLY_TONE_GUIDANCE",
    "SERVICEDESK_READ_ONLY_RULES",
    "build_servicedesk_context_prompt",
    "build_servicedesk_draft_note_prompt",
    "build_servicedesk_draft_reply_prompt",
    "build_servicedesk_skill_plan_prompt",
    "build_servicedesk_skill_plan_repair_prompt",
    "format_allowed_label_section",
    "format_allowed_labels",
]
