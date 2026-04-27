# textual_approval_screen.py

from collections.abc import Callable

from rich.markdown import Markdown
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Static

from approval import ApprovalAction, ApprovalRequest, ApprovalResponse
from previews import is_unified_diff_preview
from textual_diff_view import DiffPreview


def should_render_diff_preview(preview: str | None) -> bool:
    return bool(preview and is_unified_diff_preview(preview))


class ApprovalScreen(Screen):
    """Full-screen approval review UI."""

    CSS = """
    Screen {
        background: #10151c;
    }

    #approval-root {
        height: 1fr;
    }

    #approval-sidebar {
        width: 32;
        min-width: 28;
        max-width: 40;
        border: solid #b48ead;
        background: #121722;
        padding: 1;
    }

    #approval-main {
        width: 1fr;
        height: 1fr;
    }

    #approval-header {
        height: auto;
        border: solid #2b3a4a;
        background: #141821;
        padding: 1 2;
    }

    #approval-feedback-input {
        height: 3;
        border: solid #ebcb8b;
        background: #1b1a14;
        padding: 0 1;
    }

    #approval-feedback-input.hidden {
        display: none;
    }

    #approval-status {
        height: auto;
        min-height: 1;
        color: #7f8ea3;
        padding: 0 1;
    }

    #approval-preview-text {
        height: 1fr;
        border: solid #2b3a4a;
        background: #0d1117;
        color: #d7e1ec;
        padding: 1 2;
    }

    #approval-preview-text.empty {
        color: #7f8ea3;
    }
    """

    BINDINGS = [
        ("y", "allow_once", "Allow once"),
        ("n", "deny", "Deny"),
        ("f", "deny_with_feedback", "Feedback"),
        ("s", "allow_tool_session", "Tool session"),
        ("p", "allow_path_session", "Path session"),
    ]

    def __init__(
        self,
        *,
        request: ApprovalRequest,
        complete_callback: Callable[[ApprovalResponse], None],
    ) -> None:
        super().__init__()
        self.request = request
        self.complete_callback = complete_callback

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="approval-root"):
            yield Static(self._format_sidebar(), id="approval-sidebar")

            with Vertical(id="approval-main"):
                yield Static(self._format_header(), id="approval-header")

                if should_render_diff_preview(self.request.preview):
                    yield DiffPreview(id="approval-preview")
                else:
                    preview_text = self.request.preview or "No preview available."
                    classes = "empty" if not self.request.preview else ""
                    renderable = (
                        Text("No preview available.")
                        if not self.request.preview
                        else Markdown(preview_text)
                    )
                    yield Static(
                        renderable,
                        id="approval-preview-text",
                        classes=classes,
                    )

                yield Input(
                    placeholder="Type denial feedback and press Enter",
                    id="approval-feedback-input",
                    classes="hidden",
                    disabled=True,
                )
                yield Static("", id="approval-status")

        yield Footer()

    def on_mount(self) -> None:
        self.title = "Work Copilot"
        self.sub_title = "Approval request"

        if should_render_diff_preview(self.request.preview):
            preview = self.query_one("#approval-preview", DiffPreview)
            preview.render_preview(
                preview=self.request.preview,
                preview_path=self.request.preview_path,
            )

    def _format_header(self) -> str:
        return "\n".join(
            [
                "[bold #ebcb8b]Approval request[/] "
                "[#7f8ea3]The agent wants permission to continue.[/]",
                "",
                f"[#7f8ea3]Tool[/] {self.request.function_name}",
                f"[#7f8ea3]Path[/] {self.request.preview_path or 'not available'}",
            ]
        )

    def _format_sidebar(self) -> str:
        path_action = (
            "[#88c0d0]p[/]  allow path for session"
            if self.request.preview_path
            else "[#7f8ea3]p[/]  path approval unavailable"
        )

        return "\n".join(
            [
                "[bold #88c0d0]Actions[/]",
                "",
                "[#a3be8c]y[/]  allow once",
                "[#bf616a]n[/]  deny",
                "[#ebcb8b]f[/]  deny with feedback",
                "[#88c0d0]s[/]  allow tool for session",
                path_action,
                "",
                "[bold #88c0d0]Review[/]",
                "",
                "[#7f8ea3]Use the preview pane to inspect the requested change.[/]",
                "",
                "[#7f8ea3]Press a key to choose an action.[/]",
            ]
        )

    def _set_status(self, message: str) -> None:
        status = self.query_one("#approval-status", Static)
        status.update(message)

    def _complete(self, response: ApprovalResponse) -> None:
        self.complete_callback(response)
        self.app.pop_screen()

    def action_allow_once(self) -> None:
        self._complete(ApprovalResponse(action=ApprovalAction.ALLOW_ONCE))

    def action_deny(self) -> None:
        self._complete(ApprovalResponse(action=ApprovalAction.DENY))

    def action_deny_with_feedback(self) -> None:
        feedback_input = self.query_one("#approval-feedback-input", Input)
        feedback_input.disabled = False
        feedback_input.value = ""
        feedback_input.remove_class("hidden")
        feedback_input.focus()
        self._set_status("Type denial feedback and press Enter.")

    def action_allow_tool_session(self) -> None:
        self._complete(ApprovalResponse(action=ApprovalAction.ALLOW_TOOL_SESSION))

    def action_allow_path_session(self) -> None:
        if self.request.preview_path is None:
            self._set_status("Path session approval is not available for this request.")
            return

        self._complete(ApprovalResponse(action=ApprovalAction.ALLOW_PATH_SESSION))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "approval-feedback-input":
            return

        feedback = event.value.strip()

        if not feedback:
            self._set_status("Feedback cannot be empty.")
            return

        self._complete(
            ApprovalResponse(
                action=ApprovalAction.DENY_WITH_FEEDBACK,
                feedback=feedback,
            )
        )