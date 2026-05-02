SERVICEDESK_CONTEXT_WORKFLOW = (
    "Use this workflow:\n"
    "1. Read the request details.\n"
    "2. Read request notes.\n"
    "3. Read attachment metadata. Do not download or inspect attachment contents.\n"
    "4. Read request conversations.\n"
    "5. When conversation entries include content_url values and the content is needed, "
    "fetch the conversation content.\n\n"
)

SERVICEDESK_READ_ONLY_RULES = (
    "Important rules:\n"
    "- Use only read-only ServiceDesk tools.\n"
    "- Do not update ServiceDesk.\n"
    "- Do not add notes.\n"
    "- Do not send replies.\n"
    "- Do not execute commands.\n"
    "- Do not claim attachment contents were inspected.\n"
)

SERVICEDESK_CHRONOLOGY_RULES = (
    "Chronology rules:\n"
    "- Analyze the ticket chronologically. Later requester/technician messages may "
    "resolve or supersede earlier missing-information requests.\n"
    "- Do not list information as missing if a later conversation entry appears to "
    "provide or resolve it.\n"
    "- If an earlier question was answered later, mention it as resolved instead of "
    "listing it under Missing information.\n"
)

SERVICEDESK_DRAFT_REPLY_TONE_GUIDANCE = (
    "Tone guidance:\n"
    "- Be friendly, professional, and helpful.\n"
    "- Match the requester's language and formality. For example, if the requester writes "
    "casually, use a casual but professional tone.\n"
    "- Do not use automatic honorifics like Pan/Pani or Mr/Ms/Mrs unless the conversation "
    "already uses them.\n"
    "- Keep replies concise. Provide just enough detail for clarity.\n\n"
)

SERVICEDESK_DRAFT_REPLY_LANGUAGE_GUIDANCE = (
    "Language guidance:\n"
    "- Write the requester-facing draft reply in the same language as the requester-facing ticket conversation when clear.\n"
    "- If the requester wrote in Polish, draft the reply in Polish.\n"
    "- If the requester wrote in English, draft the reply in English.\n"
    "- If the conversation contains both Polish and English, prefer the language used by the requester in the latest requester-facing message.\n"
    "- If the requester language is unclear, use English only if the ticket content or company context does not clearly indicate Polish.\n"
    "- Do not switch languages mid-reply unless the existing conversation clearly does that.\n\n"
)


def format_allowed_labels(labels: list[str]) -> str:
    return ", ".join(f"`{label}`" for label in labels)


def format_allowed_label_section(title: str, labels: list[str]) -> str:
    return f"{title}:\n{format_allowed_labels(labels)}\n\n"
