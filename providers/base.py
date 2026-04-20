from typing import Protocol

from agent_types import ModelTurn, ToolResult, ToolSpec


class Provider(Protocol):
    def add_user_message(self, text: str) -> None:
        """Add a user message to the provider conversation history."""

    def generate(self, system_prompt: str, tools: list[ToolSpec]) -> ModelTurn:
        """Generate one provider-neutral model turn."""

    def add_tool_results(self, results: list[ToolResult]) -> None:
        """Add tool results back to the provider conversation history."""
