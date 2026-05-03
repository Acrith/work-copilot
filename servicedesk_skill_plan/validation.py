import re
from dataclasses import dataclass
from typing import Literal

from servicedesk_skill_plan.models import (
    ExtractedInput,
    ParsedServiceDeskSkillPlan,
)
from servicedesk_skill_plan.parser import parse_servicedesk_skill_plan

SUPPORTED_INSPECTOR_TOOL_IDS = frozenset(
    {
        "exchange.mailbox.inspect",
        "active_directory.user.inspect",
        "active_directory.group.inspect",
        "active_directory.group_membership.inspect",
    }
)

UNSUPPORTED_HYPOTHETICAL_EXECUTE_TOOL_IDS = frozenset(
    {
        "active_directory.user.update_attributes",
        "active_directory.group.add_member",
        "active_directory.group.remove_member",
        "active_directory.user.reset_password",
        "exchange.archive.enable",
    }
)

INSPECTOR_BOUND_FIELD_NAMES = frozenset(
    {
        "target_user",
        "target_user_email",
        "user_principal_name",
        "sam_account_name",
        "user_identifier",
        "mailbox_address",
        "shared_mailbox_address",
        "target_group",
        "group_name",
        "group_identifier",
        "distinguished_name",
    }
)

_NON_STRICT_STATUSES = frozenset({"missing", "unclear", "not_needed_now"})

_USER_IDENTIFIER_FIELDS = (
    "target_user",
    "user_identifier",
    "user_principal_name",
    "sam_account_name",
    "target_user_email",
    "distinguished_name",
)

_GROUP_IDENTIFIER_FIELDS = (
    "target_group",
    "group_identifier",
    "group_name",
)

_AD_GROUP_INSPECT_IDENTIFIER_FIELDS = (
    "target_group",
    "group_identifier",
    "group_name",
    "sam_account_name",
    "distinguished_name",
)

_MAILBOX_IDENTIFIER_FIELDS = (
    "mailbox_address",
    "target_user_email",
    "target_user",
    "shared_mailbox_address",
)

_DIRTY_IDENTIFIER_PARENS_RE = re.compile(
    r"\(\s*[^()\s]+@[^()\s]+\s*\)"
)
_DIRTY_IDENTIFIER_ANGLE_RE = re.compile(
    r"<\s*[^<>\s]+@[^<>\s]+\s*>"
)
_PREFIXED_IDENTIFIER_RE = re.compile(
    r"^\s*(user|mailbox|group)\s*:",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SkillPlanValidationFinding:
    severity: Literal["warning", "error"]
    code: str
    message: str


def validate_servicedesk_skill_plan(
    plan: ParsedServiceDeskSkillPlan,
) -> list[SkillPlanValidationFinding]:
    findings: list[SkillPlanValidationFinding] = []

    findings.extend(_check_ready_for_execution(plan))
    findings.extend(_check_suggested_execute_tools(plan))
    findings.extend(_check_supported_inspector_tools(plan))
    findings.extend(_check_no_inspectors_for_future_or_unsupported(plan))
    findings.extend(_check_clean_identifier_values(plan))
    findings.extend(_check_read_only_inspection_now_requires_inspector(plan))
    findings.extend(_check_ready_for_inspection_requires_inspector(plan))
    findings.extend(_check_selected_inspectors_have_required_inputs(plan))

    return findings


# ---- Individual rules ---------------------------------------------------


def _check_ready_for_execution(
    plan: ParsedServiceDeskSkillPlan,
) -> list[SkillPlanValidationFinding]:
    handoff = plan.automation_handoff
    value = handoff.ready_for_execution

    if value is None:
        return []

    if value.strip().lower() == "no":
        return []

    return [
        SkillPlanValidationFinding(
            severity="error",
            code="ready_for_execution_must_be_no",
            message=(
                "Automation handoff `Ready for execution` must be `no`; "
                f"got `{value}`."
            ),
        )
    ]


def _check_suggested_execute_tools(
    plan: ParsedServiceDeskSkillPlan,
) -> list[SkillPlanValidationFinding]:
    tools = plan.automation_handoff.suggested_execute_tools

    if not tools:
        return []

    findings: list[SkillPlanValidationFinding] = []

    for tool in tools:
        if tool in UNSUPPORTED_HYPOTHETICAL_EXECUTE_TOOL_IDS:
            findings.append(
                SkillPlanValidationFinding(
                    severity="error",
                    code="suggested_execute_tools_must_be_none",
                    message=(
                        "Suggested execute tool `"
                        f"{tool}` is unsupported/hypothetical and must "
                        "not appear under `Suggested execute tools`. "
                        "Use `none` while no executor is implemented."
                    ),
                )
            )
            continue

        findings.append(
            SkillPlanValidationFinding(
                severity="error",
                code="suggested_execute_tools_must_be_none",
                message=(
                    "Suggested execute tool `"
                    f"{tool}` is not an implemented, registered, "
                    "approval-gated execute tool. Use `none` while no "
                    "executor is implemented."
                ),
            )
        )

    return findings


def _check_supported_inspector_tools(
    plan: ParsedServiceDeskSkillPlan,
) -> list[SkillPlanValidationFinding]:
    tools = plan.automation_handoff.suggested_inspector_tools

    findings: list[SkillPlanValidationFinding] = []

    for tool in tools:
        if tool in SUPPORTED_INSPECTOR_TOOL_IDS:
            continue

        findings.append(
            SkillPlanValidationFinding(
                severity="error",
                code="supported_inspector_tools_only",
                message=(
                    "Suggested inspector tool `"
                    f"{tool}` is not a registered inspector ID. "
                    "Allowed values: "
                    f"{', '.join(sorted(SUPPORTED_INSPECTOR_TOOL_IDS))}."
                ),
            )
        )

    return findings


def _check_no_inspectors_for_future_or_unsupported(
    plan: ParsedServiceDeskSkillPlan,
) -> list[SkillPlanValidationFinding]:
    classification = plan.metadata.get("Capability classification", "").strip()

    if classification not in {
        "future_automation_candidate",
        "unsupported_no_safe_capability",
    }:
        return []

    if not plan.automation_handoff.suggested_inspector_tools:
        return []

    return [
        SkillPlanValidationFinding(
            severity="error",
            code="no_inspectors_for_future_or_unsupported",
            message=(
                "Capability classification is `"
                f"{classification}` but `Suggested inspector tools` is "
                "non-empty. Inspector tools must NEVER be suggested for "
                "`future_automation_candidate` or "
                "`unsupported_no_safe_capability`."
            ),
        )
    ]


def _check_clean_identifier_values(
    plan: ParsedServiceDeskSkillPlan,
) -> list[SkillPlanValidationFinding]:
    findings: list[SkillPlanValidationFinding] = []

    for extracted in plan.extracted_inputs:
        if extracted.field not in INSPECTOR_BOUND_FIELD_NAMES:
            continue

        finding = _check_one_clean_identifier(extracted)
        if finding is not None:
            findings.append(finding)

    return findings


def _check_one_clean_identifier(
    extracted: ExtractedInput,
) -> SkillPlanValidationFinding | None:
    value = extracted.value.strip()

    if not value:
        # Empty values are okay when the input is intentionally not
        # present yet (missing/unclear/not_needed_now).
        if extracted.status.strip().lower() in _NON_STRICT_STATUSES:
            return None

        return None

    if _PREFIXED_IDENTIFIER_RE.search(value):
        return SkillPlanValidationFinding(
            severity="warning",
            code="clean_identifier_values",
            message=(
                f"Inspector-bound field `{extracted.field}` value "
                f"`{value}` is prefixed with a label like `user:` / "
                "`mailbox:` / `group:`. Use a clean machine identifier "
                "and put labels in `evidence:` instead."
            ),
        )

    if _DIRTY_IDENTIFIER_PARENS_RE.search(
        value
    ) or _DIRTY_IDENTIFIER_ANGLE_RE.search(value):
        return SkillPlanValidationFinding(
            severity="warning",
            code="clean_identifier_values",
            message=(
                f"Inspector-bound field `{extracted.field}` value "
                f"`{value}` looks like a display-name + email wrapper. "
                "Inspector-bound values must be clean machine "
                "identifiers; put display-name combinations in "
                "`identity_confirmation` or `evidence:` instead."
            ),
        )

    return None


def _check_read_only_inspection_now_requires_inspector(
    plan: ParsedServiceDeskSkillPlan,
) -> list[SkillPlanValidationFinding]:
    classification = plan.metadata.get("Capability classification", "").strip()

    if classification != "read_only_inspection_now":
        return []

    if plan.automation_handoff.suggested_inspector_tools:
        return []

    return [
        SkillPlanValidationFinding(
            severity="error",
            code="read_only_inspection_now_requires_inspector",
            message=(
                "Capability classification is `read_only_inspection_now` "
                "but `Suggested inspector tools` is empty. List at least "
                "one registered inspector ID."
            ),
        )
    ]


def _check_ready_for_inspection_requires_inspector(
    plan: ParsedServiceDeskSkillPlan,
) -> list[SkillPlanValidationFinding]:
    handoff = plan.automation_handoff

    if handoff.ready_for_inspection is None:
        return []

    if handoff.ready_for_inspection.strip().lower() != "yes":
        return []

    if handoff.suggested_inspector_tools:
        return []

    return [
        SkillPlanValidationFinding(
            severity="warning",
            code="ready_for_inspection_requires_inspector",
            message=(
                "`Ready for inspection: yes` but `Suggested inspector "
                "tools` is empty. Either list a registered inspector or "
                "set `Ready for inspection: no`."
            ),
        )
    ]


def _check_selected_inspectors_have_required_inputs(
    plan: ParsedServiceDeskSkillPlan,
) -> list[SkillPlanValidationFinding]:
    """Verify each suggested inspector tool has its required identifier
    inputs marked `present` with a non-empty value in `Extracted inputs`.
    """
    present_fields = _present_input_fields(plan.extracted_inputs)
    findings: list[SkillPlanValidationFinding] = []

    for inspector_id in plan.automation_handoff.suggested_inspector_tools:
        message = _missing_inputs_message_for_inspector(
            inspector_id=inspector_id,
            present_fields=present_fields,
        )

        if message is None:
            continue

        findings.append(
            SkillPlanValidationFinding(
                severity="error",
                code="selected_inspectors_require_present_inputs",
                message=message,
            )
        )

    return findings


def _present_input_fields(
    extracted_inputs: list[ExtractedInput],
) -> set[str]:
    present: set[str] = set()

    for extracted in extracted_inputs:
        if extracted.status.strip().lower() != "present":
            continue

        if not extracted.value.strip():
            continue

        normalized_field = extracted.field.strip().lower()

        if not normalized_field:
            continue

        present.add(normalized_field)

    return present


def _missing_inputs_message_for_inspector(
    *,
    inspector_id: str,
    present_fields: set[str],
) -> str | None:
    if inspector_id == "exchange.mailbox.inspect":
        if _any_present(_MAILBOX_IDENTIFIER_FIELDS, present_fields):
            return None
        return (
            "Inspector exchange.mailbox.inspect requires a present "
            "mailbox identifier input."
        )

    if inspector_id == "active_directory.user.inspect":
        if _any_present(_USER_IDENTIFIER_FIELDS, present_fields):
            return None
        return (
            "Inspector active_directory.user.inspect requires a present "
            "user identifier input."
        )

    if inspector_id == "active_directory.group.inspect":
        if _any_present(_AD_GROUP_INSPECT_IDENTIFIER_FIELDS, present_fields):
            return None
        return (
            "Inspector active_directory.group.inspect requires a present "
            "group identifier input."
        )

    if inspector_id == "active_directory.group_membership.inspect":
        has_user = _any_present(_USER_IDENTIFIER_FIELDS, present_fields)
        has_group = _any_present(_GROUP_IDENTIFIER_FIELDS, present_fields)

        if has_user and has_group:
            return None

        return (
            "Inspector active_directory.group_membership.inspect requires "
            "both a present user identifier and a present group "
            "identifier input."
        )

    return None


def _any_present(
    candidate_fields: tuple[str, ...],
    present_fields: set[str],
) -> bool:
    return any(field in present_fields for field in candidate_fields)


# ---- Display helpers ----------------------------------------------------


def format_skill_plan_validation_findings(
    findings: list[SkillPlanValidationFinding],
) -> list[str]:
    """Format validator findings as advisory log lines.

    Returns one success line when there are no findings, otherwise a
    summary line followed by one bullet per finding tagged ERROR or
    WARNING.
    """
    if not findings:
        return ["Skill plan validation: no issues found."]

    lines: list[str] = [
        f"Skill plan validation: found {len(findings)} issue(s)."
    ]

    for finding in findings:
        severity_label = "ERROR" if finding.severity == "error" else "WARNING"
        lines.append(
            f"- {severity_label} [{finding.code}]: {finding.message}"
        )

    return lines


def validate_skill_plan_text_as_lines(text: str) -> list[str]:
    """Parse+validate+format a saved skill plan into advisory log lines.

    Never raises. Any unexpected error is wrapped into a single
    non-blocking "Skill plan validation unavailable: ..." line so the
    caller can log it without breaking the user flow.
    """
    try:
        plan = parse_servicedesk_skill_plan(text)
        findings = validate_servicedesk_skill_plan(plan)
        return format_skill_plan_validation_findings(findings)
    except Exception as exc:  # noqa: BLE001 - advisory path must not raise
        return [f"Skill plan validation unavailable: {exc}"]


@dataclass(frozen=True)
class SkillPlanValidationDisplayResult:
    """Result of running validation for a flow that may be gated on errors.

    `lines` are the formatted advisory log lines. `has_errors` is True when
    the caller should block its next step (e.g. running inspectors).
    Warnings never set `has_errors`.
    """

    lines: list[str]
    has_errors: bool


def validate_skill_plan_text_for_inspection(
    text: str,
) -> SkillPlanValidationDisplayResult:
    """Parse+validate a saved skill plan for the inspection gate.

    Returns formatted advisory lines and a boolean signalling whether
    inspection should be blocked. Errors block; warnings do not. If
    parsing/validation itself raises, the caller is told to block via
    `has_errors=True` and given a single
    `Skill plan validation unavailable: ...` line so the failure is
    visible without leaking a traceback.
    """
    try:
        plan = parse_servicedesk_skill_plan(text)
    except Exception as exc:  # noqa: BLE001 - safety gate must not raise
        return SkillPlanValidationDisplayResult(
            lines=[f"Skill plan validation unavailable: {exc}"],
            has_errors=True,
        )

    return validate_parsed_skill_plan_for_inspection(plan)


def validate_parsed_skill_plan_for_inspection(
    plan,
) -> SkillPlanValidationDisplayResult:
    """Validate an already-parsed `ParsedServiceDeskSkillPlan` for the
    inspection gate.

    Same display-result shape as `validate_skill_plan_text_for_inspection`
    so callers using either source (Markdown reparse vs structured JSON
    sidecar) gate identically. Errors block; warnings do not.
    """
    try:
        findings = validate_servicedesk_skill_plan(plan)
    except Exception as exc:  # noqa: BLE001 - safety gate must not raise
        return SkillPlanValidationDisplayResult(
            lines=[f"Skill plan validation unavailable: {exc}"],
            has_errors=True,
        )

    lines = format_skill_plan_validation_findings(findings)
    has_errors = any(finding.severity == "error" for finding in findings)

    return SkillPlanValidationDisplayResult(
        lines=lines,
        has_errors=has_errors,
    )
