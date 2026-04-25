# tests/test_textual_preview.py

from rich.text import Text

from textual_preview import format_preview_line


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