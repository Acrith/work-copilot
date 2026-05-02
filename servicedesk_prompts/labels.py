CURRENT_STATE_LABELS = [
    "not_yet_processed",
    "needs_work",
    "waiting_for_requester",
    "waiting_for_internal",
    "ready_to_close",
    "blocked",
    "risky_manual",
    "unclear",
]

REPLY_INTENT_LABELS = [
    "ask_info",
    "confirm_resolution",
    "completed",
    "follow_up",
    "explain_limitation",
    "handoff_or_escalate",
    "no_reply_recommended",
    "unclear",
]

REPLY_RECOMMENDED_LABELS = [
    "yes",
    "no",
    "unclear",
]

CONFIDENCE_LABELS = [
    "low",
    "medium",
    "high",
]

AUTOMATION_CANDIDATE_LABELS = [
    "no",
    "partial",
    "yes",
]

CAPABILITY_CLASSIFICATION_LABELS = [
    "read_only_inspection_now",
    "draft_only_manual_now",
    "blocked_missing_information",
    "unsupported_no_safe_capability",
    "future_automation_candidate",
]

RISK_LEVEL_LABELS = [
    "low",
    "medium",
    "high",
    "risky",
]
