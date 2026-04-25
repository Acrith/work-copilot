# tests/test_textual_approval_screen.py

from approval import ApprovalRequest
from textual_approval_screen import ApprovalScreen


def test_approval_screen_formats_sidebar_with_path_action():
    screen = ApprovalScreen(
        request=ApprovalRequest(
            function_name="write_file",
            args={"file_path": "sample.py"},
            preview_path="sample.py",
            preview="+ hello",
        ),
        complete_callback=lambda response: None,
    )

    sidebar = screen._format_sidebar()

    assert "allow once" in sidebar
    assert "deny with feedback" in sidebar
    assert "allow tool for session" in sidebar
    assert "allow path for session" in sidebar
    assert "Use the preview pane" in sidebar


def test_approval_screen_formats_header():
    screen = ApprovalScreen(
        request=ApprovalRequest(
            function_name="write_file",
            args={"file_path": "sample.py"},
            preview_path="sample.py",
            preview="+ hello",
        ),
        complete_callback=lambda response: None,
    )

    header = screen._format_header()

    assert "Approval request" in header
    assert "write_file" in header
    assert "sample.py" in header


def test_approval_screen_formats_sidebar_without_path_action():
    screen = ApprovalScreen(
        request=ApprovalRequest(
            function_name="bash",
            args={"command": "echo hello"},
        ),
        complete_callback=lambda response: None,
    )

    sidebar = screen._format_sidebar()

    assert "path approval unavailable" in sidebar
    assert "Use the preview pane" in sidebar