from rich.text import Text

from console_ui import (
    _highlight_changed_spans,
    _render_context_line,
    _render_hunk_line,
    _render_styled_diff_line,
)
from previews import ParsedDiffLine


def test_highlight_changed_spans_preserves_text():
    old_rendered, new_rendered = _highlight_changed_spans(
        "assert result == 'src/target.py'",
        "assert result == 'src/goal.py'",
    )

    assert old_rendered.plain == "assert result == 'src/target.py'"
    assert new_rendered.plain == "assert result == 'src/goal.py'"


def test_highlight_changed_spans_creates_spans():
    old_rendered, new_rendered = _highlight_changed_spans(
        "target",
        "goal",
    )

    assert len(old_rendered.spans) > 0
    assert len(new_rendered.spans) > 0


def test_render_context_line_contains_line_numbers_and_text():
    line = ParsedDiffLine(
        kind="context",
        text="hello world",
        old_lineno=10,
        new_lineno=10,
    )

    rendered = _render_context_line(line)

    assert rendered.plain == "  10   10   hello world"


def test_render_hunk_line_contains_hunk_text():
    line = ParsedDiffLine(
        kind="hunk",
        text="@@ -1,3 +1,3 @@",
    )

    rendered = _render_hunk_line(line)

    assert rendered.plain == "@@ -1,3 +1,3 @@"


def test_render_styled_diff_line_for_add():
    content = Text("new line")
    rendered = _render_styled_diff_line(None, 7, "+", content)

    assert rendered.plain == "        7 + new line"


def test_render_styled_diff_line_for_remove():
    content = Text("old line")
    rendered = _render_styled_diff_line(12, None, "-", content)

    assert rendered.plain == "  12      - old line"


def test_highlight_changed_spans_for_small_word_replacement():
    old_rendered, new_rendered = _highlight_changed_spans(
        "test_git_status_success_clean_repo",
        "test_git_status_provides_clean_repo",
    )

    assert old_rendered.plain == "test_git_status_success_clean_repo"
    assert new_rendered.plain == "test_git_status_provides_clean_repo"
    assert len(old_rendered.spans) > 0
    assert len(new_rendered.spans) > 0