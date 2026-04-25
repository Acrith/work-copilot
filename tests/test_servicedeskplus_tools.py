from __future__ import annotations

import connectors.servicedeskplus.tools as tools_module
from connectors.servicedeskplus.config import ServiceDeskPlusConfig


def make_config(
    *,
    enabled: bool = True,
    default_request_filter: str = "Open_System",
) -> ServiceDeskPlusConfig:
    return ServiceDeskPlusConfig(
        enabled=enabled,
        deployment="onprem",
        base_url="https://hd.exactforestall.com",
        portal=None,
        authtoken="secret-token",
        oauth_access_token=None,
        default_request_filter=default_request_filter,
    )


def test_list_request_filters_returns_error_when_disabled(monkeypatch):
    monkeypatch.setattr(
        tools_module,
        "load_servicedeskplus_config",
        lambda: make_config(enabled=False),
    )

    result = tools_module.servicedesk_list_request_filters()

    assert result == {"error": "ServiceDesk Plus connector is disabled."}


def test_list_request_filters_uses_client_when_enabled(monkeypatch):
    monkeypatch.setattr(
        tools_module,
        "load_servicedeskplus_config",
        lambda: make_config(enabled=True),
    )

    class FakeClient:
        def __init__(self, config):
            self.config = config

        def list_request_filters(self):
            return {"list_view_filters": [{"name": "Open Requests"}]}

    monkeypatch.setattr(tools_module, "ServiceDeskPlusClient", FakeClient)

    result = tools_module.servicedesk_list_request_filters()

    assert result == {"list_view_filters": [{"name": "Open Requests"}]}


def test_list_request_filters_returns_client_error(monkeypatch):
    monkeypatch.setattr(
        tools_module,
        "load_servicedeskplus_config",
        lambda: make_config(enabled=True),
    )

    class FakeClient:
        def __init__(self, config):
            self.config = config

        def list_request_filters(self):
            raise tools_module.ServiceDeskPlusError("boom")

    monkeypatch.setattr(tools_module, "ServiceDeskPlusClient", FakeClient)

    result = tools_module.servicedesk_list_request_filters()

    assert result == {"error": "boom"}


def test_list_requests_uses_client_when_enabled(monkeypatch):
    monkeypatch.setattr(
        tools_module,
        "load_servicedeskplus_config",
        lambda: make_config(enabled=True),
    )

    captured = {}

    class FakeClient:
        def __init__(self, config):
            self.config = config

        def list_requests(
            self,
            *,
            filter_name,
            row_count,
            start_index,
            sort_field,
            sort_order,
        ):
            captured["filter_name"] = filter_name
            captured["row_count"] = row_count
            captured["start_index"] = start_index
            captured["sort_field"] = sort_field
            captured["sort_order"] = sort_order
            return {"requests": [{"id": "123"}]}

    monkeypatch.setattr(tools_module, "ServiceDeskPlusClient", FakeClient)

    result = tools_module.servicedesk_list_requests(
        filter_name="Open Requests",
        row_count=5,
        start_index=1,
    )

    assert result == {"requests": [{"id": "123"}]}
    assert captured == {
        "filter_name": "Open Requests",
        "row_count": 5,
        "start_index": 1,
        "sort_field": "created_time",
        "sort_order": "desc",
    }


def test_list_requests_uses_configured_default_filter_when_omitted(monkeypatch):
    config = ServiceDeskPlusConfig(
        enabled=True,
        deployment="onprem",
        base_url="https://hd.exactforestall.com",
        portal=None,
        authtoken="secret-token",
        oauth_access_token=None,
        default_request_filter="IT - Wszystko w realizacji",
    )

    monkeypatch.setattr(
        tools_module,
        "load_servicedeskplus_config",
        lambda: config,
    )

    captured = {}

    class FakeClient:
        def __init__(self, config):
            self.config = config

        def list_requests(
            self,
            *,
            filter_name,
            row_count,
            start_index,
            sort_field,
            sort_order,
        ):
            captured["filter_name"] = filter_name
            return {"requests": []}

    monkeypatch.setattr(tools_module, "ServiceDeskPlusClient", FakeClient)

    result = tools_module.servicedesk_list_requests()

    assert result == {"requests": []}
    assert captured["filter_name"] == "IT - Wszystko w realizacji"


def test_get_request_returns_error_when_disabled(monkeypatch):
    monkeypatch.setattr(
        tools_module,
        "load_servicedeskplus_config",
        lambda: make_config(enabled=False),
    )

    result = tools_module.servicedesk_get_request(request_id="55906")

    assert result == {"error": "ServiceDesk Plus connector is disabled."}


def test_get_request_uses_client_when_enabled(monkeypatch):
    monkeypatch.setattr(
        tools_module,
        "load_servicedeskplus_config",
        lambda: make_config(enabled=True),
    )

    captured = {}

    class FakeClient:
        def __init__(self, config):
            self.config = config

        def get_request(self, request_id):
            captured["request_id"] = request_id
            return {"request": {"id": request_id}}

    monkeypatch.setattr(tools_module, "ServiceDeskPlusClient", FakeClient)

    result = tools_module.servicedesk_get_request(request_id="55906")

    assert result == {"request": {"id": "55906"}}
    assert captured["request_id"] == "55906"


def test_get_request_returns_client_error(monkeypatch):
    monkeypatch.setattr(
        tools_module,
        "load_servicedeskplus_config",
        lambda: make_config(enabled=True),
    )

    class FakeClient:
        def __init__(self, config):
            self.config = config

        def get_request(self, request_id):
            raise tools_module.ServiceDeskPlusError("boom")

    monkeypatch.setattr(tools_module, "ServiceDeskPlusClient", FakeClient)

    result = tools_module.servicedesk_get_request(request_id="55906")

    assert result == {"error": "boom"}