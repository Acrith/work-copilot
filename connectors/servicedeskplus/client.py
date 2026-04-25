from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from connectors.servicedeskplus.config import ServiceDeskPlusConfig


class ServiceDeskPlusError(RuntimeError):
    pass


@dataclass(frozen=True)
class ServiceDeskPlusClient:
    config: ServiceDeskPlusConfig

    def _base_url(self) -> str:
        if not self.config.base_url:
            raise ServiceDeskPlusError("SDP_BASE_URL is not configured.")

        return self.config.base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        if not self.config.authtoken:
            raise ServiceDeskPlusError("SDP_AUTHTOKEN is not configured.")

        return {
            "Accept": "application/vnd.manageengine.sdp.v3+json",
            "Content-Type": "application/x-www-form-urlencoded",
            "authtoken": self.config.authtoken,
        }

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = f"?{urlencode(params)}" if params else ""
        url = f"{self._base_url()}/{path.lstrip('/')}{query}"

        request = Request(
            url,
            headers=self._headers(),
            method="GET",
        )

        try:
            with urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise ServiceDeskPlusError(
                f"ServiceDesk Plus API returned HTTP {error.code}: {details}"
            ) from error
        except URLError as error:
            raise ServiceDeskPlusError(
                f"Could not connect to ServiceDesk Plus: {error.reason}"
            ) from error

        if not body:
            return {}

        try:
            return json.loads(body)
        except json.JSONDecodeError as error:
            raise ServiceDeskPlusError("ServiceDesk Plus returned invalid JSON.") from error

    def get_with_input_data(
        self,
        path: str,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        return self.get(
            path,
            params={
                "input_data": json.dumps(input_data),
            },
        )

    def list_request_filters(self) -> dict[str, Any]:
        input_data = {
            "show_all": {
                "module": "request",
            },
            "list_info": {
                "row_count": "100",
                "search_fields": {
                    "module": "request",
                },
            },
        }

        return self.get_with_input_data(
            "/api/v3/list_view_filters/show_all",
            input_data,
        )