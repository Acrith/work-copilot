# tests/test_textual_preview.py

from rich.text import Text

from textual_preview import (
    DiffLine,
    DiffSummary,
    format_diff_column_header,
    format_diff_file_header,
    format_diff_row,
    format_diff_rows,
    format_hunk_label,
    format_line_number,
    format_preview_line,
    format_preview_rows,
    parse_hunk_header,
    parse_unified_diff,
    strip_diff_marker,
    summarize_diff_rows,
)


def test_format_preview_line_formats_added_line():
    formatted = format_preview_line("+ hello")

    assert isinstance(formatted, Text)
    assert str(formatted) == "+ hello"


def test_format_preview_line_formats_removed_line():
    formatted = format_preview_line("- old")

    assert isinstance(formatted, Text)
    assert str(formatted) == "- old"


def test_format_preview_line_does_not_treat_diff_file_header_as_removed_line():
    formatted = format_preview_line("--- old")

    assert isinstance(formatted, Text)
    assert str(formatted) == "--- old"


def test_format_preview_line_does_not_treat_diff_file_header_as_added_line():
    formatted = format_preview_line("+++ new")

    assert isinstance(formatted, Text)
    assert str(formatted) == "+++ new"


def test_format_preview_line_formats_diff_hunk_line():
    formatted = format_preview_line("@@ -1,1 +1,1 @@")

    assert isinstance(formatted, Text)
    assert str(formatted) == "@@ -1,1 +1,1 @@"


def test_format_preview_line_formats_new_file_header():
    formatted = format_preview_line('New file: "sample.txt"')

    assert isinstance(formatted, Text)
    assert str(formatted) == 'New file: "sample.txt"'


def test_format_preview_line_leaves_plain_line_as_string():
    formatted = format_preview_line("plain text")

    assert formatted == "plain text"


def test_parse_hunk_header_returns_line_starts():
    assert parse_hunk_header("@@ -10,2 +12,3 @@") == (10, 12)


def test_parse_hunk_header_handles_missing_counts():
    assert parse_hunk_header("@@ -1 +1 @@") == (1, 1)


def test_parse_hunk_header_returns_none_for_non_hunk():
    assert parse_hunk_header("+ hello") is None


def test_parse_unified_diff_tracks_added_removed_and_context_lines():
    rows = parse_unified_diff(
        "\n".join(
            [
                "--- old.txt",
                "+++ new.txt",
                "@@ -1,3 +1,3 @@",
                " unchanged",
                "-old",
                "+new",
            ]
        )
    )

    assert rows == [
        DiffLine(kind="file_header", text="--- old.txt"),
        DiffLine(kind="file_header", text="+++ new.txt"),
        DiffLine(kind="hunk", text="@@ -1,3 +1,3 @@"),
        DiffLine(kind="context", text=" unchanged", old_line_no=1, new_line_no=1),
        DiffLine(kind="removed", text="-old", old_line_no=2, new_line_no=None),
        DiffLine(kind="added", text="+new", old_line_no=None, new_line_no=2),
    ]


def test_parse_unified_diff_tracks_new_file_lines():
    rows = parse_unified_diff('New file: "sample.txt"\n+ hello')

    assert rows == [
        DiffLine(kind="metadata", text='New file: "sample.txt"'),
        DiffLine(kind="added", text="+ hello", old_line_no=None, new_line_no=1),
    ]


def test_format_line_number_pads_numbers():
    assert format_line_number(1) == "   1"
    assert format_line_number(25) == "  25"


def test_format_line_number_returns_blank_for_none():
    assert format_line_number(None) == "    "


def test_strip_diff_marker_removes_added_marker_and_leading_space():
    assert strip_diff_marker("+ hello") == "hello"


def test_strip_diff_marker_removes_removed_marker_and_leading_space():
    assert strip_diff_marker("- old") == "old"


def test_strip_diff_marker_strips_plain_text():
    assert strip_diff_marker(" unchanged") == "unchanged"


def test_format_hunk_label_formats_old_and_new_ranges():
    assert format_hunk_label("@@ -1,2 +1,3 @@") == "change -1,2 → +1,3"


def test_format_diff_row_renders_added_line_with_marker_column():
    row = DiffLine(kind="added", text="+new", old_line_no=None, new_line_no=3)

    formatted = format_diff_row(row)

    assert isinstance(formatted, Text)
    assert "3" in str(formatted)
    assert "│ + │ new" in str(formatted)


def test_format_diff_row_renders_removed_line_with_marker_column():
    row = DiffLine(kind="removed", text="-old", old_line_no=2, new_line_no=None)

    formatted = format_diff_row(row)

    assert isinstance(formatted, Text)
    assert "2" in str(formatted)
    assert "│ - │ old" in str(formatted)


def test_format_diff_row_renders_context_line_with_marker_column():
    row = DiffLine(kind="context", text=" unchanged", old_line_no=1, new_line_no=1)

    formatted = format_diff_row(row)

    assert isinstance(formatted, Text)
    assert "1" in str(formatted)
    assert "│   │ unchanged" in str(formatted)


def test_format_preview_rows_uses_structured_diff_rows():
    rendered = format_preview_rows(
        "\n".join(
            [
                "@@ -1,2 +1,2 @@",
                "-old",
                "+new",
            ]
        )
    )

    assert [str(row) for row in rendered] == [
        " old  new │ Δ │ content",
        "change -1,2 → +1,2",
        "   1      │ - │ old",
        "        1 │ + │ new",
    ]


def test_summarize_diff_rows_counts_added_and_removed_lines():
    rows = [
        DiffLine(kind="context", text=" unchanged", old_line_no=1, new_line_no=1),
        DiffLine(kind="removed", text="-old", old_line_no=2, new_line_no=None),
        DiffLine(kind="added", text="+new", old_line_no=None, new_line_no=2),
    ]

    summary = summarize_diff_rows(rows)

    assert summary == DiffSummary(additions=1, removals=1)


def test_format_diff_column_header():
    header = format_diff_column_header()

    assert isinstance(header, Text)
    assert str(header) == " old  new │ Δ │ content"


def test_format_diff_file_header_includes_path_and_counts():
    header = format_diff_file_header(
        "sample.py",
        DiffSummary(additions=2, removals=1),
    )

    assert isinstance(header, Text)
    assert str(header) == "▸ sample.py (+2, -1)"


def test_format_diff_rows_adds_column_header_before_hunk_label():
    rows = [
        DiffLine(kind="hunk", text="@@ -1,1 +1,1 @@"),
        DiffLine(kind="removed", text="-old", old_line_no=1, new_line_no=None),
        DiffLine(kind="added", text="+new", old_line_no=None, new_line_no=1),
    ]

    rendered = format_diff_rows(rows)

    assert [str(row) for row in rendered] == [
        " old  new │ Δ │ content",
        "change -1,1 → +1,1",
        "   1      │ - │ old",
        "        1 │ + │ new",
    ]


def test_format_diff_rows_skips_metadata_and_file_header_rows():
    rows = [
        DiffLine(kind="metadata", text='New file: "sample.txt"'),
        DiffLine(kind="file_header", text="--- sample.txt"),
        DiffLine(kind="file_header", text="+++ sample.txt"),
        DiffLine(kind="added", text="+hello", old_line_no=None, new_line_no=1),
    ]

    rendered = format_diff_rows(rows)

    assert [str(row) for row in rendered] == [
        " old  new │ Δ │ content",
        "        1 │ + │ hello",
    ]