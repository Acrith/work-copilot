from dataclasses import dataclass
from typing import Any


JsonSchema = dict[str, Any]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: JsonSchema


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    name: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class UsageStats:
    prompt_tokens: int | None = None
    response_tokens: int | None = None


@dataclass(frozen=True)
class ModelTurn:
    text_parts: list[str]
    tool_calls: list[ToolCall]
    usage: UsageStats | None = None