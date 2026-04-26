from dataclasses import dataclass
from typing import Any, Callable

from agent_types import ToolSpec
from connectors.servicedeskplus.tools import (
    servicedesk_get_request,
    servicedesk_get_request_attachments,
    servicedesk_get_request_notes,
    servicedesk_list_request_filters,
    servicedesk_list_requests,
    servicedesk_status,
)
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
from tool_categories import ToolCategory


@dataclass(frozen=True)
class ToolDefinition:
    spec: ToolSpec
    handler: Callable[..., Any]
    category: ToolCategory
    connector: str | None = None
    resource_type: str | None = None


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
        category=ToolCategory.READ,
    ),
    "get_file_content": ToolDefinition(
        spec=ToolSpec(
            name="get_file_content",
            description=(
                "Reads file content in a specified file path relative to the working directory"
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
        category=ToolCategory.READ,
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
                    "content": string_property("File content to write or overwrite into a file"),
                },
                required=["file_path", "content"],
            ),
        ),
        handler=write_file,
        category=ToolCategory.WRITE,
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
        category=ToolCategory.EXEC,
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
                    "query": string_property("The exact text to search for in file contents."),
                },
                required=["query"],
            ),
        ),
        handler=search_in_files,
        category=ToolCategory.READ,
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
        category=ToolCategory.EXEC,
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
                    "file_path": string_property("File path relative to the working directory."),
                    "old_text": string_property("Exact existing text to replace."),
                    "new_text": string_property("Replacement text."),
                },
                required=["file_path", "old_text", "new_text"],
            ),
        ),
        handler=update_file,
        category=ToolCategory.WRITE,
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
                    "query": string_property("The exact text to search for in filenames."),
                },
                required=["query"],
            ),
        ),
        handler=find_file,
        category=ToolCategory.READ,
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
        category=ToolCategory.READ,
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
        category=ToolCategory.READ,
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
        category=ToolCategory.READ,
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
        category=ToolCategory.EXEC,
    ),
    "servicedesk_status": ToolDefinition(
        spec=ToolSpec(
            name="servicedesk_status",
            description=(
                "Shows whether the ServiceDesk Plus connector is configured. "
                "Takes no arguments."
            ),
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        ),
        handler=servicedesk_status,
        category=ToolCategory.CONNECTOR_READ,
        connector="servicedeskplus",
        resource_type="connector_status",
    ),
    "servicedesk_list_request_filters": ToolDefinition(
        spec=ToolSpec(
            name="servicedesk_list_request_filters",
            description=(
                "Lists available ServiceDesk Plus request filters/views. "
                "This is a read-only connector tool and takes no arguments."
            ),
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        ),
        handler=servicedesk_list_request_filters,
        category=ToolCategory.CONNECTOR_READ,
        connector="servicedeskplus",
        resource_type="request_filter",
    ),
    "servicedesk_list_requests": ToolDefinition(
        spec=ToolSpec(
            name="servicedesk_list_requests",
            description=(
                "Lists ServiceDesk Plus requests using a named request filter. "
                "This is a read-only connector tool. If no filter is provided, "
                "uses the configured default request filter."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "filter_name": {
                        "type": "string",
                        "description": (
                            "Named ServiceDesk request filter/view to use. "
                            "If omitted, the configured default request filter is used."
                        ),
                        "default": "Open_System",
                    },
                    "row_count": {
                        "type": "integer",
                        "description": "Number of requests to return. Maximum 50.",
                        "default": 10,
                    },
                    "start_index": {
                        "type": "integer",
                        "description": "1-based start index for paging.",
                        "default": 1,
                    },
                    "sort_field": {
                        "type": "string",
                        "description": "Field to sort by.",
                        "default": "created_time",
                    },
                    "sort_order": {
                        "type": "string",
                        "description": "Sort order: asc or desc.",
                        "default": "desc",
                    },
                },
                "required": [],
            },
        ),
        handler=servicedesk_list_requests,
        category=ToolCategory.CONNECTOR_READ,
        connector="servicedeskplus",
        resource_type="request",
    ),
    "servicedesk_get_request": ToolDefinition(
        spec=ToolSpec(
            name="servicedesk_get_request",
            description=(
                "Gets detailed information for a single ServiceDesk Plus request by ID. "
                "This is a read-only connector tool."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "request_id": {
                        "type": "string",
                        "description": "ServiceDesk Plus request ID.",
                    },
                },
                "required": ["request_id"],
            },
        ),
        handler=servicedesk_get_request,
        category=ToolCategory.CONNECTOR_READ,
        connector="servicedeskplus",
        resource_type="request",
    ),
    "servicedesk_get_request_notes": ToolDefinition(
        spec=ToolSpec(
            name="servicedesk_get_request_notes",
            description=(
                "Gets notes for a ServiceDesk Plus request. "
                "This is a read-only connector tool."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "request_id": {
                        "type": "string",
                        "description": "ServiceDesk Plus request ID.",
                    },
                    "row_count": {
                        "type": "integer",
                        "description": "Number of notes to return. Maximum 50.",
                        "default": 20,
                    },
                    "start_index": {
                        "type": "integer",
                        "description": "1-based start index for paging.",
                        "default": 1,
                    },
                    "sort_order": {
                        "type": "string",
                        "description": "Sort order: asc or desc.",
                        "default": "desc",
                    },
                },
                "required": ["request_id"],
            },
        ),
        handler=servicedesk_get_request_notes,
        category=ToolCategory.CONNECTOR_READ,
        connector="servicedeskplus",
        resource_type="request_note",
    ),
    "servicedesk_get_request_attachments": ToolDefinition(
        spec=ToolSpec(
            name="servicedesk_get_request_attachments",
            description=(
                "Gets attachment metadata for a ServiceDesk Plus request, such as filename, "
                "size, and content type. This does not download or inspect attachment contents."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "request_id": {
                        "type": "string",
                        "description": "ServiceDesk Plus request ID.",
                    },
                },
                "required": ["request_id"],
            },
        ),
        handler=servicedesk_get_request_attachments,
        category=ToolCategory.CONNECTOR_READ,
        connector="servicedeskplus",
        resource_type="request_attachment",
    ),
}


def get_tool_definitions() -> dict[str, ToolDefinition]:
    return TOOL_DEFINITIONS


def get_tool_definition(name: str) -> ToolDefinition:
    return TOOL_DEFINITIONS[name]


def get_tool_specs() -> list[ToolSpec]:
    return [definition.spec for definition in TOOL_DEFINITIONS.values()]
