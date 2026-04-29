from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class InspectorStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    ERROR = "error"


@dataclass(frozen=True)
class InspectorTarget:
    type: str
    id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InspectorRequest:
    inspector: str
    target: InspectorTarget
    request_id: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InspectorFact:
    key: str
    value: Any
    source: str = "read_only_metadata"


@dataclass(frozen=True)
class InspectorEvidence:
    label: str
    value: Any


@dataclass(frozen=True)
class InspectorError:
    code: str
    message: str
    recoverable: bool = False


@dataclass(frozen=True)
class InspectorResult:
    inspector: str
    target: InspectorTarget
    status: InspectorStatus
    summary: str
    facts: list[InspectorFact] = field(default_factory=list)
    evidence: list[InspectorEvidence] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    errors: list[InspectorError] = field(default_factory=list)

    @property
    def partial(self) -> bool:
        return self.status == InspectorStatus.PARTIAL

    @property
    def ok(self) -> bool:
        return self.status == InspectorStatus.OK

    @property
    def error(self) -> bool:
        return self.status == InspectorStatus.ERROR

    def to_dict(self) -> dict[str, Any]:
        return {
            "inspector": self.inspector,
            "target": {
                "type": self.target.type,
                "id": self.target.id,
                "metadata": self.target.metadata,
            },
            "status": self.status.value,
            "summary": self.summary,
            "facts": [
                {
                    "key": fact.key,
                    "value": fact.value,
                    "source": fact.source,
                }
                for fact in self.facts
            ],
            "evidence": [
                {
                    "label": item.label,
                    "value": item.value,
                }
                for item in self.evidence
            ],
            "limitations": self.limitations,
            "recommendations": self.recommendations,
            "partial": self.partial,
            "errors": [
                {
                    "code": error.code,
                    "message": error.message,
                    "recoverable": error.recoverable,
                }
                for error in self.errors
            ],
        }