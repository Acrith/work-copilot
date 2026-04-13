from unittest.mock import MagicMock

import pytest
from google.genai import types

import functions.call_function as call_function_module
from permissions import PermissionContext, PermissionMode, PermissionRuleSet


def create_function_call(name, args=None):
    return types.FunctionCall(name=name, args=args or {})


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


def test_write_file_ask_yes_shows_preview_and_executes(
    monkeypatch, mock_working_directory, permission_context
):
    mocked_write = MagicMock(return_value={"ok": True})
    mocked_preview = MagicMock(return_value="PREVIEW TEXT")
    mocked_print_preview = MagicMock()
    mocked_prompt = MagicMock(return_value=("y", None))

    monkeypatch.setattr(call_function_module, "write_file", mocked_write)
    monkeypatch.setattr(call_function_module, "build_write_preview", mocked_preview)
    monkeypatch.setattr(call_function_module, "print_write_preview", mocked_print_preview)
    monkeypatch.setattr(call_function_module, "approval_prompt", mocked_prompt)

    function_call = create_function_call(
        "write_file",
        {"file_path": "notes.txt", "content": "hello"},
    )

    response = call_function_module.call_function(
        function_call,
        mock_working_directory,
        permission_context,
    )

    payload = response.parts[0].function_response.response
    assert payload["result"] == {"ok": True}

    mocked_preview.assert_called_once_with(
        mock_working_directory,
        "notes.txt",
        "hello",
    )
    mocked_print_preview.assert_called_once_with("PREVIEW TEXT")

    mocked_prompt.assert_called_once()
    tool_name, prompt_args = mocked_prompt.call_args.args

    assert tool_name == "write_file"
    assert prompt_args["file_path"] == "notes.txt"
    assert prompt_args["content"] == "hello"
    assert prompt_args["working_directory"] == mock_working_directory

    mocked_write.assert_called_once_with(
        file_path="notes.txt",
        content="hello",
        working_directory=mock_working_directory,
    )


def test_write_file_ask_no_returns_error_and_does_not_execute(
    monkeypatch, mock_working_directory, permission_context
):
    mocked_write = MagicMock(return_value={"ok": True})
    mocked_preview = MagicMock(return_value="PREVIEW TEXT")
    mocked_print_preview = MagicMock()
    mocked_prompt = MagicMock(return_value=("n", None))

    monkeypatch.setattr(call_function_module, "write_file", mocked_write)
    monkeypatch.setattr(call_function_module, "build_write_preview", mocked_preview)
    monkeypatch.setattr(call_function_module, "print_write_preview", mocked_print_preview)
    monkeypatch.setattr(call_function_module, "approval_prompt", mocked_prompt)

    function_call = create_function_call(
        "write_file",
        {"file_path": "notes.txt", "content": "hello"},
    )

    response = call_function_module.call_function(
        function_call,
        mock_working_directory,
        permission_context,
    )

    payload = response.parts[0].function_response.response
    assert payload["error"] == "User denied write_file"

    mocked_preview.assert_called_once_with(
        mock_working_directory,
        "notes.txt",
        "hello",
    )
    mocked_print_preview.assert_called_once_with("PREVIEW TEXT")
    mocked_prompt.assert_called_once()
    mocked_write.assert_not_called()


def test_session_allow_tool_skips_second_prompt_for_write_file(
    monkeypatch, mock_working_directory, permission_context
):
    mocked_write = MagicMock(return_value={"ok": True})
    mocked_preview = MagicMock(return_value="PREVIEW TEXT")
    mocked_print_preview = MagicMock()
    mocked_prompt = MagicMock(return_value=("s", None))

    monkeypatch.setattr(call_function_module, "write_file", mocked_write)
    monkeypatch.setattr(call_function_module, "build_write_preview", mocked_preview)
    monkeypatch.setattr(call_function_module, "print_write_preview", mocked_print_preview)
    monkeypatch.setattr(call_function_module, "approval_prompt", mocked_prompt)

    first_call = create_function_call(
        "write_file",
        {"file_path": "first.txt", "content": "one"},
    )
    second_call = create_function_call(
        "write_file",
        {"file_path": "second.txt", "content": "two"},
    )

    first_response = call_function_module.call_function(
        first_call,
        mock_working_directory,
        permission_context,
    )
    second_response = call_function_module.call_function(
        second_call,
        mock_working_directory,
        permission_context,
    )

    assert first_response.parts[0].function_response.response["result"] == {"ok": True}
    assert second_response.parts[0].function_response.response["result"] == {"ok": True}

    assert "write_file" in permission_context.session_allow_tools
    assert mocked_prompt.call_count == 1
    assert mocked_print_preview.call_count == 1
    assert mocked_write.call_count == 2


def test_session_allow_path_applies_only_to_same_exec_path(
    monkeypatch, mock_working_directory, permission_context
):
    mocked_run = MagicMock(return_value={"ok": True})
    mocked_prompt = MagicMock(side_effect=[("p", None), ("y", None)])

    monkeypatch.setattr(call_function_module, "run_python_file", mocked_run)
    monkeypatch.setattr(call_function_module, "approval_prompt", mocked_prompt)

    first_call = create_function_call(
        "run_python_file",
        {"file_path": "script.py"},
    )
    second_call = create_function_call(
        "run_python_file",
        {"file_path": "script.py"},
    )
    third_call = create_function_call(
        "run_python_file",
        {"file_path": "other.py"},
    )

    first_response = call_function_module.call_function(
        first_call,
        mock_working_directory,
        permission_context,
    )
    second_response = call_function_module.call_function(
        second_call,
        mock_working_directory,
        permission_context,
    )
    third_response = call_function_module.call_function(
        third_call,
        mock_working_directory,
        permission_context,
    )

    assert first_response.parts[0].function_response.response["result"] == {"ok": True}
    assert second_response.parts[0].function_response.response["result"] == {"ok": True}
    assert third_response.parts[0].function_response.response["result"] == {"ok": True}

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

def test_update_denied_without_feedback(monkeypatch, tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    permission_context = PermissionContext(
        mode=PermissionMode.DEFAULT,
        workspace=str(tmp_path),
        rules=PermissionRuleSet(),
    )

    monkeypatch.setattr(
        call_function_module,
        "approval_prompt",
        lambda function_name, args: ("n", None),
    )

    function_call = create_function_call(
        "update",
        {
            "file_path": "sample.txt",
            "old_text": "beta",
            "new_text": "delta",
        },
    )

    response = call_function_module.call_function(
        function_call,
        str(tmp_path),
        permission_context,
    )

    assert response.parts[0].function_response.name == "update"
    assert response.parts[0].function_response.response["error"] == "User denied update"
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
        call_function_module,
        "approval_prompt",
        lambda function_name, args: (
            "f",
            "wrong file, create a new dedicated test file instead",
        ),
    )

    function_call = create_function_call(
        "update",
        {
            "file_path": "sample.txt",
            "old_text": "beta",
            "new_text": "delta",
        },
    )

    response = call_function_module.call_function(
        function_call,
        str(tmp_path),
        permission_context,
    )

    assert response.parts[0].function_response.name == "update"
    assert response.parts[0].function_response.response["error"] == (
        "User denied update: wrong file, create a new dedicated test file instead"
    )
    assert file_path.read_text(encoding="utf-8") == "alpha\nbeta\ngamma\n"