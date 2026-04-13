from previews import format_diff_for_terminal, is_unified_diff_preview


# Approval UI
def approval_prompt(function_name: str, args: dict) -> str:
    print("\nPermission required")
    print(f"Tool: {function_name}")

    if function_name == "write_file":
        print(f"Path: {args.get('file_path', '<unknown>')}")
    else:
        print(f"Args: {args}")

    print("[y] allow once   [n] deny   [s] allow tool for session   [p] allow path for session")
    return input("> ").strip().lower()


# ---


def print_write_preview(preview: str) -> None:
    print("\nProposed change preview")
    print("─" * 40)

    if is_unified_diff_preview(preview):
        print(format_diff_for_terminal(preview[:4000]))
    else:
        print(preview[:4000])

    print("─" * 40)
