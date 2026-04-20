from google.genai import types

import functions.call_function as call_function_module
from agent_types import ToolResult
from permissions import PermissionContext, PermissionMode, PermissionRuleSet


def create_function_call(name, args=None):
    return types.FunctionCall(name=name, args=args or {})


def make_permission_context(workspace: str):
    return PermissionContext(
        mode=PermissionMode.DEFAULT,
        workspace=workspace,
        rules=PermissionRuleSet(),
    )


def test_call_function_converts_gemini_call_to_neutral_tool_call(monkeypatch, tmp_path):
    captured = {}

    def fake_execute_tool_call(tool_call, working_directory, permission_context, verbose=False):
        captured["tool_call"] = tool_call
        captured["working_directory"] = working_directory
        captured["permission_context"] = permission_context
        captured["verbose"] = verbose

        return ToolResult(
            name=tool_call.name,
            payload={"result": {"ok": True}},
        )

    monkeypatch.setattr(
        call_function_module,
        "execute_tool_call",
        fake_execute_tool_call,
    )

    permission_context = make_permission_context(str(tmp_path))
    function_call = create_function_call(
        "get_file_content",
        {"file_path": "sample.txt"},
    )

    response = call_function_module.call_function(
        function_call,
        str(tmp_path),
        permission_context,
        verbose=True,
    )

    assert captured["tool_call"].name == "get_file_content"
    assert captured["tool_call"].args == {"file_path": "sample.txt"}
    assert captured["working_directory"] == str(tmp_path)
    assert captured["permission_context"] is permission_context
    assert captured["verbose"] is True

    function_response = response.parts[0].function_response
    assert function_response.name == "get_file_content"
    assert function_response.response == {"result": {"ok": True}}


def test_call_function_handles_missing_args(monkeypatch, tmp_path):
    captured = {}

    def fake_execute_tool_call(tool_call, working_directory, permission_context, verbose=False):
        captured["tool_call"] = tool_call

        return ToolResult(
            name=tool_call.name,
            payload={"result": "ok"},
        )

    monkeypatch.setattr(
        call_function_module,
        "execute_tool_call",
        fake_execute_tool_call,
    )

    permission_context = make_permission_context(str(tmp_path))
    function_call = create_function_call("get_files_info")

    response = call_function_module.call_function(
        function_call,
        str(tmp_path),
        permission_context,
    )

    assert captured["tool_call"].name == "get_files_info"
    assert captured["tool_call"].args == {}

    function_response = response.parts[0].function_response
    assert function_response.name == "get_files_info"
    assert function_response.response == {"result": "ok"}


def test_call_function_wraps_dispatch_error_as_gemini_tool_response(tmp_path):
    permission_context = make_permission_context(str(tmp_path))
    function_call = create_function_call("non_existent_function")

    response = call_function_module.call_function(
        function_call,
        str(tmp_path),
        permission_context,
    )

    function_response = response.parts[0].function_response
    assert function_response.name == "non_existent_function"
    assert function_response.response == {
        "error": "Unknown function: non_existent_function"
    }


def test_available_functions_is_gemini_tool():
    assert isinstance(call_function_module.available_functions, types.Tool)
    assert call_function_module.available_functions.function_declarations