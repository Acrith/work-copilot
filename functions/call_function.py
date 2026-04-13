from google.genai import types

from console_ui import approval_prompt, print_write_preview
from functions.find_file import find_file, schema_find_file
from functions.get_file_content import get_file_content, schema_get_file_content
from functions.get_files_info import get_files_info, schema_get_files_info
from functions.run_python_file import run_python_file, schema_run_python_file
from functions.run_tests import run_tests, schema_run_tests
from functions.search_in_files import schema_search_in_files, search_in_files
from functions.update_file import plan_update, schema_update_file, update_file
from functions.write_file import schema_write_file, write_file
from permissions import Decision, evaluate_request, extract_target_path
from previews import build_update_preview, build_write_preview

available_functions = types.Tool(
    function_declarations=[
        schema_get_files_info,
        schema_get_file_content,
        schema_write_file,
        schema_run_python_file,
        schema_search_in_files,
        schema_run_tests,
        schema_update_file,
        schema_find_file,
    ],
)


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


def call_function(function_call, working_directory, permission_context, verbose=False):

    # Function map for tool calling and error handling
    function_map = {
        "get_file_content": get_file_content,
        "get_files_info": get_files_info,
        "write_file": write_file,
        "run_python_file": run_python_file,
        "search_in_files": search_in_files,
        "run_tests": run_tests,
        "update": update_file,
        "find_file": find_file,
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
    # ---

    # Arg handling and function calling
    args = dict(function_call.args) if function_call.args else {}
    decision = evaluate_request(permission_context, function_name, args)

    if function_name == "update":
        update_plan = plan_update(
            working_directory,
            args.get("file_path", ""),
            args.get("old_text", ""),
            args.get("new_text", ""),
        )
        if update_plan["status"] != "ready":
            decision = Decision.ALLOW

    if decision == Decision.DENY:
        return make_tool_response(
            function_name,
            {
                "error": f"Permission denied for {function_name} in mode={permission_context.mode.value}"
            },
        )

    if decision == Decision.ASK:
        if function_name == "write_file":
            preview = build_write_preview(
                working_directory,
                args.get("file_path", ""),
                args.get("content", ""),
            )
            print_write_preview(preview)
        
        elif function_name == "update":
            preview = build_update_preview(
                working_directory,
                args.get("file_path", ""),
                args.get("old_text", ""),
                args.get("new_text", ""),
            )
            print_write_preview(preview)

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
