import pytest

from providers.openai import OpenAIProvider


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


def test_openai_provider_generate_not_implemented():
    provider = OpenAIProvider(
        api_key="test-key",
        model="test-model",
    )

    with pytest.raises(NotImplementedError):
        provider.generate("system prompt", [])


def test_openai_provider_add_tool_results_not_implemented():
    provider = OpenAIProvider(
        api_key="test-key",
        model="test-model",
    )

    with pytest.raises(NotImplementedError):
        provider.add_tool_results([])