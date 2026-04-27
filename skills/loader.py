from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    name: str
    version: int
    status: str
    description: str
    intents: list[str]
    required_information: list[str]
    systems: list[str]
    risk_level: str
    approval_requirements: list[str]
    allowed_actions_now: list[str]
    forbidden_actions_now: list[str]


def load_skill_definitions(definitions_dir: Path | None = None) -> list[SkillDefinition]:
    if definitions_dir is None:
        definitions_dir = Path(__file__).parent / "definitions"

    skills: list[SkillDefinition] = []

    for path in sorted(definitions_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))

        skills.append(
            SkillDefinition(
                id=str(data["id"]),
                name=str(data["name"]),
                version=int(data.get("version", 1)),
                status=str(data.get("status", "draft_only")),
                description=str(data.get("description", "")),
                intents=list(data.get("intents", [])),
                required_information=list(data.get("required_information", [])),
                systems=list(data.get("systems", [])),
                risk_level=str(data.get("risk_level", "medium")),
                approval_requirements=list(data.get("approval_requirements", [])),
                allowed_actions_now=list(data.get("allowed_actions_now", [])),
                forbidden_actions_now=list(data.get("forbidden_actions_now", [])),
            )
        )

    return skills


def format_skill_definitions_for_prompt(skills: list[SkillDefinition]) -> str:
    sections: list[str] = []

    for skill in skills:
        sections.append(
            "\n".join(
                [
                    f"## {skill.id}",
                    "",
                    f"Name: {skill.name}",
                    f"Status: {skill.status}",
                    f"Risk level: {skill.risk_level}",
                    "",
                    "Description:",
                    skill.description,
                    "",
                    "Intents:",
                    *[f"- {intent}" for intent in skill.intents],
                    "",
                    "Required information:",
                    *[f"- {item}" for item in skill.required_information],
                    "",
                    "Systems:",
                    *[f"- {system}" for system in skill.systems],
                    "",
                    "Approval requirements:",
                    *[f"- {item}" for item in skill.approval_requirements],
                    "",
                    "Allowed actions now:",
                    *[f"- {item}" for item in skill.allowed_actions_now],
                    "",
                    "Forbidden actions now:",
                    *[f"- {item}" for item in skill.forbidden_actions_now],
                ]
            )
        )

    return "\n\n".join(sections)