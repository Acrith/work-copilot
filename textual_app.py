# textual_app.py

from collections.abc import Callable
from threading import Event

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, RichLog, Static

from approval import ApprovalAction, ApprovalRequest, ApprovalResponse
from interactive_commands import (
    format_interactive_help,
    format_interactive_status,
    parse_interactive_command,
)
from interactive_session import (
    InteractiveSessionConfig,
    create_interactive_session_state,
    reset_interactive_context,
    run_interactive_model_turn,
)
from permissions import PermissionContext
from providers.base import Provider
from textual_approval import TextualApprovalHandler
from textual_event_sink import TextualEventSink


class WorkCopilotTextualApp(App):
    """Experimental Textual shell for Work Copilot."""

    CSS = """
    Screen {
        background: #10151c;
    }

    Header {
        background: #17202a;
        color: #d7e1ec;
    }

    Footer {
        background: #17202a;
        color: #d7e1ec;
    }

    #app-body {
        height: 1fr;
    }

    #sidebar {
        width: 34;
        min-width: 28;
        max-width: 42;
        border: solid #2b3a4a;
        background: #121a23;
        padding: 1;
    }

    #main-area {
        width: 1fr;
        height: 1fr;
    }

    #activity-log {
        height: 1fr;
        border: solid #2b3a4a;
        background: #0d1117;
        padding: 1;
    }

    #prompt-row {
        height: 3;
        border: solid #2b3a4a;
        background: #121a23;
        padding: 0 1;
    }

    #prompt-input {
        width: 1fr;
    }

    .section-title {
        color: #88c0d0;
        text-style: bold;
        margin-bottom: 1;
    }

    .muted {
        color: #7f8ea3;
    }

    .good {
        color: #a3be8c;
    }

    .warning {
        color: #ebcb8b;
    }

    #approval-panel {
        height: auto;
        max-height: 24;
        border: heavy #ebcb8b;
        background: #141821;
        padding: 1 2;
    }

    .hidden {
        display: none;
    }

    #approval-panel.hidden {
        display: none;
    }
    """

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(
        self,
        *,
        config: InteractiveSessionConfig,
        provider_factory: Callable[[], Provider],
        permission_context: PermissionContext,
    ) -> None:
        super().__init__()
        self.config = config
        self.provider_factory = provider_factory
        self.permission_context = permission_context
        self.state = create_interactive_session_state(provider_factory)
        self.is_agent_running = False
        self.pending_approval_request: ApprovalRequest | None = None
        self.pending_approval_response: ApprovalResponse | None = None
        self.pending_approval_event: Event | None = None
        self.is_collecting_approval_feedback = False


    def _set_running(self, is_running: bool) -> None:
        self.is_agent_running = is_running

        prompt = self.query_one("#prompt-input", Input)
        prompt.disabled = is_running

        if is_running:
            prompt.placeholder = "Agent is running..."
            self.sub_title = "Running"
        else:
            prompt.placeholder = "Type /help, /status, /clear, or /exit"
            self.sub_title = "Experimental Textual shell"
            prompt.focus()

        self._refresh_sidebar()


    def _log_blank(self) -> None:
        self._log("")


    def _log(self, message: str) -> None:
        log = self.query_one("#activity-log", RichLog)
        log.write(message)


    def _log_markup(self, markup: str) -> None:
        self._log(Text.from_markup(markup))


    def _log_user_message(self, message: str) -> None:
        self._log_blank()
        self._log_markup("[bold #88c0d0]You[/]")
        self._log(message)


    def _log_assistant_message(self, message: str) -> None:
        self._log_blank()
        self._log_markup("[bold #a3be8c]Work Copilot[/]")
        self._log(message)


    def _log_system_message(self, message: str) -> None:
        self._log_markup(f"[#7f8ea3]{message}[/]")


    def _log_command_lines(self, lines: list[str]) -> None:
        for index, line in enumerate(lines):
            if index == 0:
                self._log_markup(f"[bold #88c0d0]{line}[/]")
            elif line.startswith("  /"):
                command, description = line.split(maxsplit=1)
                self._log_markup(f"  [#c678dd]{command}[/]    [#d7e1ec]{description}[/]")
            elif ":" in line:
                label, value = line.split(":", maxsplit=1)
                self._log_markup(f"  [#7f8ea3]{label}:[/] [#d7e1ec]{value.strip()}[/]")
            else:
                self._log(line)


    def _clear_prompt(self) -> None:
        prompt = self.query_one("#prompt-input", Input)
        prompt.value = ""


    def request_textual_approval(
        self,
        request: ApprovalRequest,
        approval_event: Event,
    ) -> None:
        self.pending_approval_request = request
        self.pending_approval_response = None
        self.pending_approval_event = approval_event

        panel = self.query_one("#approval-panel", Static)
        panel.remove_class("hidden")
        panel.update(self._format_approval_panel(request))

        prompt = self.query_one("#prompt-input", Input)
        prompt.disabled = False
        prompt.placeholder = "Approval required: y = allow once, n = deny, f = deny with feedback"
        prompt.focus()

        self.sub_title = "Approval required"
        self._refresh_sidebar()


    def _format_approval_panel(self, request: ApprovalRequest) -> str:
        lines = [
            "[bold #ebcb8b]Approval request[/] [#7f8ea3]The agent wants permission to continue.[/]",
            "",
            "[bold #88c0d0]Request[/]",
            f"  [#7f8ea3]Tool[/]    {request.function_name}",
        ]

        if request.preview_path:
            lines.append(f"  [#7f8ea3]Path[/]    {request.preview_path}")

        if request.preview:
            lines.extend(
                [
                    "",
                    "[bold #88c0d0]Preview[/]",
                    "[#7f8ea3]────────────────────────────────────────[/]",
                    request.preview,
                    "[#7f8ea3]────────────────────────────────────────[/]",
                ]
            )

        lines.extend(
            [
                "",
                "[bold #88c0d0]Actions[/]",
                "  [#a3be8c]y[/]  allow once",
                "  [#bf616a]n[/]  deny",
                "  [#ebcb8b]f[/]  deny with feedback",
            ]
        )

        return "\n".join(lines)


    def _complete_textual_approval(self, response: ApprovalResponse) -> None:
        if self.pending_approval_event is None:
            return

        self.pending_approval_response = response
        self.is_collecting_approval_feedback = False

        panel = self.query_one("#approval-panel", Static)
        panel.update("")
        panel.add_class("hidden")

        self.pending_approval_event.set()

        self.pending_approval_request = None
        self.pending_approval_event = None

        if self.is_agent_running:
            prompt = self.query_one("#prompt-input", Input)
            prompt.disabled = True
            prompt.placeholder = "Agent is running..."

        self.sub_title = "Running" if self.is_agent_running else "Experimental Textual shell"
        self._refresh_sidebar()


    @work(thread=True)
    def _run_model_turn_worker(self, user_prompt: str) -> None:
        log = self.query_one("#activity-log", RichLog)
        event_sink = TextualEventSink(
            log,
            write_callback=lambda message: self.call_from_thread(log.write, message),
        )
        approval_handler = TextualApprovalHandler(
            request_callback=lambda request, approval_event: self.call_from_thread(
                self.request_textual_approval,
                request,
                approval_event,
            ),
            response_getter=lambda: self.pending_approval_response,
        )

        try:
            final_text = run_interactive_model_turn(
                config=self.config,
                state=self.state,
                permission_context=self.permission_context,
                user_prompt=user_prompt,
                extra_event_sinks=[event_sink],
                terminal_output=False,
                approval_handler=approval_handler,
            )

            if final_text is None:
                self.call_from_thread(
                    self._log_system_message,
                    "Turn ended without a final response. You can continue or use /clear.",
                )
        except Exception as exc:
            self.call_from_thread(
                self._log_system_message,
                f"Textual worker error: {exc}",
            )
        finally:
            self.call_from_thread(self._set_running, False)


    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_prompt = event.value.strip()
        self._clear_prompt()

        if not user_prompt:
            return

        if self.pending_approval_event is not None:
            if self.is_collecting_approval_feedback:
                feedback = user_prompt.strip()

                if not feedback:
                    self._log_system_message("Feedback cannot be empty. Type feedback or n to deny.")
                    return

                self._complete_textual_approval(
                    ApprovalResponse(
                        action=ApprovalAction.DENY_WITH_FEEDBACK,
                        feedback=feedback,
                    )
                )
                self._log_system_message("Approval denied with feedback.")
                return

            normalized = user_prompt.lower()

            if normalized == "y":
                self._complete_textual_approval(
                    ApprovalResponse(action=ApprovalAction.ALLOW_ONCE)
                )
                self._log_system_message("Approval granted once.")
                return

            if normalized == "n":
                self._complete_textual_approval(
                    ApprovalResponse(action=ApprovalAction.DENY)
                )
                self._log_system_message("Approval denied.")
                return

            if normalized == "f":
                self.is_collecting_approval_feedback = True
                prompt = self.query_one("#prompt-input", Input)
                prompt.placeholder = "Type denial feedback and press Enter"
                self._log_system_message("Type denial feedback and press Enter.")
                return

            self._log_system_message(
                "Approval pending. Press y to allow once, n to deny, or f to deny with feedback."
            )
            return
        
        if self.is_agent_running:
            self._log_system_message("A turn is already running. Please wait.")
            return

        command = parse_interactive_command(user_prompt)

        if command == "exit":
            self.exit()
            return

        if command == "help":
            self._log_blank()
            self._log_command_lines(format_interactive_help())
            return

        if command == "status":
            self._log_blank()
            self._log_command_lines(
                format_interactive_status(config=self.config, state=self.state)
            )
            return

        if command == "clear":
            reset_interactive_context(
                state=self.state,
                provider_factory=self.provider_factory,
            )
            self._refresh_sidebar()
            self._log_blank()
            self._log("Session cleared.")
            return

        if command == "unknown":
            self._log_blank()
            self._log(f"Unknown command: {user_prompt}. Type /help for commands.")
            return

        self._log_user_message(user_prompt)
        self._set_running(True)
        self._run_model_turn_worker(user_prompt)


    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="app-body"):
            yield Static(id="sidebar")

            with Vertical(id="main-area"):
                yield RichLog(id="activity-log", wrap=True)
                yield Static("", id="approval-panel", classes="hidden")
                yield Input(
                    placeholder="Type /help, /status, /clear, or /exit",
                    id="prompt-input",
                )

        yield Footer()

    def on_mount(self) -> None:
        self.title = "Work Copilot"
        self.sub_title = "Experimental Textual shell"

        self._refresh_sidebar()

        self._log_markup("[bold #88c0d0]Work Copilot Textual shell[/]")
        self._log_blank()
        self._log_system_message(
            "Textual mode can run normal prompts and supports basic write/exec approval."
        )
        self._log_system_message(
            "Approval UI currently supports allow once and deny."
        )
        self._log_blank()
        self._log_markup(
           "[#a3be8c]Ready.[/] Type [bold]/exit[/] or press [bold]Ctrl+Q[/] to quit."
        )

        self.query_one("#prompt-input", Input).focus()

    def _refresh_sidebar(self) -> None:
        run_status = "RUNNING" if self.is_agent_running else "idle"
        run_status_style = "#ebcb8b" if self.is_agent_running else "#7f8ea3"
        logging_status = "enabled" if self.config.log_run else "disabled"

        sidebar = self.query_one("#sidebar", Static)
        sidebar.update(
            "\n".join(
                [
                    "[bold #88c0d0]Session[/]",
                    "",
                    f"[#7f8ea3]Provider[/]        {self.config.provider_name}",
                    f"[#7f8ea3]Model[/]           {self.config.model}",
                    f"[#7f8ea3]Permission[/]      {self.config.permission_mode}",
                    f"[#7f8ea3]Max iterations[/]  {self.config.max_iterations}",
                    f"[#7f8ea3]Logging[/]         {logging_status}",
                    "",
                    "[bold #88c0d0]Workspace[/]",
                    self.config.workspace,
                    "",
                    "[bold #88c0d0]State[/]",
                    f"[#7f8ea3]Status[/]          [{run_status_style}]{run_status}[/]",
                    f"[#7f8ea3]Session id[/]      {self.state.interactive_session_id}",
                    f"[#7f8ea3]Context index[/]   {self.state.context_index}",
                    f"[#7f8ea3]Turn index[/]      {self.state.turn_index}",
                    "",
                    "[bold #88c0d0]Controls[/]",
                    "[#7f8ea3]Ctrl+Q[/]          Quit",
                ]
            )
        )