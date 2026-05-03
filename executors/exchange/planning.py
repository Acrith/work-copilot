"""Preview-only planning layer for the Exchange Full Access executor.

Given a parsed ServiceDesk skill plan, this module builds an
`ExecutorRequest` + `ExecutorPreview` for the mock Exchange Full
Access executor. It never executes the executor, never contacts
Exchange, never contacts ServiceDesk, and never registers the
executor globally.

Pure / local: no filesystem access, no network, no model calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from executors.exchange.mailbox_permission import (
    EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID,
    build_exchange_grant_full_access_preview,
    build_exchange_grant_full_access_request,
)
from executors.models import ExecutorPreview, ExecutorRequest
from servicedesk_skill_plan.models import (
    ExtractedInput,
    ParsedServiceDeskSkillPlan,
)

# The canonical skill id from skills/definitions/ is
# `exchange.shared_mailbox.grant_full_access`. The executor id
# `exchange.mailbox_permission.grant_full_access` is also accepted so
# a future skill plan that references the executor directly still
# triggers the same planner.
SUPPORTED_SKILL_IDS: tuple[str, ...] = (
    "exchange.shared_mailbox.grant_full_access",
    EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID,
)

# Mailbox identifier candidates, in priority order. These align with
# the existing skill-definition input name (`shared_mailbox_address`)
# and the inspector-side aliases (`mailbox_address`).
_MAILBOX_FIELDS: tuple[str, ...] = (
    "shared_mailbox_address",
    "mailbox_address",
    "mailbox",
    "target_mailbox",
)

# Trustee identifier candidates, in priority order. The canonical
# skill input is `target_user`.
_TRUSTEE_FIELDS: tuple[str, ...] = (
    "target_user",
    "target_user_email",
    "user_principal_name",
    "trustee",
)

_SKILL_MATCH_METADATA_KEYS: tuple[str, ...] = (
    "Skill match",
    "skill_match",
)


@dataclass(frozen=True)
class ExecutorPlanningResult:
    """Outcome of trying to plan a preview from a parsed skill plan.

    Display-only. Workflow state and `/sdp work` are not changed by
    this PR; consumers can read this result to decide whether to show
    a preview to the operator.
    """

    applicable: bool
    preview: ExecutorPreview | None = None
    request: ExecutorRequest | None = None
    missing_inputs: list[str] = field(default_factory=list)
    unsupported_reason: str | None = None
    warnings: list[str] = field(default_factory=list)


def plan_exchange_grant_full_access_preview_from_skill_plan(
    plan: ParsedServiceDeskSkillPlan,
    *,
    request_id: str,
) -> ExecutorPlanningResult:
    """Build a preview-only planning result for the mock Exchange Full
    Access executor.

    Returns:
    - `applicable=False` when the skill match does not point at a
      Full-Access grant (or there is no skill match).
    - `applicable=True, missing_inputs=[…]` when the skill is right
      but the parsed plan is missing the mailbox or trustee.
    - `applicable=True, request=<…>, preview=<…>` when both are
      present. The preview is structurally approval-required.
    """
    skill_match = _lookup_skill_match(plan)

    if skill_match is None:
        return ExecutorPlanningResult(
            applicable=False,
            unsupported_reason=(
                "Skill plan has no `Skill match` value; cannot plan "
                "an Exchange Full Access preview."
            ),
        )

    if skill_match not in SUPPORTED_SKILL_IDS:
        return ExecutorPlanningResult(
            applicable=False,
            unsupported_reason=(
                f"Skill `{skill_match}` is not supported by the "
                "Exchange Full Access executor planner."
            ),
        )

    present_inputs = _present_inputs_by_field(plan.extracted_inputs)

    mailbox = _first_present_value(present_inputs, _MAILBOX_FIELDS)
    trustee = _first_present_value(present_inputs, _TRUSTEE_FIELDS)

    missing: list[str] = []
    if mailbox is None:
        missing.append("mailbox")
    if trustee is None:
        missing.append("trustee")

    if missing:
        return ExecutorPlanningResult(
            applicable=True,
            missing_inputs=missing,
        )

    auto_mapping = _parse_auto_mapping_preference(
        present_inputs.get("automapping_preference")
    )

    request = build_exchange_grant_full_access_request(
        request_id=request_id,
        mailbox=mailbox,
        trustee=trustee,
        auto_mapping=auto_mapping,
    )
    preview = build_exchange_grant_full_access_preview(request)

    return ExecutorPlanningResult(
        applicable=True,
        request=request,
        preview=preview,
    )


def _lookup_skill_match(plan: ParsedServiceDeskSkillPlan) -> str | None:
    metadata = plan.metadata if isinstance(plan.metadata, dict) else {}
    for key in _SKILL_MATCH_METADATA_KEYS:
        raw = metadata.get(key)
        if isinstance(raw, str):
            cleaned = raw.strip()
            if cleaned and cleaned.lower() != "none":
                return cleaned
    return None


def _present_inputs_by_field(
    extracted_inputs: list[ExtractedInput],
) -> dict[str, ExtractedInput]:
    by_field: dict[str, ExtractedInput] = {}
    for item in extracted_inputs:
        field_name = (item.field or "").strip()
        if field_name:
            by_field[field_name] = item
    return by_field


def _first_present_value(
    present_inputs: dict[str, ExtractedInput],
    field_names: tuple[str, ...],
) -> str | None:
    for field_name in field_names:
        item = present_inputs.get(field_name)
        if item is None:
            continue
        if (item.status or "").strip().lower() != "present":
            continue
        cleaned = (item.value or "").strip()
        if cleaned:
            return cleaned
    return None


def _parse_auto_mapping_preference(
    item: ExtractedInput | None,
) -> bool | None:
    if item is None:
        return None
    if (item.status or "").strip().lower() != "present":
        return None
    cleaned = (item.value or "").strip().lower()
    if cleaned in {"yes", "true", "on", "enable", "enabled"}:
        return True
    if cleaned in {"no", "false", "off", "disable", "disabled"}:
        return False
    return None


__all__ = [
    "ExecutorPlanningResult",
    "SUPPORTED_SKILL_IDS",
    "plan_exchange_grant_full_access_preview_from_skill_plan",
]
