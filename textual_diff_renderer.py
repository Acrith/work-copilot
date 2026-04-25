# textual_diff_renderer.py

from rich.text import Text
from textual.widgets import RichLog

from textual_preview import (
    format_diff_file_header,
    format_diff_rows,
    parse_unified_diff,
    summarize_diff_rows,
)


def render_approval_preview(
    *,
    preview_log: RichLog,
    preview: str | None,
    preview_path: str | None,
) -> None:
    preview_log.write(Text.from_markup("[bold #88c0d0]Preview[/]"))
    preview_log.write("")

    if not preview:
        preview_log.write(Text.from_markup("[#7f8ea3]No preview available.[/]"))
        return

    rows = parse_unified_diff(preview)
    summary = summarize_diff_rows(rows)
    path = preview_path or "preview"

    preview_log.write(format_diff_file_header(path, summary))
    preview_log.write(Text("─" * 60, style="#30363d"))

    for row in format_diff_rows(rows):
        preview_log.write(row)