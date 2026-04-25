from __future__ import annotations

import connectors.servicedeskplus.tools as tools_module
from connectors.servicedeskplus.config import ServiceDeskPlusConfig


def make_config(*, enabled: bool = True) -> ServiceDeskPlusConfig:
    return ServiceDeskPlusConfig(
        enabled=enabled,
        deployment="onprem",
        base_url="https://hd.exactforestall.com",
        portal=None,
        authtoken="secret-token",
        oauth_access_token=None,
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