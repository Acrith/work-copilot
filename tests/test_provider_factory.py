import pytest

from providers.factory import (
    DEFAULT_GEMINI_MODEL,
    create_provider,
    get_default_model,
)
from providers.gemini import GeminiProvider


def test_get_default_model_for_gemini():
    assert get_default_model("gemini") == DEFAULT_GEMINI_MODEL


def test_get_default_model_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported provider"):
        get_default_model("openai")


def test_create_provider_creates_gemini_provider():
    provider = create_provider(
        "gemini",
        model="test-model",
        api_key="test-key",
    )

    assert isinstance(provider, GeminiProvider)
    assert provider.model == "test-model"


def test_create_provider_uses_default_gemini_model():
    provider = create_provider(
        "gemini",
        api_key="test-key",
    )

    assert isinstance(provider, GeminiProvider)
    assert provider.model == DEFAULT_GEMINI_MODEL


def test_create_provider_requires_gemini_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        create_provider("gemini")


def test_create_provider_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported provider"):
        create_provider(
            "openai",
            model="test-model",
            api_key="test-key",
        )