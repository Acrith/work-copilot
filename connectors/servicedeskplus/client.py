from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
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

    def list_requests(
        self,
        *,
        filter_name: str = "Open_System",
        row_count: int = 10,
        start_index: int = 1,
        sort_field: str = "created_time",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        safe_row_count = max(1, min(row_count, 50))
        safe_start_index = max(1, start_index)

        input_data = {
            "list_info": {
                "row_count": safe_row_count,
                "start_index": safe_start_index,
                "sort_field": sort_field,
                "sort_order": sort_order,
                "filter_by": {
                    "name": filter_name,
                },
            },
        }

        return self.get_with_input_data(
            "/api/v3/requests",
            input_data,
        )
    
    def get_request(self, request_id: str) -> dict[str, Any]:
        if not request_id:
            raise ServiceDeskPlusError("request_id is required.")

        return self.get(f"/api/v3/requests/{request_id}")


    def list_request_notes(
        self,
        *,
        request_id: str,
        row_count: int = 20,
        start_index: int = 1,
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        if not request_id:
            raise ServiceDeskPlusError("request_id is required.")

        safe_row_count = max(1, min(row_count, 50))
        safe_start_index = max(1, start_index)

        input_data = {
            "list_info": {
                "row_count": safe_row_count,
                "start_index": safe_start_index,
                "sort_field": "created_time",
                "sort_order": sort_order,
            },
        }

        return self.get_with_input_data(
            f"/api/v3/requests/{request_id}/notes",
            input_data,
        )

    
    def get_request_attachments(self, request_id: str) -> dict[str, Any]:
        if not request_id:
            raise ServiceDeskPlusError("request_id is required.")

        request_data = self.get_request(request_id)
        request = request_data.get("request", {})
        attachments = request.get("attachments", [])

        return {
            "request_id": request_id,
            "attachments": attachments,
        }

    
    def list_request_conversations(
        self,
        *,
        request_id: str,
        row_count: int = 20,
        start_index: int = 1,
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        if not request_id:
            raise ServiceDeskPlusError("request_id is required.")

        safe_row_count = max(1, min(row_count, 50))
        safe_start_index = max(1, start_index)

        input_data = {
            "list_info": {
                "row_count": safe_row_count,
                "start_index": safe_start_index,
                "sort_order": sort_order,
            },
            "system_notifications": False,
            "notes": True,
        }

        return self.get_with_input_data(
            f"/api/v3/requests/{request_id}/_conversations",
            input_data,
        )


    def get_conversation_content(self, content_url: str) -> dict[str, Any]:
        if not content_url:
            raise ServiceDeskPlusError("content_url is required.")

        base_url = self._base_url()
        base_netloc = urlparse(base_url).netloc

        if content_url.startswith("/"):
            path = content_url
        else:
            parsed_content_url = urlparse(content_url)

            if parsed_content_url.netloc != base_netloc:
                raise ServiceDeskPlusError(
                    "content_url must belong to the configured ServiceDesk Plus host."
                )

            path = parsed_content_url.path
            if parsed_content_url.query:
                path = f"{path}?{parsed_content_url.query}"

        if not path.startswith("/api/"):
            raise ServiceDeskPlusError("content_url must point to a ServiceDesk API path.")

        return self.get(path)