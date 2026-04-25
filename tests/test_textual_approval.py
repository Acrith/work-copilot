# tests/test_textual_approval.py

from approval import ApprovalAction, ApprovalRequest
from textual_approval import TextualApprovalHandler


class FakeRichLog:
    def __init__(self):
        self.messages = []

    def write(self, message):
        self.messages.append(message)


def test_textual_approval_handler_denies_with_feedback():
    log = FakeRichLog()
    handler = TextualApprovalHandler(log)

    response = handler.request_approval(
        ApprovalRequest(
            function_name="Update",
            args={"path": "sample.py"},
            preview_path="sample.py",
            preview="diff preview",
        )
    )

    assert response.action == ApprovalAction.DENY_WITH_FEEDBACK
    assert response.feedback
    assert any("Textual approval UI" in str(message) for message in log.messages)
    assert any("diff preview" in str(message) for message in log.messages)


def test_textual_approval_handler_handles_request_without_preview():
    log = FakeRichLog()
    handler = TextualApprovalHandler(log)

    response = handler.request_approval(
        ApprovalRequest(
            function_name="Bash",
            args={"command": "echo hello"},
        )
    )

    assert response.action == ApprovalAction.DENY_WITH_FEEDBACK
    assert response.feedback
    assert any("Bash" in str(message) for message in log.messages)