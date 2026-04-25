# tests/test_textual_diff_renderer.py

from textual_diff_renderer import render_approval_preview


class FakeRichLog:
    def __init__(self):
        self.messages = []

    def write(self, message):
        self.messages.append(message)


def test_render_approval_preview_handles_missing_preview():
    log = FakeRichLog()

    render_approval_preview(
        preview_log=log,
        preview=None,
        preview_path=None,
    )

    rendered = [str(message) for message in log.messages]

    assert any("Preview" in message for message in rendered)
    assert any("No preview available" in message for message in rendered)


def test_render_approval_preview_writes_file_header_and_rows():
    log = FakeRichLog()

    render_approval_preview(
        preview_log=log,
        preview='New file: "sample.txt"\n+ hello',
        preview_path="sample.txt",
    )

    rendered = [str(message) for message in log.messages]

    assert "▸ sample.txt (+1, -0)" in rendered
    assert " old  new │ Δ │ content" in rendered
    assert any("│ + │ hello" in message for message in rendered)