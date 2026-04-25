from __future__ import annotations

from typing import Any

from connectors.servicedeskplus.client import (
    ServiceDeskPlusClient,
    ServiceDeskPlusError,
)
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


def servicedesk_list_request_filters(
    working_directory: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    config = load_servicedeskplus_config()

    if not config.enabled:
        return {"error": "ServiceDesk Plus connector is disabled."}

    try:
        client = ServiceDeskPlusClient(config)
        return client.list_request_filters()
    except ServiceDeskPlusError as error:
        return {"error": str(error)}


def servicedesk_list_requests(
    filter_name: str | None = None,
    row_count: int = 10,
    start_index: int = 1,
    sort_field: str = "created_time",
    sort_order: str = "desc",
    working_directory: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    config = load_servicedeskplus_config()

    if not config.enabled:
        return {"error": "ServiceDesk Plus connector is disabled."}

    effective_filter_name = filter_name or config.default_request_filter

    try:
        client = ServiceDeskPlusClient(config)
        return client.list_requests(
            filter_name=effective_filter_name,
            row_count=row_count,
            start_index=start_index,
            sort_field=sort_field,
            sort_order=sort_order,
        )
    except ServiceDeskPlusError as error:
        return {"error": str(error)}