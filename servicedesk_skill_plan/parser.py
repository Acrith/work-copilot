from servicedesk_skill_plan.models import (
    ExtractedInput,
    ParsedServiceDeskSkillPlan,
    SkillPlanAutomationHandoff,
)

# Section headings the parser recognises.
_METADATA_HEADING = "## Metadata"
_EXTRACTED_INPUTS_HEADING = "## Extracted inputs"
_MISSING_INFO_HEADING = "## Missing information needed now"
_CURRENT_BLOCKER_HEADING = "## Current blocker"
_AUTOMATION_HANDOFF_HEADING = "## Automation handoff"


def parse_servicedesk_skill_plan(text: str) -> ParsedServiceDeskSkillPlan:
    sections = _split_sections(text)

    metadata = _parse_metadata(sections.get(_METADATA_HEADING, ""))
    extracted_inputs = _parse_extracted_inputs(
        sections.get(_EXTRACTED_INPUTS_HEADING, "")
    )
    missing_info = _parse_bullet_list(
        sections.get(_MISSING_INFO_HEADING, "")
    )
    current_blocker = _parse_block_text(
        sections.get(_CURRENT_BLOCKER_HEADING, "")
    )
    handoff = _parse_automation_handoff(
        sections.get(_AUTOMATION_HANDOFF_HEADING, "")
    )

    return ParsedServiceDeskSkillPlan(
        metadata=metadata,
        extracted_inputs=extracted_inputs,
        missing_information_needed_now=missing_info,
        current_blocker=current_blocker,
        automation_handoff=handoff,
    )


# ---- Section splitter ---------------------------------------------------


def _split_sections(text: str) -> dict[str, str]:
    """Split a Markdown document into top-level `##` sections.

    Returns a mapping from heading line (e.g. `## Metadata`) to the body
    text that follows, until the next `## ` heading. Sub-sections starting
    with `### ` stay inside their parent. Content before the first `## `
    heading is ignored (typically the `# ServiceDesk skill plan` title).
    """
    sections: dict[str, str] = {}
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith("## ") and not stripped.startswith("### "):
            if current_heading is not None:
                sections[current_heading] = "\n".join(current_lines).strip("\n")

            current_heading = stripped
            current_lines = []
            continue

        if current_heading is not None:
            current_lines.append(line)

    if current_heading is not None:
        sections[current_heading] = "\n".join(current_lines).strip("\n")

    return sections


# ---- Metadata -----------------------------------------------------------


def _parse_metadata(body: str) -> dict[str, str]:
    metadata: dict[str, str] = {}

    for line in body.splitlines():
        stripped = line.strip()

        if not stripped.startswith("- "):
            continue

        bullet = stripped[2:].strip()

        if ":" not in bullet:
            continue

        key, _, value = bullet.partition(":")
        metadata[key.strip()] = _clean_value(value)

    return metadata


# ---- Extracted inputs ---------------------------------------------------


_EXTRACTED_INPUT_KEYS = ("status", "value", "evidence", "needed_now")


def _parse_extracted_inputs(body: str) -> list[ExtractedInput]:
    inputs: list[ExtractedInput] = []
    current: dict[str, str] | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        field_name = current.get("field", "").strip()
        if field_name:
            inputs.append(
                ExtractedInput(
                    field=field_name,
                    status=current.get("status", ""),
                    value=current.get("value", ""),
                    evidence=current.get("evidence", ""),
                    needed_now=current.get("needed_now", ""),
                )
            )
        current = None

    for raw_line in body.splitlines():
        stripped = raw_line.strip()

        if stripped.startswith("- field:"):
            flush()
            field_value = _clean_value(stripped.removeprefix("- field:"))
            current = {"field": field_value}
            continue

        if current is None:
            continue

        for key in _EXTRACTED_INPUT_KEYS:
            prefix = f"{key}:"
            if stripped.startswith(prefix):
                current[key] = _clean_value(stripped.removeprefix(prefix))
                break

    flush()

    return inputs


# ---- Missing information / current blocker ------------------------------


def _parse_bullet_list(body: str) -> list[str]:
    items: list[str] = []

    for line in body.splitlines():
        stripped = line.strip()

        if not stripped.startswith("- "):
            continue

        value = _clean_value(stripped[2:])

        if not value or value.lower() == "none":
            continue

        items.append(value)

    return items


def _parse_block_text(body: str) -> str | None:
    cleaned_lines = [line.strip() for line in body.splitlines() if line.strip()]

    if not cleaned_lines:
        return None

    text = " ".join(cleaned_lines).strip()

    if not text or text.lower() == "none":
        return None

    return text


# ---- Automation handoff -------------------------------------------------


def _parse_automation_handoff(body: str) -> SkillPlanAutomationHandoff:
    fields: dict[str, str] = {}

    for line in body.splitlines():
        stripped = line.strip()

        if not stripped.startswith("- "):
            continue

        bullet = stripped[2:].strip()

        if ":" not in bullet:
            continue

        key, _, value = bullet.partition(":")
        fields[key.strip().lower()] = _clean_value(value)

    return SkillPlanAutomationHandoff(
        ready_for_inspection=_optional_str(fields.get("ready for inspection")),
        ready_for_execution=_optional_str(fields.get("ready for execution")),
        suggested_inspector_tools=_parse_tool_list(
            fields.get("suggested inspector tools")
        ),
        suggested_execute_tools=_parse_tool_list(
            fields.get("suggested execute tools")
        ),
        automation_blocker=_optional_str_drop_none(
            fields.get("automation blocker")
        ),
    )


def _parse_tool_list(value: str | None) -> list[str]:
    if value is None:
        return []

    cleaned = _clean_value(value)

    if not cleaned or cleaned.lower() == "none":
        return []

    tools: list[str] = []

    for raw in cleaned.split(","):
        item = _clean_value(raw)

        if not item:
            continue

        if item.lower() == "none":
            continue

        tools.append(item)

    return tools


# ---- Value cleaning -----------------------------------------------------


def _clean_value(value: str) -> str:
    return value.strip().strip("`").strip()


def _optional_str(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = _clean_value(value)

    if not cleaned:
        return None

    return cleaned


def _optional_str_drop_none(value: str | None) -> str | None:
    cleaned = _optional_str(value)

    if cleaned is None:
        return None

    if cleaned.lower() == "none":
        return None

    return cleaned
