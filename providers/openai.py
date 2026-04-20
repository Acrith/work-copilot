from typing import Any

from openai import OpenAI

from agent_types import ModelTurn, ToolResult, ToolSpec


class OpenAIProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.input_items: list[dict[str, Any]] = []

    def add_user_message(self, text: str) -> None:
        self.input_items.append(
            {
                "role": "user",
                "content": text,
            }
        )

    def generate(self, system_prompt: str, tools: list[ToolSpec]) -> ModelTurn:
        raise NotImplementedError("OpenAIProvider.generate is not implemented yet")

    def add_tool_results(self, results: list[ToolResult]) -> None:
        raise NotImplementedError(
            "OpenAIProvider.add_tool_results is not implemented yet"
        )