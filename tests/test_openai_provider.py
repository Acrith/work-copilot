from types import SimpleNamespace

import pytest

from providers.openai import OpenAIProvider, extract_usage


class FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)

        return SimpleNamespace(
            output_text="Hello from OpenAI",
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
            ),
        )


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


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


def test_openai_provider_generates_text(monkeypatch):
    fake_client = FakeClient()

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
            "store": False,
        }
    ]

    assert provider.input_items == [
        {
            "role": "user",
            "content": "hello",
        },
        {
            "role": "assistant",
            "content": "Hello from OpenAI",
        },
    ]


def test_extract_usage_returns_none_when_missing():
    assert extract_usage(SimpleNamespace()) is None


def test_openai_provider_add_tool_results_not_implemented():
    provider = OpenAIProvider(
        api_key="test-key",
        model="test-model",
    )

    with pytest.raises(NotImplementedError):
        provider.add_tool_results([])