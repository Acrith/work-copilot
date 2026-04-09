import os
import difflib

from google.genai import types

from functions.get_files_info import schema_get_files_info, get_files_info
from functions.get_file_content import schema_get_file_content, get_file_content
from functions.write_file import schema_write_file, write_file
from functions.run_python_file import schema_run_python_file, run_python_file
from functions.search_in_files import schema_search_in_files, search_in_files

from permissions import Decision, evaluate_request, extract_target_path

available_functions = types.Tool(
    function_declarations=[
        schema_get_files_info,
        schema_get_file_content,
        schema_write_file,
        schema_run_python_file,
        schema_search_in_files,
    ],
)

# Approval engine
def approval_prompt(function_name: str, args: dict) -> str:
    print("\nPermission required")
    print(f"Tool: {function_name}")
    print(f"Args: {args}")
    print("[y] allow once   [n] deny   [s] allow tool for session   [p] allow path for session")
    return input("> ").strip().lower()

def make_tool_response(name: str, payload: dict):
    return types.Content(
        role="tool",
        parts=[
            types.Part.from_function_response(
                name=name,
                response=payload,
            )
        ],
    )
#---

# Write diff engine
def normalize_tool_path(working_directory: str, file_path: str) -> tuple[str, str]:
    workspace = os.path.abspath(working_directory)
    target = os.path.normpath(os.path.join(workspace, file_path))
    return workspace, target

def build_write_preview(working_directory: str, file_path: str, new_content: str) -> str:
    workspace, target = normalize_tool_path(working_directory, file_path)

    if os.path.commonpath([workspace, target]) != workspace:    
        return f"Preview unavailable: \"{file_path}\" is outside the workspace."
    
    if not os.path.exists(target):
        added = "\n".join(f"+ {line}" for line in new_content.splitlines())
        return f"Preview unavailable: \"{file_path}\" is a directory."
    
    try:
        with open(target, "r", encoding="utf-8") as f:
            old_content = f.read()
    except Exception as e:
        return f"Could not read existing file for preview: {e}"
    
    diff = difflib.unified_diff(
        old_content.splitlines(),
        new_content.splitlines(),
        fromfile=f"{file_path} (current)",
        tofile=f"{file_path} (proposed)",
        lineterm="",
    )
    preview = "\n".join(diff)
    return preview if preview.strip() else f"No content changes for \"{file_path}\"."
#---

def call_function(function_call, working_directory, permission_context, verbose=False):
    if verbose:
        print(f"[tool] {function_call.name}({function_call.args})")
    else:
        print(f"[tool] {function_call.name}")

    # Function map for tool calling and error handling
    function_map = {
        "get_file_content": get_file_content,
        "get_files_info": get_files_info,
        "write_file": write_file,
        "run_python_file": run_python_file,
        "search_in_files": search_in_files
    }

    function_name = function_call.name or ""
    if function_name not in function_map:
        return types.Content(
            role="tool",
            parts=[
                types.Part.from_function_response(
                    name=function_name,
                    response={"error": f"Unknown function: {function_name}"},
                )
            ],
        )
    #---
    
    # Arg handling and function calling
    args = dict(function_call.args) if function_call.args else {}
    decision = evaluate_request(permission_context, function_name, args)

    if decision == Decision.DENY:
        return make_tool_response(
            function_name,
            {"error": f"Permission denied for {function_name} in mode={permission_context.mode.value}"},
        )

    if decision == Decision.ASK and function_name == "write_file":
        preview = build_write_preview(
            working_directory,
            args.get("file_path", ""),
            args.get("content", ""),
        )
        print("\nProposed change preview")
        print("─" * 40)
        print(preview[:4000])
        print("─" * 40)

    if decision == Decision.ASK:
        answer = approval_prompt(function_name, args)
        if answer == "n":
            return make_tool_response(
                function_name,
                {"error": f"User denied {function_name}"},
            )
        if answer == "s":
            permission_context.session_allow_tools.add(function_name)
        elif answer == "p":
            target_path = extract_target_path(function_name, args)
            if target_path:
                permission_context.session_allow_paths.add(target_path)
        elif answer != "y":
            return make_tool_response(
                function_name,
                {"error": f"Unrecognized approval response. Denied {function_name}"},
            )

    args["working_directory"] = working_directory
    function_result = function_map[function_name](**args)

    return make_tool_response(
        function_name,
        {"result": function_result},
    )

