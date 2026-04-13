import difflib
import os
import re
import shutil
import textwrap

RESET = "\033[0m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
CYAN = "\033[36m"
BOLD = "\033[1m"

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


# Write diff engine
def normalize_tool_path(working_directory: str, file_path: str) -> tuple[str, str]:
    workspace = os.path.abspath(working_directory)
    target = os.path.normpath(os.path.join(workspace, file_path))
    return workspace, target


def build_write_preview(working_directory: str, file_path: str, new_content: str) -> str:
    workspace, target = normalize_tool_path(working_directory, file_path)

    if os.path.commonpath([workspace, target]) != workspace:
        return f'Preview unavailable: "{file_path}" is outside the workspace.'

    if os.path.isdir(target):
        return f'Preview unavailable: "{file_path}" is a directory.'

    if not os.path.exists(target):
        added = "\n".join(f"+ {line}" for line in new_content.splitlines())
        return f'New file: "{file_path}"\n' + (added or "+ <empty file>")

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
    return preview if preview.strip() else f'No content changes for "{file_path}".'


# Formatting engine
def format_diff_for_terminal(diff_text: str) -> str:
    width = shutil.get_terminal_size((100, 20)).columns
    out = []
    old_ln = None
    new_ln = None

    for raw in diff_text.splitlines():
        if raw.startswith("--- ") or raw.startswith("+++ "):
            out.append(f"{DIM}{CYAN}{raw}{RESET}")
            continue

        m = HUNK_RE.match(raw)
        if m:
            old_start, old_len, new_start, new_len = m.groups()
            old_ln = int(old_start)
            new_ln = int(new_start)
            old_len = int(old_len or 1)
            new_len = int(new_len or 1)
            out.append(
                f"{DIM}Lines: old {old_start}"
                f"{'' if old_len == 1 else f'-{old_ln + old_len - 1}'}"
                f" → new {new_start}"
                f"{'' if new_len == 1 else f'-{new_ln + new_len - 1}'}{RESET}"
            )
            continue

        prefix = raw[:1] if raw else " "
        content = raw[1:] if raw else ""

        if prefix == "-":
            left = f"old {old_ln:>4}"
            color = RED
            marker = "-"
            old_ln += 1
        elif prefix == "+":
            left = f"new {new_ln:>4}"
            color = GREEN
            marker = "+"
            new_ln += 1
        else:
            left = " " * 8
            color = DIM
            marker = " "
            if old_ln is not None:
                old_ln += 1
            if new_ln is not None:
                new_ln += 1

        wrapped = textwrap.wrap(
            content,
            width=max(20, width - 14),
            replace_whitespace=False,
            drop_whitespace=False,
        ) or [""]

        for i, part in enumerate(wrapped):
            gutter = left if i == 0 else " " * len(left)
            sign = marker if i == 0 else " "
            out.append(f"{color}{gutter}  {sign} {part}{RESET}")

    return "\n".join(out)


def is_unified_diff_preview(preview: str) -> bool:
    lines = preview.splitlines()
    return len(lines) >= 2 and lines[0].startswith("--- ") and lines[1].startswith("+++ ")
