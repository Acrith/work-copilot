from agent_types import ToolCall, ToolResult
from approval import ApprovalAction
from console_ui import approval_prompt, print_mutation_preview
from functions.update_file import plan_update
from permissions import (
    Decision,
    PermissionContext,
    evaluate_request,
    extract_target_path,
)
from previews import build_update_preview, build_write_preview
from tool_registry import get_tool_definition


def execute_tool_call(
    tool_call: ToolCall,
    working_directory: str,
    permission_context: PermissionContext,
    verbose: bool = False,
) -> ToolResult:
    function_name = tool_call.name
    args = dict(tool_call.args or {})

    try:
        tool_definition = get_tool_definition(function_name)
    except KeyError:
        return ToolResult(
            name=function_name,
            payload={"error": f"Unknown function: {function_name}"},
            call_id=tool_call.call_id,
        )

    decision = evaluate_request(permission_context, function_name, args)

    if function_name == "update":
        update_plan = plan_update(
            working_directory,
            args.get("file_path", ""),
            args.get("old_text", ""),
            args.get("new_text", ""),
        )

        # If update cannot be applied anyway, don't ask for approval.
        # Let the tool return the useful validation error.
        if update_plan["status"] != "ready":
            decision = Decision.ALLOW

    if decision == Decision.DENY:
        return ToolResult(
            name=function_name,
            payload={
                "error": (
                    f"Permission denied for {function_name} in mode={permission_context.mode.value}"
                )
            },
            call_id=tool_call.call_id,
        )

    if decision == Decision.ASK:
        if function_name == "write_file":
            preview = build_write_preview(
                working_directory,
                args.get("file_path", ""),
                args.get("content", ""),
            )
            print_mutation_preview(function_name, args.get("file_path", ""), preview)

        elif function_name == "update":
            preview = build_update_preview(
                working_directory,
                args.get("file_path", ""),
                args.get("old_text", ""),
                args.get("new_text", ""),
            )
            print_mutation_preview(function_name, args.get("file_path", ""), preview)

        approval = approval_prompt(function_name, args)

        if approval.action == ApprovalAction.DENY:
            return ToolResult(
                name=function_name,
                payload={
                    "error": f"User denied {function_name}",
                    "denied_by_user": True,
                },
                call_id=tool_call.call_id,
            )

        if approval.action == ApprovalAction.DENY_WITH_FEEDBACK:
            payload = {
                "error": f"User denied {function_name}",
                "denied_by_user": True,
            }

            if approval.feedback:
                payload["feedback"] = approval.feedback

            return ToolResult(
                name=function_name,
                payload=payload,
                call_id=tool_call.call_id,
            )

        if approval.action == ApprovalAction.ALLOW_TOOL_SESSION:
            permission_context.session_allow_tools.add(function_name)

        elif approval.action == ApprovalAction.ALLOW_PATH_SESSION:
            target_path = extract_target_path(function_name, args)
            if target_path:
                permission_context.session_allow_paths.add(target_path)

    call_args = dict(args)
    call_args["working_directory"] = working_directory

    try:
        result = tool_definition.handler(**call_args)
    except TypeError as e:
        return ToolResult(
            name=function_name,
            payload={"error": f"Invalid arguments for {function_name}: {e}"},
            call_id=tool_call.call_id,
        )
    except Exception as e:
        return ToolResult(
            name=function_name,
            payload={"error": f"Tool {function_name} failed: {e}"},
            call_id=tool_call.call_id,
        )

    return ToolResult(
        name=function_name,
        payload={"result": result},
        call_id=tool_call.call_id,
    )
