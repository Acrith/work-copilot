from typing import Any

from google.genai import types

from agent_types import ToolCall, ToolResult
from tool_dispatch import execute_tool_call
from tool_registry import get_tool_specs

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
        kwargs["properties"] = {
            name: to_gemini_schema(value)
            for name, value in properties.items()
        }

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


def to_gemini_function_declaration(spec):
    return types.FunctionDeclaration(
        name=spec.name,
        description=spec.description,
        parameters=to_gemini_schema(spec.parameters),
    )


available_functions = types.Tool(
    function_declarations=[
        to_gemini_function_declaration(spec)
        for spec in get_tool_specs()
    ],
)


def make_tool_response(result: ToolResult):
    return types.Content(
        role="tool",
        parts=[
            types.Part.from_function_response(
                name=result.name,
                response=result.payload,
            )
        ],
    )


def call_function(function_call, working_directory, permission_context, verbose=False):
    tool_call = ToolCall(
        name=function_call.name or "",
        args=dict(function_call.args) if function_call.args else {},
    )

    result = execute_tool_call(
        tool_call,
        working_directory,
        permission_context,
        verbose=verbose,
    )

    return make_tool_response(result)