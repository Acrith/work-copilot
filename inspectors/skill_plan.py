from dataclasses import dataclass

from inspectors.models import InspectorRequest, InspectorTarget

SUPPORTED_INSPECTOR_IDS = {
    "exchange.mailbox.inspect",
}


INSPECTOR_ID_ALIASES = {
    "exchange.mailbox.get_properties": "exchange.mailbox.inspect",
    "exchange.mailbox.get_statistics": "exchange.mailbox.inspect",
    "exchange.mailbox.get_archive_status": "exchange.mailbox.inspect",
    "exchange.mailbox.get_retention_policy": "exchange.mailbox.inspect",
    "exchange.mailbox.get_quota_warning_status": "exchange.mailbox.inspect",
    "exchange.mailbox.get_auto_expanding_archive_status": "exchange.mailbox.inspect",
    "exchange.mailbox.prepare_inspection_report_parameters": "exchange.mailbox.inspect",
}


def normalize_inspector_id(inspector_id: str) -> str:
    cleaned = _clean_markdown_value(inspector_id)

    return INSPECTOR_ID_ALIASES.get(cleaned, cleaned)


@dataclass(frozen=True)
class SkillPlanInput:
    field: str
    status: str
    value: str
    evidence: str
    needed_now: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "field": self.field,
            "status": self.status,
            "value": self.value,
            "evidence": self.evidence,
            "needed_now": self.needed_now,
        }


def parse_suggested_inspector_tools(skill_plan_text: str) -> list[str]:
    for line in skill_plan_text.splitlines():
        stripped = line.strip()

        if not stripped.startswith("- Suggested inspector tools:"):
            continue

        raw_tools = stripped.removeprefix("- Suggested inspector tools:").strip()

        if not raw_tools or raw_tools.lower() == "none":
            return []

        return [
            _clean_markdown_value(tool)
            for tool in raw_tools.split(",")
            if _clean_markdown_value(tool)
        ]

    return []


def parse_extracted_inputs(skill_plan_text: str) -> dict[str, SkillPlanInput]:
    parsed: dict[str, SkillPlanInput] = {}
    current: dict[str, object] | None = None

    def save_current() -> None:
        if current is None:
            return

        field = str(current.get("field", "")).strip()

        if not field:
            return

        parsed[field] = SkillPlanInput(
            field=field,
            status=str(current.get("status", "")).strip(),
            value=_clean_markdown_value(str(current.get("value", ""))),
            evidence=str(current.get("evidence", "")).strip(),
            needed_now=bool(current.get("needed_now", False)),
        )

    for line in skill_plan_text.splitlines():
        stripped = line.strip()

        if stripped.startswith("- field:"):
            save_current()
            current = {
                "field": stripped.removeprefix("- field:").strip(),
                "status": "",
                "value": "",
                "evidence": "",
                "needed_now": False,
            }
            continue

        if current is None:
            continue

        if stripped.startswith("status:"):
            current["status"] = stripped.removeprefix("status:").strip()
        elif stripped.startswith("value:"):
            current["value"] = stripped.removeprefix("value:").strip()
        elif stripped.startswith("evidence:"):
            current["evidence"] = stripped.removeprefix("evidence:").strip()
        elif stripped.startswith("needed_now:"):
            value = stripped.removeprefix("needed_now:").strip().lower()
            current["needed_now"] = value == "yes"

    save_current()

    return parsed


def build_inspector_request_from_skill_plan(
    *,
    request_id: str,
    skill_plan_text: str,
    inspector_id: str,
) -> InspectorRequest:
    inspector_id = normalize_inspector_id(inspector_id)

    if inspector_id not in SUPPORTED_INSPECTOR_IDS:
        raise ValueError(f"Unsupported inspector for skill-plan handoff: {inspector_id}")

    extracted_inputs = parse_extracted_inputs(skill_plan_text)

    if inspector_id == "exchange.mailbox.inspect":
        mailbox_address = _first_present_input_value(
            extracted_inputs,
            [
                "mailbox_address",
                "target_user_email",
                "target_user",
                "shared_mailbox_address",
            ],
        )

        if mailbox_address is None:
            raise ValueError(
                "Cannot build exchange.mailbox.inspect request: "
                "missing mailbox_address or equivalent extracted input"
            )

        return InspectorRequest(
            inspector=inspector_id,
            request_id=request_id,
            target=InspectorTarget(
                type="mailbox",
                id=mailbox_address,
                metadata={"source": "skill_plan"},
            ),
            inputs={
                "mailbox_address": mailbox_address,
                "skill_plan_inputs": {
                    field: item.to_dict()
                    for field, item in extracted_inputs.items()
                },
            },
        )

    raise ValueError(f"Unsupported inspector for skill-plan handoff: {inspector_id}")


def _first_present_input_value(
    extracted_inputs: dict[str, SkillPlanInput],
    field_names: list[str],
) -> str | None:
    for field_name in field_names:
        item = extracted_inputs.get(field_name)

        if item is None:
            continue

        if item.status != "present":
            continue

        if item.value:
            return item.value

    return None


def _clean_markdown_value(value: str) -> str:
    return value.strip().strip("`").strip()


def select_supported_inspector_tool(suggested_tools: list[str]) -> str | None:
    for tool in suggested_tools:
        normalized = normalize_inspector_id(tool)

        if normalized in SUPPORTED_INSPECTOR_IDS:
            return normalized

    return None


def parse_skill_match(skill_plan_text: str) -> str | None:
    for line in skill_plan_text.splitlines():
        stripped = line.strip()

        if not stripped.startswith("- Skill match:"):
            continue

        raw_value = stripped.removeprefix("- Skill match:").strip()
        cleaned = _clean_markdown_value(raw_value)

        if not cleaned or cleaned.lower() == "none":
            return None

        return cleaned

    return None


@dataclass(frozen=True)
class SkillPlanInspectorSelection:
    inspector_id: str
    source: str


def select_inspector_for_skill_plan(
    skill_plan_text: str,
) -> SkillPlanInspectorSelection | None:
    suggested_tools = parse_suggested_inspector_tools(skill_plan_text)
    suggested = select_supported_inspector_tool(suggested_tools)

    if suggested is not None:
        return SkillPlanInspectorSelection(
            inspector_id=suggested,
            source="suggested_inspector_tools",
        )

    skill_match = parse_skill_match(skill_plan_text)

    if skill_match is None:
        return None

    normalized_skill_match = normalize_inspector_id(skill_match)

    if normalized_skill_match in SUPPORTED_INSPECTOR_IDS:
        return SkillPlanInspectorSelection(
            inspector_id=normalized_skill_match,
            source="skill_match",
        )

    return None
