from agent_types import ToolSpec
from tool_registry import get_tool_definition, get_tool_specs


def test_tool_registry_returns_provider_neutral_specs():
    specs = get_tool_specs()

    assert specs
    assert all(isinstance(spec, ToolSpec) for spec in specs)


def test_tool_registry_contains_expected_tools():
    names = {spec.name for spec in get_tool_specs()}

    assert {
        "get_files_info",
        "get_file_content",
        "write_file",
        "run_python_file",
        "search_in_files",
        "run_tests",
        "update",
        "find_file",
        "git_status",
        "git_diff_file",
        "git_diff",
        "bash",
    } <= names


def test_get_tool_definition_returns_handler():
    definition = get_tool_definition("get_file_content")

    assert definition.spec.name == "get_file_content"
    assert callable(definition.handler)
