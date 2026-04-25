# textual_approval.py

from collections.abc import Callable

from rich.text import Text
from textual.widgets import RichLog

from approval import ApprovalAction, ApprovalHandler, ApprovalRequest, ApprovalResponse


class TextualApprovalHandler(ApprovalHandler):
    def __init__(
        self,
        log: RichLog,
        *,
        write_callback: Callable[[str | Text], None] | None = None,
    ) -> None:
        self.log = log
        self.write_callback = write_callback

    def _write(self, message: str | Text) -> None:
        if self.write_callback is not None:
            self.write_callback(message)
            return

        self.log.write(message)

    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        if request.preview is not None:
            self._write(
                Text.from_markup(
                    f"[bold #ebcb8b]Approval required for {request.function_name}[/]"
                )
            )
            self._write(
                Text.from_markup(f"[#7f8ea3]Path:[/] {request.preview_path or ''}")
            )
            self._write(request.preview)
        else:
            self._write(
                Text.from_markup(
                    f"[bold #ebcb8b]Approval required for {request.function_name}[/]"
                )
            )

        self._write(
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