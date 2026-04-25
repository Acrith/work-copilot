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


def format_line_number(value: int | None) -> str:
    if value is None:
        return "    "

    return f"{value:>4}"


def format_diff_column_header() -> Text:
    return Text(f"{'old':>4} {'new':>4}  content", style="bold #8b949e")


def format_diff_file_header(path: str, summary: DiffSummary) -> Text:
    text = Text()
    text.append("▸ ", style="#8b949e")
    text.append(path, style="bold #c9d1d9")
    text.append(" ")
    text.append(f"(+{summary.additions}", style="bold #7ee787")
    text.append(", ")
    text.append(f"-{summary.removals})", style="bold #ff7b72")
    return text


def format_diff_row(row: DiffLine) -> Text | str:
    if row.kind == "metadata":
        return Text(row.text, style="bold #f2cc60")

    if row.kind == "file_header":
        return Text(row.text, style="#8b949e")

    if row.kind == "hunk":
        return Text(row.text, style="bold #79c0ff")

    old_no = format_line_number(row.old_line_no)
    new_no = format_line_number(row.new_line_no)

    if row.kind == "added":
        return Text(f"{old_no} {new_no}  {row.text}", style="bold #7ee787")

    if row.kind == "removed":
        return Text(f"{old_no} {new_no}  {row.text}", style="bold #ff7b72")

    if row.kind == "context":
        return Text(f"{old_no} {new_no}  {row.text}", style="#c9d1d9")

    return row.text


def format_diff_rows(rows: list[DiffLine]) -> list[Text | str]:
    rendered: list[Text | str] = []
    wrote_column_header = False

    for row in rows:
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