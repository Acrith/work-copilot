# tests/test_textual_preview.py

from rich.text import Text

from textual_preview import DiffLine, format_preview_line, parse_hunk_header, parse_unified_diff


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


def test_parse_unified_diff_tracks_metadata_lines():
    rows = parse_unified_diff('New file: "sample.txt"\n+ hello')

    assert rows == [
        DiffLine(kind="metadata", text='New file: "sample.txt"'),
        DiffLine(kind="added", text="+ hello", old_line_no=None, new_line_no=None),
    ]