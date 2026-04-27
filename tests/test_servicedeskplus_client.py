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
    plain_text_to_basic_html,
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


def test_get_request_calls_expected_endpoint_and_headers(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(
            b'{"request": {"id": "55906", "subject": "Udostepnienie prezentacji"}}'
        )

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    result = client.get_request("55906")

    assert result == {
        "request": {
            "id": "55906",
            "subject": "Udostepnienie prezentacji",
        }
    }

    request = captured["request"]
    parsed_url = urlparse(request.full_url)

    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "hd.exactforestall.com"
    assert parsed_url.path == "/api/v3/requests/55906"
    assert parsed_url.query == ""
    assert captured["timeout"] == 30

    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["accept"] == "application/vnd.manageengine.sdp.v3+json"
    assert headers["content-type"] == "application/x-www-form-urlencoded"
    assert headers["authtoken"] == "secret-token"


def test_get_request_requires_request_id():
    client = ServiceDeskPlusClient(make_config())

    with pytest.raises(ServiceDeskPlusError, match="request_id is required"):
        client.get_request("")


def test_list_request_notes_calls_expected_endpoint_and_input_data(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(
            b'{"notes": [{"id": "note-1", "description": "Test note"}]}'
        )

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    result = client.list_request_notes(
        request_id="55906",
        row_count=10,
        start_index=2,
        sort_order="asc",
    )

    assert result == {"notes": [{"id": "note-1", "description": "Test note"}]}

    request = captured["request"]
    parsed_url = urlparse(request.full_url)

    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "hd.exactforestall.com"
    assert parsed_url.path == "/api/v3/requests/55906/notes"
    assert captured["timeout"] == 30

    query = parse_qs(parsed_url.query)
    assert "input_data" in query

    input_data = json.loads(query["input_data"][0])

    assert input_data == {
        "list_info": {
            "row_count": 10,
            "start_index": 2,
            "sort_field": "created_time",
            "sort_order": "asc",
        },
    }

    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["accept"] == "application/vnd.manageengine.sdp.v3+json"
    assert headers["content-type"] == "application/x-www-form-urlencoded"
    assert headers["authtoken"] == "secret-token"


def test_list_request_notes_caps_row_count(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse(b'{"notes": []}')

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    client.list_request_notes(request_id="55906", row_count=999)

    parsed_url = urlparse(captured["request"].full_url)
    query = parse_qs(parsed_url.query)
    input_data = json.loads(query["input_data"][0])

    assert input_data["list_info"]["row_count"] == 50


def test_list_request_notes_normalizes_start_index(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse(b'{"notes": []}')

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    client.list_request_notes(request_id="55906", start_index=-5)

    parsed_url = urlparse(captured["request"].full_url)
    query = parse_qs(parsed_url.query)
    input_data = json.loads(query["input_data"][0])

    assert input_data["list_info"]["start_index"] == 1


def test_list_request_notes_requires_request_id():
    client = ServiceDeskPlusClient(make_config())

    with pytest.raises(ServiceDeskPlusError, match="request_id is required"):
        client.list_request_notes(request_id="")


def test_get_request_attachments_returns_metadata(monkeypatch):
    def fake_get_request(self, request_id):
        assert request_id == "55906"
        return {
            "request": {
                "id": "55906",
                "subject": "Test ticket",
                "attachments": [
                    {
                        "id": "attachment-1",
                        "name": "screenshot.png",
                        "content_type": "image/png",
                        "size": "12345",
                    }
                ],
            }
        }

    monkeypatch.setattr(ServiceDeskPlusClient, "get_request", fake_get_request)

    client = ServiceDeskPlusClient(make_config())

    result = client.get_request_attachments("55906")

    assert result == {
        "request_id": "55906",
        "attachments": [
            {
                "id": "attachment-1",
                "name": "screenshot.png",
                "content_type": "image/png",
                "size": "12345",
            }
        ],
    }


def test_get_request_attachments_returns_empty_list_when_missing(monkeypatch):
    def fake_get_request(self, request_id):
        assert request_id == "55906"
        return {
            "request": {
                "id": "55906",
                "subject": "Test ticket",
            }
        }

    monkeypatch.setattr(ServiceDeskPlusClient, "get_request", fake_get_request)

    client = ServiceDeskPlusClient(make_config())

    result = client.get_request_attachments("55906")

    assert result == {
        "request_id": "55906",
        "attachments": [],
    }


def test_get_request_attachments_requires_request_id():
    client = ServiceDeskPlusClient(make_config())

    with pytest.raises(ServiceDeskPlusError, match="request_id is required"):
        client.get_request_attachments("")


def test_list_request_conversations_calls_expected_endpoint_and_input_data(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(
            b'{"conversations": [{"id": "conv-1", "description": "Test reply"}]}'
        )

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    result = client.list_request_conversations(
        request_id="55906",
        row_count=10,
        start_index=2,
        sort_order="asc",
    )

    assert result == {
        "conversations": [{"id": "conv-1", "description": "Test reply"}]
    }

    request = captured["request"]
    parsed_url = urlparse(request.full_url)

    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "hd.exactforestall.com"
    assert parsed_url.path == "/api/v3/requests/55906/_conversations"
    assert captured["timeout"] == 30

    query = parse_qs(parsed_url.query)
    assert "input_data" in query

    input_data = json.loads(query["input_data"][0])

    assert input_data == {
        "list_info": {
            "row_count": 10,
            "start_index": 2,
            "sort_order": "asc",
        },
        "system_notifications": False,
        "notes": True,
    }


def test_list_request_conversations_caps_row_count(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse(b'{"conversations": []}')

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    client.list_request_conversations(request_id="55906", row_count=999)

    parsed_url = urlparse(captured["request"].full_url)
    query = parse_qs(parsed_url.query)
    input_data = json.loads(query["input_data"][0])

    assert input_data["list_info"]["row_count"] == 50


def test_list_request_conversations_requires_request_id():
    client = ServiceDeskPlusClient(make_config())

    with pytest.raises(ServiceDeskPlusError, match="request_id is required"):
        client.list_request_conversations(request_id="")


def test_get_conversation_content_allows_relative_api_url(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse(b'{"description": "Conversation body"}')

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    result = client.get_conversation_content(
        "/api/v3/requests/55478/_conversations/296479/content"
    )

    assert result == {"description": "Conversation body"}

    parsed_url = urlparse(captured["request"].full_url)
    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "hd.exactforestall.com"
    assert parsed_url.path == "/api/v3/requests/55478/_conversations/296479/content"


def test_get_conversation_content_allows_same_host_absolute_api_url(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse(b'{"description": "Conversation body"}')

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    result = client.get_conversation_content(
        "https://hd.exactforestall.com/api/v3/requests/55478/_conversations/296479/content"
    )

    assert result == {"description": "Conversation body"}

    parsed_url = urlparse(captured["request"].full_url)
    assert parsed_url.netloc == "hd.exactforestall.com"
    assert parsed_url.path == "/api/v3/requests/55478/_conversations/296479/content"


def test_get_conversation_content_rejects_external_url():
    client = ServiceDeskPlusClient(make_config())

    with pytest.raises(ServiceDeskPlusError, match="configured ServiceDesk Plus host"):
        client.get_conversation_content(
            "https://example.com/api/v3/requests/55478/_conversations/296479/content"
        )


def test_get_conversation_content_rejects_non_api_path():
    client = ServiceDeskPlusClient(make_config())

    with pytest.raises(ServiceDeskPlusError, match="ServiceDesk API path"):
        client.get_conversation_content("/reports/private")


def test_get_conversation_content_requires_content_url():
    client = ServiceDeskPlusClient(make_config())

    with pytest.raises(ServiceDeskPlusError, match="content_url is required"):
        client.get_conversation_content("")


def test_plain_text_to_basic_html_escapes_and_preserves_line_breaks():
    result = plain_text_to_basic_html("hello & goodbye\n<script>alert(1)</script>")

    assert result == "hello &amp; goodbye<br />&lt;script&gt;alert(1)&lt;/script&gt;"


def test_post_sends_form_encoded_body_and_headers(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(b'{"response_status": {"status": "success"}}')

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    result = client.post(
        "/api/v3/example",
        data={"input_data": '{"hello": "world"}'},
    )

    assert result == {"response_status": {"status": "success"}}

    request = captured["request"]
    parsed_url = urlparse(request.full_url)

    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "hd.exactforestall.com"
    assert parsed_url.path == "/api/v3/example"
    assert request.get_method() == "POST"
    assert captured["timeout"] == 30

    body = request.data.decode("utf-8")
    parsed_body = parse_qs(body)
    assert parsed_body["input_data"] == ['{"hello": "world"}']

    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["accept"] == "application/vnd.manageengine.sdp.v3+json"
    assert headers["content-type"] == "application/x-www-form-urlencoded"
    assert headers["authtoken"] == "secret-token"


def test_post_with_input_data_sends_json_input_data(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse(b'{"ok": true}')

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    result = client.post_with_input_data(
        "/api/v3/example",
        {"draft": {"subject": "Test"}},
    )

    assert result == {"ok": True}

    body = captured["request"].data.decode("utf-8")
    parsed_body = parse_qs(body)
    input_data = json.loads(parsed_body["input_data"][0])

    assert input_data == {"draft": {"subject": "Test"}}


def test_add_request_draft_posts_expected_payload(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(
            b'{"draft": {"id": "draft-1"}, "response_status": {"status": "success"}}'
        )

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    result = client.add_request_draft(
        request_id="55776",
        subject="Re: Test subject",
        description="Line 1\nLine <2>",
    )

    assert result == {
        "draft": {"id": "draft-1"},
        "response_status": {"status": "success"},
    }

    request = captured["request"]
    parsed_url = urlparse(request.full_url)

    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "hd.exactforestall.com"
    assert parsed_url.path == "/api/v3/requests/55776/drafts"
    assert request.get_method() == "POST"
    assert captured["timeout"] == 30

    body = request.data.decode("utf-8")
    parsed_body = parse_qs(body)
    input_data = json.loads(parsed_body["input_data"][0])

    assert input_data == {
        "draft": {
            "type": "reply",
            "subject": "Re: Test subject",
            "description": "Line 1<br />Line &lt;2&gt;",
        }
    }


def test_add_request_draft_uses_custom_draft_type(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse(b'{"draft": {"id": "draft-1"}}')

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    client = ServiceDeskPlusClient(make_config())

    client.add_request_draft(
        request_id="55776",
        subject="Test",
        description="Body",
        draft_type="forward",
    )

    body = captured["request"].data.decode("utf-8")
    parsed_body = parse_qs(body)
    input_data = json.loads(parsed_body["input_data"][0])

    assert input_data["draft"]["type"] == "forward"


def test_add_request_draft_requires_request_id():
    client = ServiceDeskPlusClient(make_config())

    with pytest.raises(ServiceDeskPlusError, match="request_id is required"):
        client.add_request_draft(
            request_id="",
            subject="Test",
            description="Body",
        )


def test_add_request_draft_requires_subject():
    client = ServiceDeskPlusClient(make_config())

    with pytest.raises(ServiceDeskPlusError, match="subject is required"):
        client.add_request_draft(
            request_id="55776",
            subject="   ",
            description="Body",
        )


def test_add_request_draft_requires_description():
    client = ServiceDeskPlusClient(make_config())

    with pytest.raises(ServiceDeskPlusError, match="description is required"):
        client.add_request_draft(
            request_id="55776",
            subject="Test",
            description="   ",
        )