# tests/test_textual_approval.py

from threading import Event

from approval import ApprovalAction, ApprovalRequest, ApprovalResponse
from textual_approval import TextualApprovalHandler


def test_textual_approval_handler_returns_callback_response():
    captured = {}

    def request_callback(request: ApprovalRequest, approval_event: Event) -> None:
        captured["request"] = request
        captured["approval_event"] = approval_event
        captured["response"] = ApprovalResponse(action=ApprovalAction.ALLOW_ONCE)
        approval_event.set()

    def response_getter() -> ApprovalResponse | None:
        return captured["response"]

    handler = TextualApprovalHandler(
        request_callback=request_callback,
        response_getter=response_getter,
    )

    request = ApprovalRequest(
        function_name="write_file",
        args={"file_path": "example.txt"},
    )

    response = handler.request_approval(request)

    assert captured["request"] is request
    assert response.action == ApprovalAction.ALLOW_ONCE


def test_textual_approval_handler_denies_if_callback_returns_no_response():
    def request_callback(request: ApprovalRequest, approval_event: Event) -> None:
        approval_event.set()

    def response_getter() -> ApprovalResponse | None:
        return None

    handler = TextualApprovalHandler(
        request_callback=request_callback,
        response_getter=response_getter,
    )

    response = handler.request_approval(
        ApprovalRequest(
            function_name="write_file",
            args={"file_path": "example.txt"},
        )
    )

    assert response.action == ApprovalAction.DENY
    assert response.feedback


def test_textual_approval_handler_can_return_feedback_response():
    captured = {}

    def request_callback(request: ApprovalRequest, approval_event: Event) -> None:
        captured["response"] = ApprovalResponse(
            action=ApprovalAction.DENY_WITH_FEEDBACK,
            feedback="Do not create that file.",
        )
        approval_event.set()

    def response_getter() -> ApprovalResponse | None:
        return captured["response"]

    handler = TextualApprovalHandler(
        request_callback=request_callback,
        response_getter=response_getter,
    )

    response = handler.request_approval(
        ApprovalRequest(
            function_name="write_file",
            args={"file_path": "example.txt"},
        )
    )

    assert response.action == ApprovalAction.DENY_WITH_FEEDBACK
    assert response.feedback == "Do not create that file."


def test_textual_approval_handler_can_return_allow_tool_session():
    captured = {}

    def request_callback(request: ApprovalRequest, approval_event: Event) -> None:
        captured["response"] = ApprovalResponse(
            action=ApprovalAction.ALLOW_TOOL_SESSION,
        )
        approval_event.set()

    def response_getter() -> ApprovalResponse | None:
        return captured["response"]

    handler = TextualApprovalHandler(
        request_callback=request_callback,
        response_getter=response_getter,
    )

    response = handler.request_approval(
        ApprovalRequest(
            function_name="write_file",
            args={"file_path": "example.txt"},
            preview_path="example.txt",
        )
    )

    assert response.action == ApprovalAction.ALLOW_TOOL_SESSION


def test_textual_approval_handler_can_return_allow_path_session():
    captured = {}

    def request_callback(request: ApprovalRequest, approval_event: Event) -> None:
        captured["response"] = ApprovalResponse(
            action=ApprovalAction.ALLOW_PATH_SESSION,
        )
        approval_event.set()

    def response_getter() -> ApprovalResponse | None:
        return captured["response"]

    handler = TextualApprovalHandler(
        request_callback=request_callback,
        response_getter=response_getter,
    )

    response = handler.request_approval(
        ApprovalRequest(
            function_name="write_file",
            args={"file_path": "example.txt"},
            preview_path="example.txt",
        )
    )

    assert response.action == ApprovalAction.ALLOW_PATH_SESSION