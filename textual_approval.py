# textual_approval.py

from rich.text import Text
from textual.widgets import RichLog

from approval import ApprovalAction, ApprovalHandler, ApprovalRequest, ApprovalResponse


class TextualApprovalHandler(ApprovalHandler):
    def __init__(self, log: RichLog) -> None:
        self.log = log

    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        if request.preview is not None:
            self.log.write(
                Text.from_markup(
                    f"[bold #ebcb8b]Approval required for {request.function_name}[/]"
                )
            )
            self.log.write(Text.from_markup(f"[#7f8ea3]Path:[/] {request.preview_path or ''}"))
            self.log.write(request.preview)
        else:
            self.log.write(
                Text.from_markup(
                    f"[bold #ebcb8b]Approval required for {request.function_name}[/]"
                )
            )

        self.log.write(
            Text.from_markup(
                "[#7f8ea3]Textual approval UI is not implemented yet. "
                "Use the interactive CLI for write/exec tasks for now.[/]"
            )
        )

        return ApprovalResponse(
            action=ApprovalAction.DENY_WITH_FEEDBACK,
            feedback=(
                "Textual approval UI is not implemented yet. "
                "Use interactive CLI for write/exec tasks."
            ),
        )