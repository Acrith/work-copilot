from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RequiredInput:
    name: str
    description: str
    required: bool = False


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    family: str | None
    name: str
    version: int
    status: str
    description: str
    when_to_use: list[str]
    when_not_to_use: list[str]
    required_inputs: list[RequiredInput]
    derived_outputs: list[str]
    output_artifacts: list[str]
    systems: list[str]
    data_sensitivity: list[str]
    execution_mode: dict[str, Any] | None
    risk_level: str
    approval_requirements: list[str]
    allowed_actions_now: list[str]
    forbidden_actions_now: list[str]
    current_manual_adapter: dict[str, Any] | None
    future_tool_bindings: dict[str, Any] | None
    automation_readiness: str | None

    # Legacy schema support. Keep temporarily while old YAML files are removed.
    intents: list[str]
    required_information: list[str]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def _as_str_list(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value)]


def _as_optional_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value

    return None


def _parse_required_inputs(value: Any) -> list[RequiredInput]:
    items: list[RequiredInput] = []

    for item in _as_list(value):
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()

            if not name:
                continue

            items.append(
                RequiredInput(
                    name=name,
                    description=str(item.get("description", "")),
                    required=bool(item.get("required", False)),
                )
            )
        else:
            name = str(item).strip()

            if name:
                items.append(
                    RequiredInput(
                        name=name,
                        description="",
                        required=False,
                    )
                )

    return items


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Skill definition must be a mapping: {path}")

    if not data.get("id"):
        raise ValueError(f"Skill definition missing required field 'id': {path}")

    if not data.get("name"):
        raise ValueError(f"Skill definition missing required field 'name': {path}")

    return data


def load_skill_definitions(
    definitions_dir: Path | None = None,
) -> list[SkillDefinition]:
    if definitions_dir is None:
        definitions_dir = Path(__file__).parent / "definitions"

    skills: list[SkillDefinition] = []

    for path in sorted(definitions_dir.glob("*.yaml")):
        data = _load_yaml_mapping(path)

        skills.append(
            SkillDefinition(
                id=str(data["id"]),
                family=(
                    str(data["family"])
                    if data.get("family") is not None
                    else None
                ),
                name=str(data["name"]),
                version=int(data.get("version", 1)),
                status=str(data.get("status", "draft_only")),
                description=str(data.get("description", "")),
                when_to_use=_as_str_list(data.get("when_to_use")),
                when_not_to_use=_as_str_list(data.get("when_not_to_use")),
                required_inputs=_parse_required_inputs(
                    data.get("required_inputs")
                ),
                derived_outputs=_as_str_list(data.get("derived_outputs")),
                output_artifacts=_as_str_list(data.get("output_artifacts")),
                systems=_as_str_list(data.get("systems")),
                data_sensitivity=_as_str_list(data.get("data_sensitivity")),
                execution_mode=_as_optional_dict(data.get("execution_mode")),
                risk_level=str(data.get("risk_level", "medium")),
                approval_requirements=_as_str_list(
                    data.get("approval_requirements")
                ),
                allowed_actions_now=_as_str_list(
                    data.get("allowed_actions_now")
                ),
                forbidden_actions_now=_as_str_list(
                    data.get("forbidden_actions_now")
                ),
                current_manual_adapter=_as_optional_dict(
                    data.get("current_manual_adapter")
                ),
                future_tool_bindings=_as_optional_dict(
                    data.get("future_tool_bindings")
                ),
                automation_readiness=(
                    str(data["automation_readiness"])
                    if data.get("automation_readiness") is not None
                    else None
                ),
                intents=_as_str_list(data.get("intents")),
                required_information=_as_str_list(
                    data.get("required_information")
                ),
            )
        )

    return skills


def _format_nested_value(value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent

    if isinstance(value, dict):
        lines: list[str] = []

        for key, item in value.items():
            if isinstance(item, dict | list):
                lines.append(f"{prefix}- {key}:")
                lines.extend(_format_nested_value(item, indent + 4))
            else:
                lines.append(f"{prefix}- {key}: {item}")

        return lines

    if isinstance(value, list):
        lines = []

        for item in value:
            if isinstance(item, dict | list):
                lines.append(f"{prefix}-")
                lines.extend(_format_nested_value(item, indent + 4))
            else:
                lines.append(f"{prefix}- {item}")

        return lines

    return [f"{prefix}- {value}"]


def _format_section(label: str, value: Any) -> list[str]:
    if value is None or value == [] or value == {}:
        return []

    return [
        f"{label}:",
        *_format_nested_value(value),
        "",
    ]


def _format_required_inputs(items: list[RequiredInput]) -> list[str]:
    if not items:
        return []

    lines = ["Required inputs:"]

    for item in items:
        required = str(item.required).lower()
        description = item.description or "No description provided"
        lines.append(f"- {item.name}: {description} (required: {required})")

    lines.append("")
    return lines


def format_skill_definitions_for_prompt(
    skills: list[SkillDefinition],
) -> str:
    sections: list[str] = []

    for skill in skills:
        lines: list[str] = [
            f"## {skill.id}",
            "",
            f"Family: {skill.family or ''}",
            f"Name: {skill.name}",
            f"Version: {skill.version}",
            f"Status: {skill.status}",
            f"Risk level: {skill.risk_level}",
            "",
            "Description:",
            skill.description or "",
            "",
        ]

        lines.extend(_format_section("When to use", skill.when_to_use))
        lines.extend(_format_section("When not to use", skill.when_not_to_use))
        lines.extend(_format_required_inputs(skill.required_inputs))
        lines.extend(_format_section("Derived outputs", skill.derived_outputs))
        lines.extend(_format_section("Output artifacts", skill.output_artifacts))
        lines.extend(_format_section("Systems", skill.systems))
        lines.extend(_format_section("Data sensitivity", skill.data_sensitivity))
        lines.extend(_format_section("Execution mode", skill.execution_mode))
        lines.extend(
            _format_section(
                "Approval requirements",
                skill.approval_requirements,
            )
        )
        lines.extend(
            _format_section(
                "Allowed actions now",
                skill.allowed_actions_now,
            )
        )
        lines.extend(
            _format_section(
                "Forbidden actions now",
                skill.forbidden_actions_now,
            )
        )
        lines.extend(
            _format_section(
                "Current manual adapter",
                skill.current_manual_adapter,
            )
        )
        lines.extend(
            _format_section(
                "Future tool bindings",
                skill.future_tool_bindings,
            )
        )

        if skill.automation_readiness is not None:
            lines.extend(
                _format_section(
                    "Automation readiness",
                    [skill.automation_readiness],
                )
            )

        # Temporary legacy support. Remove after old schema files are gone.
        lines.extend(_format_section("Legacy intents", skill.intents))
        lines.extend(
            _format_section(
                "Legacy required information",
                skill.required_information,
            )
        )

        sections.append("\n".join(lines).strip())

    return "\n\n".join(sections)