from types import SimpleNamespace

import pytest

from agent_types import ToolResult, ToolSpec
from providers.base import ProviderError
from providers.openai import (
    OpenAIProvider,
    extract_tool_calls,
    extract_usage,
    to_openai_tool,
)


class FakeResponses:
    def __init__(self, response):
        self.calls = []
        self.response = response

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response):
        self.responses = FakeResponses(response)


def test_openai_provider_stores_user_message():
    provider = OpenAIProvider(
        api_key="test-key",
        model="test-model",
    )

    provider.add_user_message("hello")

    assert provider.model == "test-model"
    assert provider.input_items == [
        {
            "role": "user",
            "content": "hello",
        }
    ]


def test_to_openai_tool_converts_tool_spec():
    spec = ToolSpec(
        name="get_file_content",
        description="Read a file.",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
            },
            "required": ["file_path"],
        },
    )

    assert to_openai_tool(spec) == {
        "type": "function",
        "name": "get_file_content",
        "description": "Read a file.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
            },
            "required": ["file_path"],
        },
    }


def test_openai_provider_generates_text():
    output_item = SimpleNamespace(type="message", content="Hello from OpenAI")
    response = SimpleNamespace(
        output_text="Hello from OpenAI",
        output=[output_item],
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
        ),
    )
    fake_client = FakeClient(response)

    provider = OpenAIProvider(
        api_key="test-key",
        model="test-model",
    )
    provider.client = fake_client
    provider.add_user_message("hello")

    turn = provider.generate("system prompt", [])

    assert turn.text_parts == ["Hello from OpenAI"]
    assert turn.tool_calls == []
    assert turn.usage.prompt_tokens == 10
    assert turn.usage.response_tokens == 5

    assert fake_client.responses.calls == [
        {
            "model": "test-model",
            "instructions": "system prompt",
            "input": [
                {
                    "role": "user",
                    "content": "hello",
                }
            ],
            "tools": [],
            "store": False,
        }
    ]

    assert provider.input_items == [
        {
            "role": "user",
            "content": "hello",
        },
        output_item,
    ]


def test_openai_provider_extracts_tool_call():
    tool_call_item = SimpleNamespace(
        type="function_call",
        name="get_file_content",
        arguments='{"file_path": "main.py"}',
        call_id="call_123",
    )
    response = SimpleNamespace(
        output_text="",
        output=[tool_call_item],
        usage=None,
    )
    fake_client = FakeClient(response)

    provider = OpenAIProvider(
        api_key="test-key",
        model="test-model",
    )
    provider.client = fake_client
    provider.add_user_message("Read main.py")

    turn = provider.generate(
        "system prompt",
        [
            ToolSpec(
                name="get_file_content",
                description="Read a file.",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                    },
                    "required": ["file_path"],
                },
            )
        ],
    )

    assert turn.text_parts == []
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].name == "get_file_content"
    assert turn.tool_calls[0].args == {"file_path": "main.py"}
    assert turn.tool_calls[0].call_id == "call_123"

    assert provider.input_items == [
        {
            "role": "user",
            "content": "Read main.py",
        },
        tool_call_item,
    ]


def test_extract_tool_calls_handles_invalid_json_arguments():
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="function_call",
                name="broken_tool",
                arguments="{not json",
                call_id="call_bad",
            )
        ]
    )

    tool_calls = extract_tool_calls(response)

    assert len(tool_calls) == 1
    assert tool_calls[0].name == "broken_tool"
    assert tool_calls[0].args == {}
    assert tool_calls[0].call_id == "call_bad"


def test_extract_usage_returns_none_when_missing():
    assert extract_usage(SimpleNamespace()) is None


def test_openai_provider_add_tool_results_appends_function_outputs():
    provider = OpenAIProvider(
        api_key="test-key",
        model="test-model",
    )

    provider.add_tool_results(
        [
            ToolResult(
                name="get_file_content",
                payload={"result": "hello"},
                call_id="call_123",
            )
        ]
    )

    assert provider.input_items == [
        {
            "type": "function_call_output",
            "call_id": "call_123",
            "output": '{"result": "hello"}',
        }
    ]


def test_openai_provider_add_tool_results_requires_call_id():
    provider = OpenAIProvider(
        api_key="test-key",
        model="test-model",
    )

    with pytest.raises(ValueError, match="Missing call_id"):
        provider.add_tool_results(
            [
                ToolResult(
                    name="get_file_content",
                    payload={"result": "hello"},
                )
            ]
        )


class RaisingResponses:
    def create(self, **kwargs):
        raise RuntimeError("api broke")


class RaisingClient:
    def __init__(self):
        self.responses = RaisingResponses()


def test_openai_provider_wraps_request_errors():
    provider = OpenAIProvider(
        api_key="test-key",
        model="test-model",
    )
    provider.client = RaisingClient()

    with pytest.raises(ProviderError, match="OpenAI request failed"):
        provider.generate("system prompt", [])
