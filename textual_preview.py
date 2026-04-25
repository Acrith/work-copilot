# textual_preview.py

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import zip_longest
from typing import Literal

from rich.text import Text

DiffLineKind = Literal[
    "file_header",
    "hunk",
    "added",
    "removed",
    "context",
    "metadata",
]

HEADER_TRIGGER_KINDS = {"hunk", "added", "removed", "context"}
DIFF_COLUMN_SEPARATOR = "│"

STYLE_DIFF_HEADER = "bold #8b949e"
STYLE_FILE_HEADER = "bold #c9d1d9"
STYLE_METADATA = "bold #f2cc60"
STYLE_HUNK = "bold #79c0ff"

# Full row backgrounds are owned by textual_diff_view.py CSS.
# These styles should stay foreground-only.
STYLE_ADDED_ROW = "#d7ffe0"
STYLE_REMOVED_ROW = "#ffd7d7"
STYLE_CONTEXT_ROW = "#c9d1d9"

STYLE_ADDED_MARKER = "bold #7ee787"
STYLE_REMOVED_MARKER = "bold #ff7b72"

STYLE_ADDED_HIGHLIGHT = "bold #ffffff on #245c38"
STYLE_REMOVED_HIGHLIGHT = "bold #ffffff on #7a3030"

STYLE_MUTED = "#8b949e"

HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


@dataclass(frozen=True)
class DiffLine:
    kind: DiffLineKind
    text: str
    old_line_no: int | None = None
    new_line_no: int | None = None


@dataclass(frozen=True)
class DiffSummary:
    additions: int
    removals: int


def parse_hunk_header(line: str) -> tuple[int, int] | None:
    match = HUNK_HEADER_RE.match(line)

    if match is None:
        return None

    return int(match.group("old_start")), int(match.group("new_start"))


def parse_unified_diff(preview: str) -> list[DiffLine]:
    rows: list[DiffLine] = []
    old_line_no: int | None = None
    new_line_no: int | None = None

    for line in preview.splitlines():
        hunk_start = parse_hunk_header(line)

        if hunk_start is not None:
            old_line_no, new_line_no = hunk_start
            rows.append(DiffLine(kind="hunk", text=line))
            continue

        if line.startswith("---") or line.startswith("+++"):
            rows.append(DiffLine(kind="file_header", text=line))
            continue

        if line.startswith("New file:"):
            old_line_no = None
            new_line_no = 1
            rows.append(DiffLine(kind="metadata", text=line))
            continue

        if line.startswith("Updated file:"):
            rows.append(DiffLine(kind="metadata", text=line))
            continue

        if line.startswith("Deleted file:"):
            rows.append(DiffLine(kind="metadata", text=line))
            continue

        if line.startswith("+"):
            rows.append(
                DiffLine(
                    kind="added",
                    text=line,
                    old_line_no=None,
                    new_line_no=new_line_no,
                )
            )
            if new_line_no is not None:
                new_line_no += 1
            continue

        if line.startswith("-"):
            rows.append(
                DiffLine(
                    kind="removed",
                    text=line,
                    old_line_no=old_line_no,
                    new_line_no=None,
                )
            )
            if old_line_no is not None:
                old_line_no += 1
            continue

        rows.append(
            DiffLine(
                kind="context",
                text=line,
                old_line_no=old_line_no,
                new_line_no=new_line_no,
            )
        )

        if old_line_no is not None:
            old_line_no += 1
        if new_line_no is not None:
            new_line_no += 1

    return rows


def summarize_diff_rows(rows: list[DiffLine]) -> DiffSummary:
    additions = sum(1 for row in rows if row.kind == "added")
    removals = sum(1 for row in rows if row.kind == "removed")

    return DiffSummary(additions=additions, removals=removals)


def format_preview_line(line: str) -> Text | str:
    if line.startswith("@@"):
        return Text(line, style=STYLE_HUNK)

    if line.startswith("+") and not line.startswith("+++"):
        return Text(line, style=STYLE_ADDED_MARKER)

    if line.startswith("-") and not line.startswith("---"):
        return Text(line, style=STYLE_REMOVED_MARKER)

    if line.startswith("New file:") or line.startswith("Updated file:"):
        return Text(line, style=STYLE_METADATA)

    if line.startswith("Deleted file:"):
        return Text(line, style=STYLE_REMOVED_MARKER)

    if line.startswith("+++") or line.startswith("---"):
        return Text(line, style=STYLE_MUTED)

    return line


def format_hunk_label(text: str) -> str:
    cleaned = text.replace("@@", "").strip()
    parts = cleaned.split(maxsplit=2)

    if len(parts) >= 2:
        return f"change {parts[0]} → {parts[1]}"

    return f"change {cleaned}"


def format_line_number(value: int | None) -> str:
    if value is None:
        return "    "

    return f"{value:>4}"


def strip_diff_marker(text: str) -> str:
    if text.startswith(("+", "-")):
        return text[1:].lstrip()

    return text.lstrip()


def plain_added_text(text: str) -> Text:
    return Text(strip_diff_marker(text), style=STYLE_ADDED_ROW)


def plain_removed_text(text: str) -> Text:
    return Text(strip_diff_marker(text), style=STYLE_REMOVED_ROW)


def plain_context_text(text: str) -> Text:
    return Text(strip_diff_marker(text), style=STYLE_CONTEXT_ROW)


def format_diff_column_header() -> Text:
    return Text(
        f"{'old':>4} {'new':>4} "
        f"{DIFF_COLUMN_SEPARATOR} Δ {DIFF_COLUMN_SEPARATOR} content",
        style=STYLE_DIFF_HEADER,
    )


def format_diff_file_header(path: str, summary: DiffSummary) -> Text:
    text = Text()
    text.append("▸ ", style=STYLE_MUTED)
    text.append(path, style=STYLE_FILE_HEADER)
    text.append(" ")
    text.append(f"(+{summary.additions}", style=STYLE_ADDED_MARKER)
    text.append(", ")
    text.append(f"-{summary.removals})", style=STYLE_REMOVED_MARKER)
    return text


def build_diff_row_prefix(
    *,
    old_line_no: int | None,
    new_line_no: int | None,
    marker: str,
    row_style: str,
    marker_style: str,
) -> Text:
    old_no = format_line_number(old_line_no)
    new_no = format_line_number(new_line_no)

    text = Text()
    text.append(f"{old_no} {new_no} {DIFF_COLUMN_SEPARATOR} ", style=row_style)
    text.append(marker, style=marker_style)
    text.append(f" {DIFF_COLUMN_SEPARATOR} ", style=row_style)
    return text


def render_diff_row_with_content(
    *,
    row: DiffLine,
    marker: str,
    content: Text,
    row_style: str,
    marker_style: str,
) -> Text:
    text = build_diff_row_prefix(
        old_line_no=row.old_line_no,
        new_line_no=row.new_line_no,
        marker=marker,
        row_style=row_style,
        marker_style=marker_style,
    )
    text.append_text(content)
    return text


def format_diff_row(row: DiffLine) -> Text | str:
    if row.kind == "metadata":
        return Text(row.text, style=STYLE_METADATA)

    if row.kind == "file_header":
        return Text(row.text, style=STYLE_MUTED)

    if row.kind == "hunk":
        return Text(format_hunk_label(row.text), style=STYLE_HUNK)

    if row.kind == "added":
        return render_diff_row_with_content(
            row=row,
            marker="+",
            content=plain_added_text(row.text),
            row_style=STYLE_ADDED_ROW,
            marker_style=STYLE_ADDED_MARKER,
        )

    if row.kind == "removed":
        return render_diff_row_with_content(
            row=row,
            marker="-",
            content=plain_removed_text(row.text),
            row_style=STYLE_REMOVED_ROW,
            marker_style=STYLE_REMOVED_MARKER,
        )

    if row.kind == "context":
        return render_diff_row_with_content(
            row=row,
            marker=" ",
            content=plain_context_text(row.text),
            row_style=STYLE_CONTEXT_ROW,
            marker_style=STYLE_CONTEXT_ROW,
        )

    return row.text


def highlight_changed_spans(old_text: str, new_text: str) -> tuple[Text, Text]:
    old_text = strip_diff_marker(old_text)
    new_text = strip_diff_marker(new_text)

    matcher = SequenceMatcher(None, old_text, new_text)

    old_rendered = Text()
    new_rendered = Text()

    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        old_chunk = old_text[old_start:old_end]
        new_chunk = new_text[new_start:new_end]

        if tag == "equal":
            if old_chunk:
                old_rendered.append(old_chunk, style=STYLE_REMOVED_ROW)
            if new_chunk:
                new_rendered.append(new_chunk, style=STYLE_ADDED_ROW)
        else:
            if old_chunk:
                old_rendered.append(old_chunk, style=STYLE_REMOVED_HIGHLIGHT)
            if new_chunk:
                new_rendered.append(new_chunk, style=STYLE_ADDED_HIGHLIGHT)

    return old_rendered, new_rendered


def format_change_block(rows: list[DiffLine]) -> list[Text]:
    rendered: list[Text] = []
    removed_rows: list[DiffLine] = []
    added_rows: list[DiffLine] = []
    phase = "removed"

    for row in rows:
        if row.kind == "removed" and phase == "removed":
            removed_rows.append(row)
            continue

        if row.kind == "added":
            phase = "added"
            added_rows.append(row)
            continue

        if row.kind == "removed":
            removed_rows.append(row)

    for removed_row, added_row in zip_longest(removed_rows, added_rows):
        if removed_row is not None and added_row is not None:
            old_text, new_text = highlight_changed_spans(
                removed_row.text,
                added_row.text,
            )
            rendered.append(
                render_diff_row_with_content(
                    row=removed_row,
                    marker="-",
                    content=old_text,
                    row_style=STYLE_REMOVED_ROW,
                    marker_style=STYLE_REMOVED_MARKER,
                )
            )
            rendered.append(
                render_diff_row_with_content(
                    row=added_row,
                    marker="+",
                    content=new_text,
                    row_style=STYLE_ADDED_ROW,
                    marker_style=STYLE_ADDED_MARKER,
                )
            )
        elif removed_row is not None:
            rendered.append(format_diff_row(removed_row))
        elif added_row is not None:
            rendered.append(format_diff_row(added_row))

    return rendered


def format_diff_rows(rows: list[DiffLine]) -> list[Text | str]:
    rendered: list[Text | str] = []
    wrote_column_header = False
    index = 0

    while index < len(rows):
        row = rows[index]

        if row.kind in {"metadata", "file_header"}:
            index += 1
            continue

        if row.kind in HEADER_TRIGGER_KINDS and not wrote_column_header:
            rendered.append(format_diff_column_header())
            wrote_column_header = True

        if row.kind in {"removed", "added"}:
            block: list[DiffLine] = []

            while index < len(rows) and rows[index].kind in {"removed", "added"}:
                block.append(rows[index])
                index += 1

            rendered.extend(format_change_block(block))
            continue

        rendered.append(format_diff_row(row))
        index += 1

    return rendered


def format_preview_rows(preview: str) -> list[Text | str]:
    rows = parse_unified_diff(preview)

    if not rows:
        return []

    return format_diff_rows(rows)