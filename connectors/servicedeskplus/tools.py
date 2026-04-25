from __future__ import annotations

from typing import Any

from connectors.servicedeskplus.config import load_servicedeskplus_config


def servicedesk_status(
    working_directory: str | None = None,
    **_: Any,
) -> str:
    config = load_servicedeskplus_config()

    if not config.enabled:
        return "ServiceDesk Plus connector is disabled."

    return (
        "ServiceDesk Plus connector is enabled. "
        f"deployment={config.deployment}, "
        f"base_url_configured={bool(config.base_url)}, "
        f"portal_configured={bool(config.portal)}, "
        f"authtoken_configured={bool(config.authtoken)}, "
        f"oauth_access_token_configured={bool(config.oauth_access_token)}"
    )