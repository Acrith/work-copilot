from __future__ import annotations

import json
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

import pytest

import connectors.servicedeskplus.client as client_module
from connectors.servicedeskplus.client import (
    ServiceDeskPlusClient,
    ServiceDeskPlusError,
)
from connectors.servicedeskplus.config import ServiceDeskPlusConfig


def make_config(
    *,
    base_url: str | None = "https://hd.exactforestall.com/",
    authtoken: str | None = "secret-token",
) -> ServiceDeskPlusConfig:
    return ServiceDeskPlusConfig(
        enabled=True,
        deployment="onprem",
        base_url=base_url,
        portal=None,
        authtoken=authtoken,
        oauth_access_token=None,
        default_request_filter="Open_System",
    )


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def read(self) -> bytes:
        return self.body


def test_list_request_filters_calls_expected_endpoint_and_headers(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(
            b'{"list_view_filters": [{"name": "Open Requests"}]}'
        )

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    result = client.list_request_filters()

    assert result == {"list_view_filters": [{"name": "Open Requests"}]}

    request = captured["request"]
    parsed_url = urlparse(request.full_url)

    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "hd.exactforestall.com"
    assert parsed_url.path == "/api/v3/list_view_filters/show_all"
    assert captured["timeout"] == 30

    query = parse_qs(parsed_url.query)
    assert "input_data" in query

    input_data = json.loads(query["input_data"][0])

    assert input_data == {
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

    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["accept"] == "application/vnd.manageengine.sdp.v3+json"
    assert headers["content-type"] == "application/x-www-form-urlencoded"
    assert headers["authtoken"] == "secret-token"


def test_missing_base_url_raises_clean_error():
    client = ServiceDeskPlusClient(make_config(base_url=None))

    with pytest.raises(ServiceDeskPlusError, match="SDP_BASE_URL"):
        client.list_request_filters()


def test_missing_authtoken_raises_clean_error():
    client = ServiceDeskPlusClient(make_config(authtoken=None))

    with pytest.raises(ServiceDeskPlusError, match="SDP_AUTHTOKEN"):
        client.list_request_filters()


def test_http_error_is_wrapped(monkeypatch):
    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},
            BytesIO(b'{"error": "bad token"}'),
        )

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    with pytest.raises(ServiceDeskPlusError, match="HTTP 401"):
        client.list_request_filters()


def test_url_error_is_wrapped(monkeypatch):
    def fake_urlopen(request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    with pytest.raises(ServiceDeskPlusError, match="Could not connect"):
        client.list_request_filters()


def test_invalid_json_is_wrapped(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse(b"not json")

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    with pytest.raises(ServiceDeskPlusError, match="invalid JSON"):
        client.list_request_filters()


def test_list_requests_calls_expected_endpoint_and_input_data(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(
            b'{"requests": [{"id": "123", "subject": "Test request"}]}'
        )

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    result = client.list_requests(
        filter_name="Open Requests",
        row_count=20,
        start_index=2,
    )

    assert result == {"requests": [{"id": "123", "subject": "Test request"}]}

    request = captured["request"]
    parsed_url = urlparse(request.full_url)

    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "hd.exactforestall.com"
    assert parsed_url.path == "/api/v3/requests"
    assert captured["timeout"] == 30

    query = parse_qs(parsed_url.query)
    assert "input_data" in query

    input_data = json.loads(query["input_data"][0])

    assert input_data == {
        "list_info": {
            "row_count": 20,
            "start_index": 2,
            "sort_field": "created_time",
            "sort_order": "desc",
            "filter_by": {
                "name": "Open Requests",
            },
        },
    }


def test_list_requests_caps_row_count(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse(b'{"requests": []}')

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    client.list_requests(row_count=999)

    parsed_url = urlparse(captured["request"].full_url)
    query = parse_qs(parsed_url.query)
    input_data = json.loads(query["input_data"][0])

    assert input_data["list_info"]["row_count"] == 50