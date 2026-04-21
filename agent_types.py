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
    call_id: str | None = None


@dataclass(frozen=True)
class ToolResult:
    name: str
    payload: dict[str, Any]
    call_id: str | None = None


@dataclass(frozen=True)
class UsageStats:
    prompt_tokens: int | None = None
    response_tokens: int | None = None


@dataclass
class UsageTotals:
    prompt_tokens: int = 0
    response_tokens: int = 0

    def add(self, usage: UsageStats | None) -> None:
        if usage is None:
            return

        if usage.prompt_tokens is not None:
            self.prompt_tokens += usage.prompt_tokens

        if usage.response_tokens is not None:
            self.response_tokens += usage.response_tokens

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.response_tokens

    @property
    def has_usage(self) -> bool:
        return self.prompt_tokens > 0 or self.response_tokens > 0


@dataclass(frozen=True)
class ModelTurn:
    text_parts: list[str]
    tool_calls: list[ToolCall]
    usage: UsageStats | None = None
