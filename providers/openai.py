from copy import deepcopy
from typing import Any

from openai import OpenAI

from agent_types import ModelTurn, ToolResult, ToolSpec, UsageStats


def extract_usage(response) -> UsageStats | None:
    usage = getattr(response, "usage", None)
    if not usage:
        return None

    return UsageStats(
        prompt_tokens=getattr(usage, "input_tokens", None),
        response_tokens=getattr(usage, "output_tokens", None),
    )


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
        # Tool calling is intentionally not implemented in this PR.
        # The tools argument is accepted to satisfy the Provider protocol.
        response = self.client.responses.create(
            model=self.model,
            instructions=system_prompt,
            input=deepcopy(self.input_items),
            store=False,
        )

        text = getattr(response, "output_text", "") or ""
        text_parts = [text.strip()] if text.strip() else []

        # Keep manual conversation history for the next turn.
        if text_parts:
            self.input_items.append(
                {
                    "role": "assistant",
                    "content": text_parts[0],
                }
            )

        return ModelTurn(
            text_parts=text_parts,
            tool_calls=[],
            usage=extract_usage(response),
        )

    def add_tool_results(self, results: list[ToolResult]) -> None:
        raise NotImplementedError(
            "OpenAIProvider tool results are not implemented yet"
        )