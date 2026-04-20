from agent_types import ToolCall
from permissions import PermissionContext, PermissionMode, PermissionRuleSet
from tool_dispatch import execute_tool_call


def make_context(workspace: str) -> PermissionContext:
    return PermissionContext(
        mode=PermissionMode.DEFAULT,
        workspace=workspace,
        rules=PermissionRuleSet(),
    )


def test_execute_unknown_tool_returns_error(tmp_path):
    result = execute_tool_call(
        ToolCall(name="nope", args={}),
        str(tmp_path),
        make_context(str(tmp_path)),
    )

    assert result.name == "nope"
    assert "error" in result.payload


def test_execute_read_tool_returns_result(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")

    result = execute_tool_call(
        ToolCall(name="get_file_content", args={"file_path": "sample.txt"}),
        str(tmp_path),
        make_context(str(tmp_path)),
    )

    assert result.name == "get_file_content"
    assert result.payload == {"result": "hello"}


def test_execute_denied_tool_returns_error(tmp_path):
    result = execute_tool_call(
        ToolCall(
            name="bash",
            args={
                "command": "echo nope",
                "cwd": ".git",
            },
        ),
        str(tmp_path),
        make_context(str(tmp_path)),
    )

    assert result.name == "bash"
    assert "error" in result.payload
    assert "Permission denied" in result.payload["error"]


def test_execute_tool_preserves_call_id(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")

    result = execute_tool_call(
        ToolCall(
            name="get_file_content",
            args={"file_path": "sample.txt"},
            call_id="call_123",
        ),
        str(tmp_path),
        make_context(str(tmp_path)),
    )

    assert result.name == "get_file_content"
    assert result.call_id == "call_123"
    assert result.payload == {"result": "hello"}
