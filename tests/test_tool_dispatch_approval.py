from unittest.mock import MagicMock

import pytest

import tool_dispatch as tool_dispatch_module
from agent_types import ToolCall, ToolSpec
from approval import ApprovalAction, ApprovalResponse
from permissions import PermissionContext, PermissionMode, PermissionRuleSet
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
    )


def test_write_file_ask_yes_shows_preview_and_executes(
    monkeypatch,
    mock_working_directory,
    permission_context,
):
    mocked_write = MagicMock(return_value={"ok": True})
    mocked_preview = MagicMock(return_value="PREVIEW TEXT")
    mocked_print_preview = MagicMock()
    mocked_prompt = MagicMock(return_value=ApprovalResponse(ApprovalAction.ALLOW_ONCE))

    monkeypatch.setattr(
        tool_dispatch_module,
        "get_tool_definition",
        lambda name: make_definition(name, mocked_write),
    )
    monkeypatch.setattr(tool_dispatch_module, "build_write_preview", mocked_preview)
    monkeypatch.setattr(tool_dispatch_module, "print_mutation_preview", mocked_print_preview)
    monkeypatch.setattr(tool_dispatch_module, "approval_prompt", mocked_prompt)

    result = tool_dispatch_module.execute_tool_call(
        ToolCall(
            name="write_file",
            args={"file_path": "notes.txt", "content": "hello"},
        ),
        mock_working_directory,
        permission_context,
    )

    assert result.payload["result"] == {"ok": True}

    mocked_preview.assert_called_once_with(
        mock_working_directory,
        "notes.txt",
        "hello",
    )
    mocked_print_preview.assert_called_once_with(
        "write_file",
        "notes.txt",
        "PREVIEW TEXT",
    )
    mocked_prompt.assert_called_once()

    tool_name, prompt_args = mocked_prompt.call_args.args
    assert tool_name == "write_file"
    assert prompt_args["file_path"] == "notes.txt"
    assert prompt_args["content"] == "hello"

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
    mocked_print_preview = MagicMock()
    mocked_prompt = MagicMock(return_value=ApprovalResponse(ApprovalAction.DENY))

    monkeypatch.setattr(
        tool_dispatch_module,
        "get_tool_definition",
        lambda name: make_definition(name, mocked_write),
    )
    monkeypatch.setattr(tool_dispatch_module, "build_write_preview", mocked_preview)
    monkeypatch.setattr(tool_dispatch_module, "print_mutation_preview", mocked_print_preview)
    monkeypatch.setattr(tool_dispatch_module, "approval_prompt", mocked_prompt)

    result = tool_dispatch_module.execute_tool_call(
        ToolCall(
            name="write_file",
            args={"file_path": "notes.txt", "content": "hello"},
        ),
        mock_working_directory,
        permission_context,
    )

    assert result.payload["error"] == "User denied write_file"

    mocked_preview.assert_called_once_with(
        mock_working_directory,
        "notes.txt",
        "hello",
    )
    mocked_print_preview.assert_called_once_with(
        "write_file",
        "notes.txt",
        "PREVIEW TEXT",
    )
    mocked_prompt.assert_called_once()
    mocked_write.assert_not_called()


def test_session_allow_tool_skips_second_prompt_for_write_file(
    monkeypatch,
    mock_working_directory,
    permission_context,
):
    mocked_write = MagicMock(return_value={"ok": True})
    mocked_preview = MagicMock(return_value="PREVIEW TEXT")
    mocked_print_preview = MagicMock()
    mocked_prompt = MagicMock(return_value=ApprovalResponse(ApprovalAction.ALLOW_TOOL_SESSION))

    monkeypatch.setattr(
        tool_dispatch_module,
        "get_tool_definition",
        lambda name: make_definition(name, mocked_write),
    )
    monkeypatch.setattr(tool_dispatch_module, "build_write_preview", mocked_preview)
    monkeypatch.setattr(tool_dispatch_module, "print_mutation_preview", mocked_print_preview)
    monkeypatch.setattr(tool_dispatch_module, "approval_prompt", mocked_prompt)

    first_result = tool_dispatch_module.execute_tool_call(
        ToolCall(
            name="write_file",
            args={"file_path": "first.txt", "content": "one"},
        ),
        mock_working_directory,
        permission_context,
    )

    second_result = tool_dispatch_module.execute_tool_call(
        ToolCall(
            name="write_file",
            args={"file_path": "second.txt", "content": "two"},
        ),
        mock_working_directory,
        permission_context,
    )

    assert first_result.payload["result"] == {"ok": True}
    assert second_result.payload["result"] == {"ok": True}
    assert "write_file" in permission_context.session_allow_tools
    assert mocked_prompt.call_count == 1
    assert mocked_print_preview.call_count == 1
    assert mocked_write.call_count == 2


def test_session_allow_path_applies_only_to_same_exec_path(
    monkeypatch,
    mock_working_directory,
    permission_context,
):
    mocked_run = MagicMock(return_value={"ok": True})
    mocked_prompt = MagicMock(
        side_effect=[
            ApprovalResponse(ApprovalAction.ALLOW_PATH_SESSION),
            ApprovalResponse(ApprovalAction.ALLOW_ONCE),
        ]
    )

    monkeypatch.setattr(
        tool_dispatch_module,
        "get_tool_definition",
        lambda name: make_definition(name, mocked_run),
    )
    monkeypatch.setattr(tool_dispatch_module, "approval_prompt", mocked_prompt)

    first_result = tool_dispatch_module.execute_tool_call(
        ToolCall(name="run_python_file", args={"file_path": "script.py"}),
        mock_working_directory,
        permission_context,
    )
    second_result = tool_dispatch_module.execute_tool_call(
        ToolCall(name="run_python_file", args={"file_path": "script.py"}),
        mock_working_directory,
        permission_context,
    )
    third_result = tool_dispatch_module.execute_tool_call(
        ToolCall(name="run_python_file", args={"file_path": "other.py"}),
        mock_working_directory,
        permission_context,
    )

    assert first_result.payload["result"] == {"ok": True}
    assert second_result.payload["result"] == {"ok": True}
    assert third_result.payload["result"] == {"ok": True}
    assert "script.py" in permission_context.session_allow_paths
    assert mocked_prompt.call_count == 2

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

    mocked_prompt = MagicMock(return_value=ApprovalResponse(ApprovalAction.ALLOW_ONCE))
    monkeypatch.setattr(tool_dispatch_module, "approval_prompt", mocked_prompt)

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
    )

    mocked_prompt.assert_not_called()
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

    mocked_prompt = MagicMock(return_value=ApprovalResponse(ApprovalAction.ALLOW_ONCE))
    mocked_print_preview = MagicMock()

    monkeypatch.setattr(tool_dispatch_module, "approval_prompt", mocked_prompt)
    monkeypatch.setattr(tool_dispatch_module, "print_mutation_preview", mocked_print_preview)

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
    )

    assert result.name == "update"
    assert result.payload["result"] == 'Successfully updated "sample.txt"'
    assert file_path.read_text(encoding="utf-8") == "alpha\ndelta\ngamma\n"
    mocked_prompt.assert_called_once()
    mocked_print_preview.assert_called_once()


def test_update_denied_without_feedback(monkeypatch, tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    permission_context = PermissionContext(
        mode=PermissionMode.DEFAULT,
        workspace=str(tmp_path),
        rules=PermissionRuleSet(),
    )

    monkeypatch.setattr(
        tool_dispatch_module,
        "approval_prompt",
        lambda function_name, args: ApprovalResponse(ApprovalAction.DENY),
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
    )

    assert result.name == "update"
    assert result.payload["error"] == "User denied update"
    assert file_path.read_text(encoding="utf-8") == "alpha\nbeta\ngamma\n"


def test_update_denied_with_feedback(monkeypatch, tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    permission_context = PermissionContext(
        mode=PermissionMode.DEFAULT,
        workspace=str(tmp_path),
        rules=PermissionRuleSet(),
    )

    monkeypatch.setattr(
        tool_dispatch_module,
        "approval_prompt",
        lambda function_name, args: ApprovalResponse(
            ApprovalAction.DENY_WITH_FEEDBACK,
            feedback="wrong file, create a new dedicated test file instead",
        ),
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
    )

    assert result.name == "update"
    assert result.payload == {
        "error": "User denied update",
        "denied_by_user": True,
        "feedback": "wrong file, create a new dedicated test file instead",
    }
    assert file_path.read_text(encoding="utf-8") == "alpha\nbeta\ngamma\n"
