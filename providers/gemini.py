from typing import Any

from google import genai
from google.genai import types

from agent_types import ModelTurn, ToolCall, ToolResult, ToolSpec, UsageStats
from providers.base import ProviderError

TYPE_MAP = {
    "object": types.Type.OBJECT,
    "string": types.Type.STRING,
    "array": types.Type.ARRAY,
    "integer": types.Type.INTEGER,
    "boolean": types.Type.BOOLEAN,
}


def to_gemini_schema(schema: dict[str, Any]) -> types.Schema:
    kwargs: dict[str, Any] = {}

    schema_type = schema.get("type")
    if schema_type:
        kwargs["type"] = TYPE_MAP[schema_type]

    description = schema.get("description")
    if description:
        kwargs["description"] = description

    properties = schema.get("properties")
    if properties is not None:
        kwargs["properties"] = {name: to_gemini_schema(value) for name, value in properties.items()}

    required = schema.get("required")
    if required is not None:
        kwargs["required"] = required

    items = schema.get("items")
    if items is not None:
        kwargs["items"] = to_gemini_schema(items)

    nullable = schema.get("nullable")
    if nullable is not None:
        kwargs["nullable"] = nullable

    return types.Schema(**kwargs)


def to_gemini_function_declaration(spec: ToolSpec) -> types.FunctionDeclaration:
    return types.FunctionDeclaration(
        name=spec.name,
        description=spec.description,
        parameters=to_gemini_schema(spec.parameters),
    )


def to_gemini_tool(tools: list[ToolSpec]) -> types.Tool:
    return types.Tool(
        function_declarations=[to_gemini_function_declaration(spec) for spec in tools],
    )


def extract_text_parts(response) -> list[str]:
    texts: list[str] = []

    if not response.candidates:
        return texts

    for candidate in response.candidates:
        content = getattr(candidate, "content", None)
        if not content:
            continue

        parts = getattr(content, "parts", None) or []
        for part in parts:
            text = getattr(part, "text", None)
            if not text:
                continue

            stripped = text.strip()
            if stripped:
                texts.append(stripped)

    return texts


def extract_tool_calls(response) -> list[ToolCall]:
    tool_calls: list[ToolCall] = []

    for function_call in response.function_calls or []:
        tool_calls.append(
            ToolCall(
                name=function_call.name or "",
                args=dict(function_call.args) if function_call.args else {},
            )
        )

    return tool_calls


def extract_usage(response) -> UsageStats | None:
    usage_metadata = getattr(response, "usage_metadata", None)
    if not usage_metadata:
        return None

    return UsageStats(
        prompt_tokens=getattr(usage_metadata, "prompt_token_count", None),
        response_tokens=getattr(usage_metadata, "candidates_token_count", None),
    )


class GeminiProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.messages: list[types.Content] = []

    def add_user_message(self, text: str) -> None:
        self.messages.append(
            types.Content(
                role="user",
                parts=[types.Part(text=text)],
            )
        )

    def generate(self, system_prompt: str, tools: list[ToolSpec]) -> ModelTurn:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=self.messages,
                config=types.GenerateContentConfig(
                    tools=[to_gemini_tool(tools)],
                    system_instruction=system_prompt,
                ),
            )
        except Exception as e:
            raise ProviderError(f"Gemini request failed: {e}") from e

        if response.candidates:
            for candidate in response.candidates:
                if candidate.content:
                    self.messages.append(candidate.content)

        return ModelTurn(
            text_parts=extract_text_parts(response),
            tool_calls=extract_tool_calls(response),
            usage=extract_usage(response),
        )

    def add_tool_results(self, results: list[ToolResult]) -> None:
        parts = [
            types.Part.from_function_response(
                name=result.name,
                response=result.payload,
            )
            for result in results
        ]

        self.messages.append(
            types.Content(
                role="user",
                parts=parts,
            )
        )
