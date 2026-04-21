import json
from copy import deepcopy
from typing import Any

from openai import OpenAI

from agent_types import ModelTurn, ToolCall, ToolResult, ToolSpec, UsageStats
from providers.base import ProviderError


def extract_usage(response) -> UsageStats | None:
    usage = getattr(response, "usage", None)
    if not usage:
        return None

    return UsageStats(
        prompt_tokens=getattr(usage, "input_tokens", None),
        response_tokens=getattr(usage, "output_tokens", None),
    )


def to_openai_tool(spec: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "name": spec.name,
        "description": spec.description,
        "parameters": spec.parameters,
    }


def extract_tool_calls(response) -> list[ToolCall]:
    tool_calls: list[ToolCall] = []

    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "function_call":
            continue

        raw_arguments = getattr(item, "arguments", "{}") or "{}"

        try:
            args = json.loads(raw_arguments)
        except json.JSONDecodeError:
            args = {}

        tool_calls.append(
            ToolCall(
                name=getattr(item, "name", "") or "",
                args=args,
                call_id=getattr(item, "call_id", None),
            )
        )

    return tool_calls


class OpenAIProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.input_items: list[Any] = []

    def add_user_message(self, text: str) -> None:
        self.input_items.append(
            {
                "role": "user",
                "content": text,
            }
        )

    def generate(self, system_prompt: str, tools: list[ToolSpec]) -> ModelTurn:
        openai_tools = [to_openai_tool(spec) for spec in tools]

        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=system_prompt,
                input=deepcopy(self.input_items),
                tools=openai_tools,
                store=False,
            )
        except Exception as e:
            raise ProviderError(f"OpenAI request failed: {e}") from e

        # Preserve model output for future turns. OpenAI docs show this pattern
        # especially for function calls/reasoning items.
        self.input_items.extend(getattr(response, "output", []) or [])

        text = getattr(response, "output_text", "") or ""
        text_parts = [text.strip()] if text.strip() else []

        return ModelTurn(
            text_parts=text_parts,
            tool_calls=extract_tool_calls(response),
            usage=extract_usage(response),
        )

    def add_tool_results(self, results: list[ToolResult]) -> None:
        for result in results:
            if not result.call_id:
                raise ValueError(f"Missing call_id for OpenAI tool result: {result.name}")

            self.input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": result.call_id,
                    "output": json.dumps(result.payload),
                }
            )
