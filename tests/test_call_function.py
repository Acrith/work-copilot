import pytest
from unittest.mock import MagicMock
from google.genai import types
import functions.call_function as call_function_module
from permissions import PermissionContext, PermissionMode, PermissionRuleSet


def mock_dispatched_function(**kwargs):
    return {"mock_result": "success", "args": kwargs}


@pytest.fixture
def mock_working_directory():
    return "/tmp/test_dir"


@pytest.fixture
def permission_context(mock_working_directory):
    return PermissionContext(
        mode=PermissionMode.DEFAULT,
        workspace=mock_working_directory,
        rules=PermissionRuleSet(),
    )


def create_function_call(name, args=None):
    return types.FunctionCall(name=name, args=args or {})


def test_dispatches_known_function_and_passes_working_directory(monkeypatch, mock_working_directory, permission_context):
    mocked = MagicMock(side_effect=mock_dispatched_function)
    monkeypatch.setattr(call_function_module, "get_file_content", mocked)

    function_call = create_function_call("get_file_content", {"file_path": "test.txt"})
    response = call_function_module.call_function(function_call, mock_working_directory, permission_context)

    assert response.parts[0].function_response.name == "get_file_content"

    result = response.parts[0].function_response.response["result"]
    assert result["mock_result"] == "success"
    assert result["args"]["file_path"] == "test.txt"
    assert result["args"]["working_directory"] == mock_working_directory

    mocked.assert_called_once_with(
        file_path="test.txt",
        working_directory=mock_working_directory,
    )


def test_unknown_function_name_returns_error(mock_working_directory, permission_context):
    function_call = create_function_call("non_existent_function")
    response = call_function_module.call_function(function_call, mock_working_directory, permission_context)

    assert response.parts[0].function_response.name == "non_existent_function"
    assert response.parts[0].function_response.response["error"] == (
        "Unknown function: non_existent_function"
    )


def test_missing_arguments_are_forwarded_as_is(monkeypatch, mock_working_directory, permission_context):
    mocked = MagicMock(side_effect=mock_dispatched_function)
    monkeypatch.setattr(call_function_module, "get_file_content", mocked)

    function_call = create_function_call("get_file_content", {})
    response = call_function_module.call_function(function_call, mock_working_directory, permission_context)

    result = response.parts[0].function_response.response["result"]
    assert result["args"]["working_directory"] == mock_working_directory
    assert "file_path" not in result["args"]

    mocked.assert_called_once_with(
        working_directory=mock_working_directory,
    )