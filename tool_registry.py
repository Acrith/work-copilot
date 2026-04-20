from dataclasses import dataclass
from typing import Any, Callable

from agent_types import ToolSpec

from functions.find_file import find_file
from functions.get_file_content import get_file_content
from functions.get_files_info import get_files_info
from functions.git_diff import git_diff
from functions.git_diff_file import git_diff_file
from functions.git_status import git_status
from functions.run_python_file import run_python_file
from functions.run_shell_command import run_shell_command
from functions.run_tests import run_tests
from functions.search_in_files import search_in_files
from functions.update_file import update_file
from functions.write_file import write_file


@dataclass(frozen=True)
class ToolDefinition:
    spec: ToolSpec
    handler: Callable[..., Any]


def string_property(description: str, *, nullable: bool = False) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "string",
        "description": description,
    }
    if nullable:
        schema["nullable"] = True
    return schema


def integer_property(description: str, *, nullable: bool = False) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "integer",
        "description": description,
    }
    if nullable:
        schema["nullable"] = True
    return schema


def boolean_property(description: str) -> dict[str, Any]:
    return {
        "type": "boolean",
        "description": description,
    }


def array_property(description: str, items: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "array",
        "description": description,
        "items": items,
    }


def object_schema(
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }

    if required is not None:
        schema["required"] = required

    return schema


TOOL_DEFINITIONS: dict[str, ToolDefinition] = {
    "get_files_info": ToolDefinition(
        spec=ToolSpec(
            name="get_files_info",
            description=(
                "Lists files in a specified directory relative to the working "
                "directory, providing file size and directory status"
            ),
            parameters=object_schema(
                {
                    "directory": string_property(
                        "Directory path to list files from, relative to the "
                        "working directory. Defaults to the working directory itself."
                    ),
                },
            ),
        ),
        handler=get_files_info,
    ),
    "get_file_content": ToolDefinition(
        spec=ToolSpec(
            name="get_file_content",
            description=(
                "Reads file content in a specified file path relative to the "
                "working directory"
            ),
            parameters=object_schema(
                {
                    "file_path": string_property(
                        "File path to read from, relative to the working directory"
                    ),
                },
                required=["file_path"],
            ),
        ),
        handler=get_file_content,
    ),
    "write_file": ToolDefinition(
        spec=ToolSpec(
            name="write_file",
            description=(
                "Write or overwrite content of a file in a specified file path "
                "relative to the working directory"
            ),
            parameters=object_schema(
                {
                    "file_path": string_property(
                        "File path to write to, relative to the working directory"
                    ),
                    "content": string_property(
                        "File content to write or overwrite into a file"
                    ),
                },
                required=["file_path", "content"],
            ),
        ),
        handler=write_file,
    ),
    "run_python_file": ToolDefinition(
        spec=ToolSpec(
            name="run_python_file",
            description=(
                "Executes a Python file in a specified file path relative to the "
                "working directory with optional arguments"
            ),
            parameters=object_schema(
                {
                    "file_path": string_property(
                        "File path to execute, relative to the working directory"
                    ),
                    "args": array_property(
                        "List of arguments to run Python file with",
                        string_property("Argument value"),
                    ),
                },
                required=["file_path"],
            ),
        ),
        handler=run_python_file,
    ),
    "search_in_files": ToolDefinition(
        spec=ToolSpec(
            name="search_in_files",
            description=(
                "Recursively search text files inside the working directory for "
                "a given text query and return the relative paths of matching files."
            ),
            parameters=object_schema(
                {
                    "query": string_property(
                        "The exact text to search for in file contents."
                    ),
                },
                required=["query"],
            ),
        ),
        handler=search_in_files,
    ),
    "run_tests": ToolDefinition(
        spec=ToolSpec(
            name="run_tests",
            description=(
                "Runs pytest in the workspace, optionally scoped to a specific "
                "test path or -k filter"
            ),
            parameters=object_schema(
                {
                    "test_path": string_property(
                        "Optional path to a test file or test directory, relative "
                        "to the working directory",
                        nullable=True,
                    ),
                    "keyword": string_property(
                        "Optional pytest -k expression to filter tests",
                        nullable=True,
                    ),
                    "max_failures": integer_property(
                        "Optional pytest --maxfail value",
                        nullable=True,
                    ),
                    "quiet": boolean_property("Whether to pass -q to pytest"),
                },
            ),
        ),
        handler=run_tests,
    ),
    "update": ToolDefinition(
        spec=ToolSpec(
            name="update",
            description=(
                "Replace one exact text block inside an existing file. Fails if "
                "the file is missing, the target text is missing, or the target "
                "text appears multiple times."
            ),
            parameters=object_schema(
                {
                    "file_path": string_property(
                        "File path relative to the working directory."
                    ),
                    "old_text": string_property("Exact existing text to replace."),
                    "new_text": string_property("Replacement text."),
                },
                required=["file_path", "old_text", "new_text"],
            ),
        ),
        handler=update_file,
    ),
    "find_file": ToolDefinition(
        spec=ToolSpec(
            name="find_file",
            description=(
                "Recursively search for filenames inside the working directory "
                "for a given text query and return the relative paths of matching files."
            ),
            parameters=object_schema(
                {
                    "query": string_property(
                        "The exact text to search for in filenames."
                    ),
                },
                required=["query"],
            ),
        ),
        handler=find_file,
    ),
    "git_status": ToolDefinition(
        spec=ToolSpec(
            name="git_status",
            description=(
                "Inspect the git repository in the workspace and return a compact "
                "human-readable summary of repository status."
            ),
            parameters=object_schema({}, required=[]),
        ),
        handler=git_status,
    ),
    "git_diff_file": ToolDefinition(
        spec=ToolSpec(
            name="git_diff_file",
            description=(
                "Show the current git diff for one file inside the workspace. "
                "Returns a readable diff or a clear error."
            ),
            parameters=object_schema(
                {
                    "file_path": string_property(
                        "Path to the file, relative to the working directory."
                    ),
                },
                required=["file_path"],
            ),
        ),
        handler=git_diff_file,
    ),
    "git_diff": ToolDefinition(
        spec=ToolSpec(
            name="git_diff",
            description=(
                "Inspect the local git repository inside the provided workspace "
                "and return the current repository-wide git diff as a string."
            ),
            parameters=object_schema({}, required=[]),
        ),
        handler=git_diff,
    ),
    "bash": ToolDefinition(
        spec=ToolSpec(
            name="bash",
            description="Executes a shell command.",
            parameters=object_schema(
                {
                    "command": string_property("The shell command to execute."),
                    "cwd": string_property(
                        "The current working directory for the command. Defaults "
                        "to the workspace root.",
                        nullable=True,
                    ),
                    "timeout_seconds": integer_property(
                        "The maximum time in seconds to wait for the command to "
                        "complete. Defaults to 30 seconds.",
                        nullable=True,
                    ),
                },
                required=["command"],
            ),
        ),
        handler=run_shell_command,
    ),
}


def get_tool_definitions() -> dict[str, ToolDefinition]:
    return TOOL_DEFINITIONS


def get_tool_definition(name: str) -> ToolDefinition:
    return TOOL_DEFINITIONS[name]


def get_tool_specs() -> list[ToolSpec]:
    return [definition.spec for definition in TOOL_DEFINITIONS.values()]