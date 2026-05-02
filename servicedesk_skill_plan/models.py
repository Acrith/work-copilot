from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExtractedInput:
    field: str
    status: str = ""
    value: str = ""
    evidence: str = ""
    needed_now: str = ""


@dataclass(frozen=True)
class SkillPlanAutomationHandoff:
    ready_for_inspection: str | None = None
    ready_for_execution: str | None = None
    suggested_inspector_tools: list[str] = field(default_factory=list)
    suggested_execute_tools: list[str] = field(default_factory=list)
    automation_blocker: str | None = None


@dataclass(frozen=True)
class ParsedServiceDeskSkillPlan:
    metadata: dict[str, str] = field(default_factory=dict)
    extracted_inputs: list[ExtractedInput] = field(default_factory=list)
    missing_information_needed_now: list[str] = field(default_factory=list)
    current_blocker: str | None = None
    automation_handoff: SkillPlanAutomationHandoff = field(
        default_factory=SkillPlanAutomationHandoff
    )
