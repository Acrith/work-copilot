from approval import ApprovalAction, ApprovalRequest, ApprovalResponse, parse_approval_action


def test_parse_approval_action_accepts_valid_choices():
    assert parse_approval_action("y") == ApprovalAction.ALLOW_ONCE
    assert parse_approval_action("n") == ApprovalAction.DENY
    assert parse_approval_action("f") == ApprovalAction.DENY_WITH_FEEDBACK
    assert parse_approval_action("s") == ApprovalAction.ALLOW_TOOL_SESSION
    assert parse_approval_action("p") == ApprovalAction.ALLOW_PATH_SESSION


def test_parse_approval_action_normalizes_input():
    assert parse_approval_action(" Y ") == ApprovalAction.ALLOW_ONCE


def test_parse_approval_action_rejects_invalid_choice():
    assert parse_approval_action("x") is None


def test_approval_request_stores_preview_fields():
    request = ApprovalRequest(
        function_name="write_file",
        args={"file_path": "notes.txt", "content": "hello"},
        preview_path="notes.txt",
        preview="PREVIEW",
    )

    assert request.function_name == "write_file"
    assert request.args["file_path"] == "notes.txt"
    assert request.preview_path == "notes.txt"
    assert request.preview == "PREVIEW"


def test_approval_response_stores_feedback():
    response = ApprovalResponse(
        action=ApprovalAction.DENY_WITH_FEEDBACK,
        feedback="stop here",
    )

    assert response.action == ApprovalAction.DENY_WITH_FEEDBACK
    assert response.feedback == "stop here"
