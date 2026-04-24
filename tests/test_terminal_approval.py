import terminal_approval as terminal_approval_module
from approval import ApprovalAction, ApprovalRequest, ApprovalResponse


def test_terminal_approval_handler_shows_preview_and_prompts(monkeypatch):
    captured = {}

    def fake_print_mutation_preview(function_name, path, preview):
        captured["preview"] = (function_name, path, preview)

    def fake_approval_prompt(function_name, args):
        captured["prompt"] = (function_name, args)
        return ApprovalResponse(ApprovalAction.ALLOW_ONCE)

    monkeypatch.setattr(
        terminal_approval_module,
        "print_mutation_preview",
        fake_print_mutation_preview,
    )
    monkeypatch.setattr(
        terminal_approval_module,
        "approval_prompt",
        fake_approval_prompt,
    )

    handler = terminal_approval_module.TerminalApprovalHandler()

    response = handler.request_approval(
        ApprovalRequest(
            function_name="write_file",
            args={"file_path": "notes.txt", "content": "hello"},
            preview_path="notes.txt",
            preview="PREVIEW TEXT",
        )
    )

    assert response == ApprovalResponse(ApprovalAction.ALLOW_ONCE)
    assert captured["preview"] == ("write_file", "notes.txt", "PREVIEW TEXT")
    assert captured["prompt"] == (
        "write_file",
        {"file_path": "notes.txt", "content": "hello"},
    )


def test_terminal_approval_handler_skips_preview_when_missing(monkeypatch):
    captured = {"preview_called": False}

    def fake_print_mutation_preview(function_name, path, preview):
        captured["preview_called"] = True

    def fake_approval_prompt(function_name, args):
        return ApprovalResponse(ApprovalAction.DENY)

    monkeypatch.setattr(
        terminal_approval_module,
        "print_mutation_preview",
        fake_print_mutation_preview,
    )
    monkeypatch.setattr(
        terminal_approval_module,
        "approval_prompt",
        fake_approval_prompt,
    )

    handler = terminal_approval_module.TerminalApprovalHandler()

    response = handler.request_approval(
        ApprovalRequest(
            function_name="bash",
            args={"command": "echo hello"},
        )
    )

    assert response == ApprovalResponse(ApprovalAction.DENY)
    assert captured["preview_called"] is False