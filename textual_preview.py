# textual_preview.py

import re
from dataclasses import dataclass
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

DIFF_COLUMN_SEPARATOR = "│"
STYLE_DIFF_HEADER = "bold #8b949e"
STYLE_FILE_HEADER = "bold #c9d1d9"
STYLE_METADATA = "bold #f2cc60"
STYLE_HUNK = "bold #79c0ff on #111d2e"
STYLE_ADDED = "bold #7ee787 on #102a16"
STYLE_REMOVED = "bold #ff7b72 on #2a1414"
STYLE_CONTEXT = "#c9d1d9"
STYLE_MUTED = "#8b949e"


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


STRUCTURED_DIFF_KINDS = {"added", "removed", "context"}

HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


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
        return Text(line, style="bold #79c0ff")

    if line.startswith("+") and not line.startswith("+++"):
        return Text(line, style="bold #7ee787")

    if line.startswith("-") and not line.startswith("---"):
        return Text(line, style="bold #ff7b72")

    if line.startswith("New file:") or line.startswith("Updated file:"):
        return Text(line, style="bold #f2cc60")

    if line.startswith("Deleted file:"):
        return Text(line, style="bold #ff7b72")

    if line.startswith("+++") or line.startswith("---"):
        return Text(line, style="#8b949e")

    return line


def format_hunk_label(text: str) -> str:
    return f"change {text.replace('@@', '').strip()}"


def format_line_number(value: int | None) -> str:
    if value is None:
        return "    "

    return f"{value:>4}"


def strip_diff_marker(text: str) -> str:
    if text.startswith(("+", "-")):
        return text[1:]

    return text


def format_diff_column_header() -> Text:
    return Text(
        f"{'old':>4} {'new':>4} {DIFF_COLUMN_SEPARATOR} Δ {DIFF_COLUMN_SEPARATOR} content",
        style=STYLE_DIFF_HEADER,
    )


def format_diff_file_header(path: str, summary: DiffSummary) -> Text:
    text = Text()
    text.append("▸ ", style=STYLE_MUTED)
    text.append(path, style=STYLE_FILE_HEADER)
    text.append(" ")
    text.append(f"(+{summary.additions}", style="bold #7ee787")
    text.append(", ")
    text.append(f"-{summary.removals})", style="bold #ff7b72")
    return text


def format_diff_row(row: DiffLine) -> Text | str:
    if row.kind == "metadata":
        return Text(row.text, style=STYLE_METADATA)

    if row.kind == "file_header":
        return Text(row.text, style=STYLE_MUTED)

    if row.kind == "hunk":
        return Text(format_hunk_label(row.text), style=STYLE_HUNK)

    old_no = format_line_number(row.old_line_no)
    new_no = format_line_number(row.new_line_no)

    if row.kind == "added":
        return Text(
            f"{old_no} {new_no} {DIFF_COLUMN_SEPARATOR} + {DIFF_COLUMN_SEPARATOR} {strip_diff_marker(row.text)}",
            style=STYLE_ADDED,
        )

    if row.kind == "removed":
        return Text(
            f"{old_no} {new_no} {DIFF_COLUMN_SEPARATOR} - {DIFF_COLUMN_SEPARATOR} {strip_diff_marker(row.text)}",
            style=STYLE_REMOVED,
        )

    if row.kind == "context":
        return Text(
            f"{old_no} {new_no} {DIFF_COLUMN_SEPARATOR}   {DIFF_COLUMN_SEPARATOR} {row.text.lstrip()}",
            style=STYLE_CONTEXT,
        )

    return row.text


def format_diff_rows(rows: list[DiffLine]) -> list[Text | str]:
    rendered: list[Text | str] = []
    wrote_column_header = False

    for row in rows:
        if row.kind in {"metadata", "file_header"}:
            continue

        if row.kind in STRUCTURED_DIFF_KINDS and not wrote_column_header:
            rendered.append(format_diff_column_header())
            wrote_column_header = True

        rendered.append(format_diff_row(row))

    return rendered


def format_preview_rows(preview: str) -> list[Text | str]:
    rows = parse_unified_diff(preview)

    if not rows:
        return []

    return format_diff_rows(rows)