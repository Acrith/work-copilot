# textual_diff_renderer.py

from dataclasses import dataclass

from rich.text import Text
from textual.widgets import RichLog

from textual_preview import (
    format_diff_column_header,
    format_diff_file_header,
    format_diff_rows,
    parse_unified_diff,
    summarize_diff_rows,
)


@dataclass(frozen=True)
class DiffRenderRow:
    content: Text | str
    css_class: str = "context"


def _classify_rendered_row(row: Text | str) -> str:
    row_text = str(row)

    if not row_text:
        return "empty"

    if row_text == str(format_diff_column_header()):
        return "column-header"

    if row_text.startswith("change "):
        return "hunk"

    if "│ + │" in row_text or "| + |" in row_text:
        return "added"

    if "│ - │" in row_text or "| - |" in row_text:
        return "removed"

    return "context"


def build_approval_preview_rows(
    *,
    preview: str | None,
    preview_path: str | None,
) -> list[DiffRenderRow]:
    rows: list[DiffRenderRow] = [
        DiffRenderRow(
            Text.from_markup("[bold #88c0d0]Preview[/]"),
            css_class="title",
        ),
        DiffRenderRow("", css_class="empty"),
    ]

    if not preview:
        rows.append(
            DiffRenderRow(
                Text.from_markup("[#7f8ea3]No preview available.[/]"),
                css_class="muted",
            )
        )
        return rows

    parsed_rows = parse_unified_diff(preview)
    summary = summarize_diff_rows(parsed_rows)
    path = preview_path or "preview"

    rows.append(
        DiffRenderRow(
            format_diff_file_header(path, summary),
            css_class="file-header",
        )
    )
    rows.append(
        DiffRenderRow(
            Text("─" * 60, style="#30363d"),
            css_class="separator",
        )
    )

    for row in format_diff_rows(parsed_rows):
        rows.append(
            DiffRenderRow(
                row,
                css_class=_classify_rendered_row(row),
            )
        )

    return rows


def render_approval_preview(
    *,
    preview_log: RichLog,
    preview: str | None,
    preview_path: str | None,
) -> None:
    for row in build_approval_preview_rows(
        preview=preview,
        preview_path=preview_path,
    ):
        preview_log.write(row.content)