import os

from providers.base import Provider
from providers.gemini import GeminiProvider

DEFAULT_PROVIDER = "gemini"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


def get_default_model(provider_name: str) -> str:
    if provider_name == "gemini":
        return DEFAULT_GEMINI_MODEL

    raise ValueError(f"Unsupported provider: {provider_name}")


def create_provider(
    provider_name: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
) -> Provider:
    if provider_name == "gemini":
        resolved_api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not resolved_api_key:
            raise RuntimeError("GEMINI_API_KEY is required for provider 'gemini'")

        return GeminiProvider(
            api_key=resolved_api_key,
            model=model or DEFAULT_GEMINI_MODEL,
        )

    raise ValueError(f"Unsupported provider: {provider_name}")