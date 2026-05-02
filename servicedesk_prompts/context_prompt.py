from servicedesk_prompts.common import (
    SERVICEDESK_CHRONOLOGY_RULES,
    SERVICEDESK_CONTEXT_WORKFLOW,
    SERVICEDESK_READ_ONLY_RULES,
    format_allowed_label_section,
)
from servicedesk_prompts.labels import (
    AUTOMATION_CANDIDATE_LABELS,
    CONFIDENCE_LABELS,
    CURRENT_STATE_LABELS,
    REPLY_INTENT_LABELS,
    REPLY_RECOMMENDED_LABELS,
    RISK_LEVEL_LABELS,
)


def build_servicedesk_context_prompt(request_id: str) -> str:
    return (
        f"Prepare a ServiceDesk context summary for request {request_id}.\n\n"
        f"{SERVICEDESK_CONTEXT_WORKFLOW}"
        "Return a concise but useful context summary. Focus on what happened, current state, "
        "who is waiting on whom, and the safest next action.\n\n"
        "Use one of the allowed labels exactly. If none fits safely, use `unclear` and "
        "explain why in Safety notes.\n\n"
        f"{format_allowed_label_section('Allowed current_state labels', CURRENT_STATE_LABELS)}"
        f"{format_allowed_label_section('Allowed reply_recommended labels', REPLY_RECOMMENDED_LABELS)}"
        f"{format_allowed_label_section('Allowed reply_intent labels', REPLY_INTENT_LABELS)}"
        f"{format_allowed_label_section('Allowed confidence labels', CONFIDENCE_LABELS)}"
        f"{format_allowed_label_section('Allowed automation_candidate labels', AUTOMATION_CANDIDATE_LABELS)}"
        f"{format_allowed_label_section('Allowed risk_level labels', RISK_LEVEL_LABELS)}"
        "Include the original ServiceDesk request subject in Metadata as `request_subject`. "
        "Use the subject exactly as shown in the request details when available. "
        "Do not invent, translate, summarize, or rewrite the subject.\n\n"
        "Use this output structure:\n\n"
        "# ServiceDesk request context\n\n"
        "## Metadata\n\n"
        f"- request_id: {request_id}\n"
        "- request_subject: <original ServiceDesk request subject exactly as shown in request details, or unclear>\n\n"
        "## Current state\n\n"
        "<one allowed current_state label>\n\n"
        "## Confidence\n\n"
        "<one allowed confidence label>\n\n"
        "## Reply recommended\n\n"
        "<one allowed reply_recommended label>\n\n"
        "## Possible reply intent\n\n"
        "<one allowed reply_intent label>\n\n"
        "## Summary\n\n"
        "<summarize the request and relevant conversation history>\n\n"
        "## Latest known activity\n\n"
        "<summarize the newest meaningful requester/technician activity>\n\n"
        "## Suggested next action\n\n"
        "<recommend the safest next action>\n\n"
        "## Missing information\n\n"
        "- <list missing details, or write `none`>\n\n"
        "## Resolved earlier questions\n\n"
        "- <list earlier blockers/questions resolved by later conversation entries, "
        "or write `none`>\n\n"
        "## Automation candidate\n\n"
        "<one allowed automation_candidate label>\n\n"
        "## Risk level\n\n"
        "<one allowed risk_level label>\n\n"
        "## Context inspected\n\n"
        "- request details: yes/no\n"
        "- notes: yes/no\n"
        "- attachment metadata: yes/no\n"
        "- conversations: yes/no\n"
        "- conversation content: yes/no\n\n"
        "## Safety notes\n\n"
        "<mention uncertainty, missing information, risky assumptions, or attachments that "
        "exist but were not inspected>\n\n"
        "Consistency rules:\n"
        "- If `Reply recommended` is `no`, use `Possible reply intent` = "
        "`no_reply_recommended` unless there is a clear reason not to.\n"
        "- If `Current state` is `waiting_for_requester`, decide whether a follow-up is "
        "actually needed now. Waiting does not automatically mean a reply is required.\n"
        "- Do not claim work is being investigated unless ticket assignment, status, notes, "
        "or conversations support that.\n"
        "- Use `Resolved earlier questions` for earlier asks that were answered or made "
        "irrelevant by later conversation entries.\n\n"
        f"{SERVICEDESK_CHRONOLOGY_RULES}\n"
        f"{SERVICEDESK_READ_ONLY_RULES}"
    )
