from difflib import SequenceMatcher
from itertools import zip_longest

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

from previews import is_unified_diff_preview, parse_unified_diff, summarize_diff

console = Console(color_system="truecolor")

GUTTER_STYLE = "bright_black"
HUNK_STYLE = "bright_black"
CONTEXT_STYLE = "dim"

REMOVED_LINE_STYLE = "white on #370000"
ADDED_LINE_STYLE = "white on #003700"

REMOVED_HIGHLIGHT_STYLE = "bold white on #7c0000"
ADDED_HIGHLIGHT_STYLE = "bold white on #007c00"


def _tool_display_name(function_name: str) -> str:
    names = {
        "write_file": "Write",
        "update": "Update",
        "bash": "Bash",
        "git_status": "Git Status",
        "git_diff": "Git Diff",
        "git_diff_file": "Git Diff File",
        "get_file_content": "Get File Content",
        "get_files_info": "Get Files Info",
        "run_tests": "Run Tests",
        "run_python_file": "Run Python File",
        "find_file": "Find File",
        "search_in_files": "Search In Files",
    }
    return names.get(function_name, function_name.replace("_", " ").title())


def _tool_summary_verb(function_name: str) -> str:
    verbs = {
        "write_file": "Updated",
        "update": "Updated",
    }
    return verbs.get(function_name, "Changed")


def build_preview_summary(function_name: str, file_path: str, preview: str) -> str:
    if preview.startswith("No content changes"):
        return preview

    if preview.startswith("Preview unavailable"):
        return preview

    additions, removals = summarize_diff(preview)
    verb = _tool_summary_verb(function_name)
    return (
        f"{verb} {file_path} with "
        f"{additions} addition{'s' if additions != 1 else ''} and "
        f"{removals} removal{'s' if removals != 1 else ''}"
    )


def approval_prompt(function_name: str, args: dict) -> tuple[str, str | None]:
    console.print()
    console.print("Permission required", style="bold yellow")
    console.print(f"[bold]Tool:[/bold] [cyan]{_tool_display_name(function_name)}[/cyan]")

    if function_name in {"write_file", "update"}:
        console.print(f"[bold]Path:[/bold] {args.get('file_path', '')}")

    elif function_name == "bash":
        command = args.get("command", "")
        cwd = args.get("cwd") or "."
        timeout = args.get("timeout_seconds")
        timeout_display = timeout if timeout is not None else 30

        console.print(f"[bold]Command:[/bold] {command}", highlight=False)
        console.print(f"[bold]Cwd:[/bold] {cwd}", highlight=False)
        console.print(f"[bold]Timeout:[/bold] {timeout_display}s", highlight=False)

    else:
        console.print(f"[bold]Args:[/bold] {args}", highlight=False)

    options = Text()
    options.append("[y]", style="green")
    options.append(" allow once   ")
    options.append("[n]", style="red")
    options.append(" deny   ")
    options.append("[f]", style="magenta")
    options.append(" deny with feedback   ")
    options.append("[s]", style="cyan")
    options.append(" allow tool for session   ")
    options.append("[p]", style="yellow")
    options.append(" allow path for session")
    console.print(options)

    answer = console.input("> ").strip().lower()

    if answer == "f":
        feedback = console.input("Reason: ").strip()
        return "f", feedback or "No reason provided."

    return answer, None


def print_mutation_preview(function_name: str, file_path: str, preview: str) -> None:
    title = f"{_tool_display_name(function_name)}({file_path})"
    tree = Tree(Text(f"● {title}", style="bold green"), guide_style="bright_black")

    if is_unified_diff_preview(preview):
        summary = build_preview_summary(function_name, file_path, preview)
        tree.add(Text(summary, style="dim"))
        console.print(tree)
        console.print(
            Panel(
                render_rich_diff(preview),
                border_style="bright_black",
                padding=(0, 1),
            )
        )
    else:
        tree.add(Text("Preview", style="dim"))
        console.print(tree)
        console.print(
            Panel(
                preview[:4000],
                border_style="bright_black",
                padding=(0, 1),
            )
        )


def format_tool_call(function_call, verbose: bool) -> Text:
    display_name = _tool_display_name(function_call.name or "")
    text = Text("• ", style="bright_black")
    text.append("[tool] ", style="bold cyan")
    text.append(display_name, style="bold white")
    if verbose and function_call.args:
        text.append(f" {dict(function_call.args)}", style="bright_black")
    return text


def print_agent_update(text: str) -> None:
    console.print(Text(f"• {text}", style="white"))


def print_final_response(text: str) -> None:
    console.print()
    console.print(text, highlight=False)
    console.print()


def print_verbose_stats(user_prompt: str, response) -> None:
    console.print(f"User prompt: {user_prompt}", style="dim")
    console.print(
        f"Prompt tokens: {response.usage_metadata.prompt_token_count}",
        style="dim",
    )
    console.print(
        f"Response tokens: {response.usage_metadata.candidates_token_count}",
        style="dim",
    )


def print_error(text: str) -> None:
    console.print(text, style="bold red")


def _render_context_line(line) -> Text:
    text = Text()
    text.append(f"{'' if line.old_lineno is None else line.old_lineno:>4} ", style=GUTTER_STYLE)
    text.append(f"{'' if line.new_lineno is None else line.new_lineno:>4} ", style=GUTTER_STYLE)
    text.append("  ", style=CONTEXT_STYLE)
    text.append(line.text, style=CONTEXT_STYLE)
    return text


def _render_hunk_line(line) -> Text:
    return Text(line.text, style=HUNK_STYLE)


def _render_styled_diff_line(
    old_lineno: int | None,
    new_lineno: int | None,
    marker: str,
    content: Text,
) -> Text:
    text = Text()
    text.append(
        f"{'' if old_lineno is None else old_lineno:>4} ",
        style=GUTTER_STYLE,
    )
    text.append(
        f"{'' if new_lineno is None else new_lineno:>4} ",
        style=GUTTER_STYLE,
    )

    if marker == "-":
        marker_style = REMOVED_LINE_STYLE
    elif marker == "+":
        marker_style = ADDED_LINE_STYLE
    else:
        marker_style = CONTEXT_STYLE

    if marker in {"-", "+"}:
        text.append(f"{marker} ", style=marker_style)
    else:
        text.append("  ", style=marker_style)

    text.append_text(content)
    return text


def _plain_removed_text(text: str) -> Text:
    return Text(text, style=REMOVED_LINE_STYLE)


def _plain_added_text(text: str) -> Text:
    return Text(text, style=ADDED_LINE_STYLE)


def _highlight_changed_spans(old_text: str, new_text: str) -> tuple[Text, Text]:
    matcher = SequenceMatcher(None, old_text, new_text)

    old_rendered = Text()
    new_rendered = Text()

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old_chunk = old_text[i1:i2]
        new_chunk = new_text[j1:j2]

        if tag == "equal":
            if old_chunk:
                old_rendered.append(old_chunk, style=REMOVED_LINE_STYLE)
            if new_chunk:
                new_rendered.append(new_chunk, style=ADDED_LINE_STYLE)
        else:
            if old_chunk:
                old_rendered.append(old_chunk, style=REMOVED_HIGHLIGHT_STYLE)
            if new_chunk:
                new_rendered.append(new_chunk, style=ADDED_HIGHLIGHT_STYLE)

    return old_rendered, new_rendered


def _render_change_block(block_lines: list) -> list[Text]:
    renderables = []
    removes = []
    adds = []
    phase = "remove"

    for line in block_lines:
        if line.kind == "remove" and phase == "remove":
            removes.append(line)
        elif line.kind == "add":
            phase = "add"
            adds.append(line)

    for old_line, new_line in zip_longest(removes, adds):
        if old_line and new_line:
            old_text, new_text = _highlight_changed_spans(old_line.text, new_line.text)
            renderables.append(_render_styled_diff_line(old_line.old_lineno, None, "-", old_text))
            renderables.append(_render_styled_diff_line(None, new_line.new_lineno, "+", new_text))
        elif old_line:
            renderables.append(
                _render_styled_diff_line(
                    old_line.old_lineno,
                    None,
                    "-",
                    _plain_removed_text(old_line.text),
                )
            )
        elif new_line:
            renderables.append(
                _render_styled_diff_line(
                    None,
                    new_line.new_lineno,
                    "+",
                    _plain_added_text(new_line.text),
                )
            )

    return renderables


def render_rich_diff(preview: str):
    parsed = parse_unified_diff(preview)
    lines = parsed.lines
    i = 0
    renderables = []

    while i < len(lines):
        line = lines[i]

        if line.kind == "meta":
            i += 1
            continue

        if line.kind == "hunk":
            renderables.append(_render_hunk_line(line))
            i += 1
            continue

        if line.kind == "context":
            renderables.append(_render_context_line(line))
            i += 1
            continue

        if line.kind in {"remove", "add"}:
            block = []
            while i < len(lines) and lines[i].kind in {"remove", "add"}:
                block.append(lines[i])
                i += 1
            renderables.extend(_render_change_block(block))
            continue

        i += 1

    return Group(*renderables)
