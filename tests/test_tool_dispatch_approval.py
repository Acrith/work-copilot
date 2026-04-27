from unittest.mock import MagicMock

import pytest

import tool_dispatch as tool_dispatch_module
from agent_types import ToolCall, ToolSpec
from approval import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalResponse,
)
from permissions import Decision, PermissionContext, PermissionMode, PermissionRuleSet
from tool_categories import ToolCategory
from tool_registry import ToolDefinition


@pytest.fixture
def mock_working_directory(tmp_path):
    return str(tmp_path)


@pytest.fixture
def permission_context(mock_working_directory):
    return PermissionContext(
        mode=PermissionMode.DEFAULT,
        workspace=mock_working_directory,
        rules=PermissionRuleSet(),
    )


def make_definition(name, handler):
    category_by_name = {
        "get_file_content": ToolCategory.READ,
        "get_files_info": ToolCategory.READ,
        "search_in_files": ToolCategory.READ,
        "find_file": ToolCategory.READ,
        "git_status": ToolCategory.READ,
        "git_diff_file": ToolCategory.READ,
        "write_file": ToolCategory.WRITE,
        "update": ToolCategory.WRITE,
        "run_python_file": ToolCategory.EXEC,
        "run_tests": ToolCategory.EXEC,
        "bash": ToolCategory.EXEC,
    }

    return ToolDefinition(
        spec=ToolSpec(
            name=name,
            description="Test tool",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        handler=handler,
        category=category_by_name.get(name, ToolCategory.EXEC),
    )


class FakeApprovalHandler:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests: list[ApprovalRequest] = []

    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        self.requests.append(request)
        return self.responses.pop(0)


def test_write_file_ask_yes_shows_preview_and_executes(
    monkeypatch,
    mock_working_directory,
    permission_context,
):
    mocked_write = MagicMock(return_value={"ok": True})
    mocked_preview = MagicMock(return_value="PREVIEW TEXT")
    approval_handler = FakeApprovalHandler([ApprovalResponse(ApprovalAction.ALLOW_ONCE)])

    monkeypatch.setattr(
        tool_dispatch_module,
        "get_tool_definition",
        lambda name: make_definition(name, mocked_write),
    )
    monkeypatch.setattr(tool_dispatch_module, "build_write_preview", mocked_preview)

    result = tool_dispatch_module.execute_tool_call(
        ToolCall(
            name="write_file",
            args={"file_path": "notes.txt", "content": "hello"},
        ),
        mock_working_directory,
        permission_context,
        approval_handler=approval_handler,
    )

    assert result.payload["result"] == {"ok": True}

    mocked_preview.assert_called_once_with(
        mock_working_directory,
        "notes.txt",
        "hello",
    )

    assert len(approval_handler.requests) == 1
    request = approval_handler.requests[0]
    assert request.function_name == "write_file"
    assert request.args == {"file_path": "notes.txt", "content": "hello"}
    assert request.preview_path == "notes.txt"
    assert request.preview == "PREVIEW TEXT"

    mocked_write.assert_called_once_with(
        file_path="notes.txt",
        content="hello",
        working_directory=mock_working_directory,
    )


def test_write_file_ask_no_returns_error_and_does_not_execute(
    monkeypatch,
    mock_working_directory,
    permission_context,
):
    mocked_write = MagicMock(return_value={"ok": True})
    mocked_preview = MagicMock(return_value="PREVIEW TEXT")
    approval_handler = FakeApprovalHandler([ApprovalResponse(ApprovalAction.DENY)])

    monkeypatch.setattr(
        tool_dispatch_module,
        "get_tool_definition",
        lambda name: make_definition(name, mocked_write),
    )
    monkeypatch.setattr(tool_dispatch_module, "build_write_preview", mocked_preview)

    result = tool_dispatch_module.execute_tool_call(
        ToolCall(
            name="write_file",
            args={"file_path": "notes.txt", "content": "hello"},
        ),
        mock_working_directory,
        permission_context,
        approval_handler=approval_handler,
    )

    assert result.payload == {
        "error": "User denied write_file",
        "denied_by_user": True,
    }

    mocked_preview.assert_called_once_with(
        mock_working_directory,
        "notes.txt",
        "hello",
    )

    assert len(approval_handler.requests) == 1
    request = approval_handler.requests[0]
    assert request.function_name == "write_file"
    assert request.preview_path == "notes.txt"
    assert request.preview == "PREVIEW TEXT"

    mocked_write.assert_not_called()


def test_session_allow_tool_skips_second_prompt_for_write_file(
    monkeypatch,
    mock_working_directory,
    permission_context,
):
    mocked_write = MagicMock(return_value={"ok": True})
    mocked_preview = MagicMock(return_value="PREVIEW TEXT")
    approval_handler = FakeApprovalHandler([ApprovalResponse(ApprovalAction.ALLOW_TOOL_SESSION)])

    monkeypatch.setattr(
        tool_dispatch_module,
        "get_tool_definition",
        lambda name: make_definition(name, mocked_write),
    )
    monkeypatch.setattr(tool_dispatch_module, "build_write_preview", mocked_preview)

    first_result = tool_dispatch_module.execute_tool_call(
        ToolCall(
            name="write_file",
            args={"file_path": "first.txt", "content": "one"},
        ),
        mock_working_directory,
        permission_context,
        approval_handler=approval_handler,
    )

    second_result = tool_dispatch_module.execute_tool_call(
        ToolCall(
            name="write_file",
            args={"file_path": "second.txt", "content": "two"},
        ),
        mock_working_directory,
        permission_context,
        approval_handler=approval_handler,
    )

    assert first_result.payload["result"] == {"ok": True}
    assert second_result.payload["result"] == {"ok": True}
    assert "write_file" in permission_context.session_allow_tools
    assert len(approval_handler.requests) == 1
    assert mocked_preview.call_count == 1
    assert mocked_write.call_count == 2


def test_session_allow_path_applies_only_to_same_exec_path(
    monkeypatch,
    mock_working_directory,
    permission_context,
):
    mocked_run = MagicMock(return_value={"ok": True})
    approval_handler = FakeApprovalHandler(
        [
            ApprovalResponse(ApprovalAction.ALLOW_PATH_SESSION),
            ApprovalResponse(ApprovalAction.ALLOW_ONCE),
        ]
    )

    monkeypatch.setattr(
        tool_dispatch_module,
        "get_tool_definition",
        lambda name: make_definition(name, mocked_run),
    )

    first_result = tool_dispatch_module.execute_tool_call(
        ToolCall(name="run_python_file", args={"file_path": "script.py"}),
        mock_working_directory,
        permission_context,
        approval_handler=approval_handler,
    )
    second_result = tool_dispatch_module.execute_tool_call(
        ToolCall(name="run_python_file", args={"file_path": "script.py"}),
        mock_working_directory,
        permission_context,
        approval_handler=approval_handler,
    )
    third_result = tool_dispatch_module.execute_tool_call(
        ToolCall(name="run_python_file", args={"file_path": "other.py"}),
        mock_working_directory,
        permission_context,
        approval_handler=approval_handler,
    )

    assert first_result.payload["result"] == {"ok": True}
    assert second_result.payload["result"] == {"ok": True}
    assert third_result.payload["result"] == {"ok": True}
    assert "script.py" in permission_context.session_allow_paths
    assert len(approval_handler.requests) == 2

    mocked_run.assert_any_call(
        file_path="script.py",
        working_directory=mock_working_directory,
    )
    mocked_run.assert_any_call(
        file_path="other.py",
        working_directory=mock_working_directory,
    )
    assert mocked_run.call_count == 3


def test_invalid_update_skips_approval(monkeypatch, tmp_path):
    permission_context = PermissionContext(
        mode=PermissionMode.DEFAULT,
        workspace=str(tmp_path),
        rules=PermissionRuleSet(),
    )

    approval_handler = FakeApprovalHandler([ApprovalResponse(ApprovalAction.ALLOW_ONCE)])

    result = tool_dispatch_module.execute_tool_call(
        ToolCall(
            name="update",
            args={
                "file_path": "missing.txt",
                "old_text": "a",
                "new_text": "b",
            },
        ),
        str(tmp_path),
        permission_context,
        approval_handler=approval_handler,
    )

    assert len(approval_handler.requests) == 0
    assert result.name == "update"
    assert result.payload["result"] == (
        'Error: File not found: "missing.txt". '
        "Use find_file or get_files_info to locate the correct path."
    )


def test_valid_update_asks_approval(monkeypatch, tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    permission_context = PermissionContext(
        mode=PermissionMode.DEFAULT,
        workspace=str(tmp_path),
        rules=PermissionRuleSet(),
    )

    approval_handler = FakeApprovalHandler([ApprovalResponse(ApprovalAction.ALLOW_ONCE)])

    result = tool_dispatch_module.execute_tool_call(
        ToolCall(
            name="update",
            args={
                "file_path": "sample.txt",
                "old_text": "beta",
                "new_text": "delta",
            },
        ),
        str(tmp_path),
        permission_context,
        approval_handler=approval_handler,
    )

    assert result.name == "update"
    assert result.payload["result"] == 'Successfully updated "sample.txt"'
    assert file_path.read_text(encoding="utf-8") == "alpha\ndelta\ngamma\n"

    assert len(approval_handler.requests) == 1
    request = approval_handler.requests[0]
    assert request.function_name == "update"
    assert request.preview_path == "sample.txt"
    assert request.preview is not None


def test_update_denied_without_feedback(monkeypatch, tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    permission_context = PermissionContext(
        mode=PermissionMode.DEFAULT,
        workspace=str(tmp_path),
        rules=PermissionRuleSet(),
    )

    approval_handler = FakeApprovalHandler([ApprovalResponse(ApprovalAction.DENY)])

    result = tool_dispatch_module.execute_tool_call(
        ToolCall(
            name="update",
            args={
                "file_path": "sample.txt",
                "old_text": "beta",
                "new_text": "delta",
            },
        ),
        str(tmp_path),
        permission_context,
        approval_handler=approval_handler,
    )

    assert result.name == "update"
    assert result.payload == {
        "error": "User denied update",
        "denied_by_user": True,
    }
    assert file_path.read_text(encoding="utf-8") == "alpha\nbeta\ngamma\n"


def test_update_denied_with_feedback(monkeypatch, tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    permission_context = PermissionContext(
        mode=PermissionMode.DEFAULT,
        workspace=str(tmp_path),
        rules=PermissionRuleSet(),
    )

    approval_handler = FakeApprovalHandler(
        [
            ApprovalResponse(
                ApprovalAction.DENY_WITH_FEEDBACK,
                feedback="wrong file, create a new dedicated test file instead",
            )
        ]
    )

    result = tool_dispatch_module.execute_tool_call(
        ToolCall(
            name="update",
            args={
                "file_path": "sample.txt",
                "old_text": "beta",
                "new_text": "delta",
            },
        ),
        str(tmp_path),
        permission_context,
        approval_handler=approval_handler,
    )

    assert result.name == "update"
    assert result.payload == {
        "error": "User denied update",
        "denied_by_user": True,
        "feedback": "wrong file, create a new dedicated test file instead",
    }
    assert file_path.read_text(encoding="utf-8") == "alpha\nbeta\ngamma\n"


def test_execute_ask_tool_without_approval_handler_returns_error(tmp_path):
    result = tool_dispatch_module.execute_tool_call(
        ToolCall(name="bash", args={"command": "echo hello"}),
        str(tmp_path),
        PermissionContext(
            mode=PermissionMode.DEFAULT,
            workspace=str(tmp_path),
            rules=PermissionRuleSet(),
        ),
    )

    assert result.payload == {"error": "No approval handler configured for bash"}


def test_connector_write_ask_shows_connector_preview_and_executes(
    monkeypatch,
    mock_working_directory,
    permission_context,
):
    mocked_tool = MagicMock(return_value={"ok": True})
    approval_handler = FakeApprovalHandler([ApprovalResponse(ApprovalAction.ALLOW_ONCE)])

    monkeypatch.setattr(
        tool_dispatch_module,
        "evaluate_request",
        lambda ctx, function_name, args: Decision.ASK,
    )
    monkeypatch.setattr(
        tool_dispatch_module,
        "get_tool_definition",
        lambda name: make_definition(name, mocked_tool),
    )

    result = tool_dispatch_module.execute_tool_call(
        ToolCall(
            name="servicedesk_add_request_draft",
            args={
                "request_id": "55776",
                "subject": "Re: Test subject",
                "description": "Hello from draft",
            },
        ),
        mock_working_directory,
        permission_context,
        approval_handler=approval_handler,
    )

    assert result.payload["result"] == {"ok": True}

    assert len(approval_handler.requests) == 1
    request = approval_handler.requests[0]

    assert request.function_name == "servicedesk_add_request_draft"
    assert request.args == {
        "request_id": "55776",
        "subject": "Re: Test subject",
        "description": "Hello from draft",
    }
    assert request.preview_path is None
    assert request.preview is not None
    assert "# ServiceDesk draft reply" in request.preview
    assert "**Action:** Save draft reply" in request.preview
    assert "**Ticket:** 55776" in request.preview
    assert "**Type:** reply" in request.preview
    assert "## Subject" in request.preview
    assert "Re: Test subject" in request.preview
    assert "## Draft body" in request.preview
    assert "Hello from draft" in request.preview
    assert "## Safety" in request.preview
    assert "This will save a draft in ServiceDesk Plus." in request.preview
    assert "It will not send the reply to the requester." in request.preview

    mocked_tool.assert_called_once_with(
        request_id="55776",
        subject="Re: Test subject",
        description="Hello from draft",
        working_directory=mock_working_directory,
    )