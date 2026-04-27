# textual_app.py

from collections.abc import Callable
from pathlib import Path
from threading import Event

from rich.console import RenderableType
from rich.markdown import Markdown
from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, RichLog, Static, TextArea

from agent_types import ToolCall
from approval import ApprovalRequest, ApprovalResponse
from draft_exports import (
    build_servicedesk_context_path,
    build_servicedesk_draft_path,
    build_servicedesk_draft_subject,
    build_servicedesk_latest_context_path,
    build_servicedesk_latest_draft_path,
    extract_servicedesk_draft_reply,
    is_no_requester_reply_recommended,
    read_text_if_exists,
    save_text_draft,
)
from interactive_commands import (
    build_interactive_help_renderable,
    build_servicedesk_context_prompt,
    build_servicedesk_draft_reply_prompt,
    build_servicedesk_triage_prompt,
    format_interactive_status,
    parse_interactive_command,
    parse_sdp_request_id,
    parse_triage_limit,
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
from textual_approval_screen import ApprovalScreen
from textual_event_sink import TextualEventSink
from tool_dispatch import execute_tool_call

MIN_PROMPT_HEIGHT = 3
MAX_PROMPT_HEIGHT = 8


class PromptTextArea(TextArea):
    """Chat-style prompt composer.

    Enter submits.
    Ctrl+J inserts a newline.
    Shift+Enter inserts a newline if the terminal reports it distinctly.
    Esc clears the composer.
    """

    def _on_key(self, event: events.Key) -> None:
        event_name = getattr(event, "name", "")

        if event.key in {"shift+enter", "ctrl+j"} or event_name in {
            "shift_enter",
            "ctrl_j",
        }:
            self.insert("\n")
            self.app.resize_composer()
            event.prevent_default()
            event.stop()
            return

        if event.key == "enter":
            self.app.submit_composer()
            event.prevent_default()
            event.stop()
            return

        if event.key == "escape":
            self.app.clear_composer()
            event.prevent_default()
            event.stop()
            return


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

    #prompt-input {
        width: 1fr;
        height: 3;
        min-height: 3;
        max-height: 8;
        border: solid #2b3a4a;
        background: #121a23;
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

    def _prompt(self) -> PromptTextArea:
        return self.query_one("#prompt-input", PromptTextArea)

    def _set_running(self, is_running: bool) -> None:
        self.is_agent_running = is_running

        prompt = self._prompt()
        prompt.disabled = is_running

        if is_running:
            prompt.placeholder = "Agent is running..."
            self.sub_title = "Running"
        else:
            prompt.placeholder = (
                "Type /help, /status, /clear, or /exit. "
                "Enter submits, Ctrl+J adds a newline."
            )
            self.sub_title = "Experimental Textual shell"
            prompt.focus()

        self._refresh_sidebar()

    def _log_blank(self) -> None:
        self._log("")

    def _log(self, message: RenderableType) -> None:
        log = self.query_one("#activity-log", RichLog)
        log.write(message)

    def _log_markup(self, markup: str) -> None:
        self._log(Text.from_markup(markup))

    def _log_markdown(self, message: str) -> None:
        self._log(Markdown(message))

    def _log_user_message(self, message: str) -> None:
        self._log_blank()
        self._log_markup("[bold #88c0d0]You[/]")
        self._log(message)

    def _log_assistant_message(self, message: str) -> None:
        self._log_blank()
        self._log_markup("[bold #a3be8c]Work Copilot[/]")
        self._log_markdown(message)

    def _log_system_message(self, message: str) -> None:
        self._log_markup(f"[#7f8ea3]{message}[/]")

    def _log_command_lines(self, lines: list[str]) -> None:
        for index, line in enumerate(lines):
            if index == 0:
                self._log_markup(f"[bold #88c0d0]{line}[/]")
            elif line.startswith("  /"):
                command, description = line.split(maxsplit=1)
                self._log_markup(
                    f"  [#c678dd]{command}[/]    [#d7e1ec]{description}[/]"
                )
            elif ":" in line:
                label, value = line.split(":", maxsplit=1)
                self._log_markup(f"  [#7f8ea3]{label}:[/] [#d7e1ec]{value.strip()}[/]")
            else:
                self._log(line)

    def resize_composer(self) -> None:
        prompt = self._prompt()
        line_count = prompt.text.count("\n") + 1
        height = max(MIN_PROMPT_HEIGHT, min(MAX_PROMPT_HEIGHT, line_count + 2))
        prompt.styles.height = height

    def clear_composer(self) -> None:
        prompt = self._prompt()
        prompt.load_text("")
        self.resize_composer()

    def _clear_prompt(self) -> None:
        self.clear_composer()

    def submit_composer(self) -> None:
        prompt = self._prompt()

        if self.is_agent_running:
            self._log_system_message("A turn is already running. Please wait.")
            return

        self._submit_prompt(prompt.text)

    @work(thread=True)
    def _save_servicedesk_draft_worker(
        self,
        *,
        request_id: str,
        subject: str,
        description: str,
    ) -> None:
        approval_handler = TextualApprovalHandler(
            request_callback=lambda request, approval_event: self.call_from_thread(
                self.request_textual_approval,
                request,
                approval_event,
            ),
            response_getter=lambda: self.pending_approval_response,
        )

        try:
            result = execute_tool_call(
                ToolCall(
                    name="servicedesk_add_request_draft",
                    args={
                        "request_id": request_id,
                        "subject": subject,
                        "description": description,
                    },
                ),
                self.config.workspace,
                self.permission_context,
                approval_handler=approval_handler,
            )

            if "error" in result.payload:
                self.call_from_thread(
                    self._log_system_message,
                    f"Could not save ServiceDesk draft: {result.payload['error']}",
                )
                return

            self.call_from_thread(
                self._log_system_message,
                f"ServiceDesk draft saved for request {request_id}.",
            )
        except Exception as exc:
            self.call_from_thread(
                self._log_system_message,
                f"ServiceDesk draft save error: {exc}",
            )
        finally:
            self.call_from_thread(self._set_running, False)

    def request_textual_approval(
        self,
        request: ApprovalRequest,
        approval_event: Event,
    ) -> None:
        self.pending_approval_request = request
        self.pending_approval_response = None
        self.pending_approval_event = approval_event

        approval_screen = ApprovalScreen(
            request=request,
            complete_callback=self._complete_textual_approval,
        )
        self.push_screen(approval_screen)

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
                "  [#88c0d0]s[/]  allow this tool for session",
            ]
        )

        if request.preview_path:
            lines.append("  [#88c0d0]p[/]  allow this path for session")
        else:
            lines.append("  [#7f8ea3]p[/]  allow path unavailable")

        return "\n".join(lines)

    def _complete_textual_approval(self, response: ApprovalResponse) -> None:
        if self.pending_approval_event is None:
            return

        self.pending_approval_response = response
        self.pending_approval_event.set()

        self.pending_approval_request = None
        self.pending_approval_event = None

        self.sub_title = "Running" if self.is_agent_running else "Experimental Textual shell"
        self._refresh_sidebar()

    @work(thread=True)
    def _run_model_turn_worker(
        self,
        user_prompt: str,
        save_output_path: str | None = None,
        save_latest_path: str | None = None,
    ) -> None:
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

            if final_text is not None and save_output_path is not None:
                saved_path = save_text_draft(Path(save_output_path), final_text)
                self.call_from_thread(
                    self._log_system_message,
                    f"Output saved to: {saved_path}",
                )

                if save_latest_path is not None:
                    latest_path = save_text_draft(Path(save_latest_path), final_text)
                    self.call_from_thread(
                        self._log_system_message,
                        f"Latest output saved to: {latest_path}",
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

    def _submit_prompt(self, user_prompt: str) -> None:
        user_prompt = user_prompt.strip()
        self._clear_prompt()

        if not user_prompt:
            return

        command = parse_interactive_command(user_prompt)

        if command == "exit":
            self.exit()
            return

        if command == "help":
            self._log_blank()
            self._log(build_interactive_help_renderable())
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

        if command in {"triage_servicedesk", "sdp_triage"}:
            limit = parse_triage_limit(user_prompt)
            triage_prompt = build_servicedesk_triage_prompt(limit)

            self._log_user_message(user_prompt)
            self._log_system_message(
                f"Running ServiceDesk triage for up to {limit} requests."
            )
            self._set_running(True)
            self._run_model_turn_worker(triage_prompt)
            return

        if command == "sdp_context":
            request_id = parse_sdp_request_id(user_prompt)

            if request_id is None:
                self._log_blank()
                self._log("Usage: /sdp context <request_id>")
                return

            context_prompt = build_servicedesk_context_prompt(request_id)
            context_path = build_servicedesk_context_path(
                workspace=self.config.workspace,
                request_id=request_id,
            )
            latest_context_path = build_servicedesk_latest_context_path(
                workspace=self.config.workspace,
                request_id=request_id,
            )

            self._log_user_message(user_prompt)
            self._log_system_message(
                f"Preparing ServiceDesk context summary for request {request_id}."
            )
            self._set_running(True)
            self._run_model_turn_worker(
                context_prompt,
                save_output_path=str(context_path),
                save_latest_path=str(latest_context_path),
            )
            return

        if command == "sdp_draft_reply":
            request_id = parse_sdp_request_id(user_prompt)

            if request_id is None:
                self._log_blank()
                self._log("Usage: /sdp draft-reply <request_id>")
                return

            latest_context_path = build_servicedesk_latest_context_path(
                workspace=self.config.workspace,
                request_id=request_id,
            )
            saved_context = read_text_if_exists(latest_context_path)

            draft_prompt = build_servicedesk_draft_reply_prompt(
                request_id,
                saved_context=saved_context,
            )
            draft_path = build_servicedesk_draft_path(
                workspace=self.config.workspace,
                request_id=request_id,
            )
            latest_draft_path = build_servicedesk_latest_draft_path(
                workspace=self.config.workspace,
                request_id=request_id,
            )

            self._log_user_message(user_prompt)

            if saved_context is not None:
                self._log_system_message(
                    f"Drafting ServiceDesk reply for request {request_id} using saved context."
                )
                self._log_system_message(f"Saved context: {latest_context_path}")
            else:
                self._log_system_message(
                    f"Drafting ServiceDesk reply for request {request_id}."
                )
                self._log_system_message("No saved context found; ServiceDesk context may be read.")

            self._set_running(True)
            self._run_model_turn_worker(
                draft_prompt,
                save_output_path=str(draft_path),
                save_latest_path=str(latest_draft_path),
            )
            return

        if command == "sdp_save_draft":
            request_id = parse_sdp_request_id(user_prompt)

            if request_id is None:
                self._log_blank()
                self._log("Usage: /sdp save-draft <request_id>")
                return

            latest_reply_path = build_servicedesk_latest_draft_path(
                workspace=self.config.workspace,
                request_id=request_id,
            )
            latest_reply = read_text_if_exists(latest_reply_path)

            if latest_reply is None:
                self._log_blank()
                self._log(
                    f"No local reply draft found for request {request_id}. "
                    f"Run /sdp draft-reply {request_id} first."
                )
                return

            draft_body = extract_servicedesk_draft_reply(latest_reply)

            if draft_body is None:
                self._log_blank()
                self._log(
                    f"Could not find a ## Draft reply section in {latest_reply_path}."
                )
                return

            if is_no_requester_reply_recommended(draft_body):
                self._log_blank()
                self._log(
                    "Latest local draft says no requester-facing reply is recommended. "
                    "No ServiceDesk draft was created."
                )
                return

            subject = build_servicedesk_draft_subject(request_id)

            self._log_user_message(user_prompt)
            self._log_system_message(
                f"Saving latest local reply as a ServiceDesk draft for request {request_id}."
            )
            self._log_system_message(f"Source: {latest_reply_path}")

            self._set_running(True)
            self._save_servicedesk_draft_worker(
                request_id=request_id,
                subject=subject,
                description=draft_body,
            )
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
                yield PromptTextArea(
                    text="",
                    id="prompt-input",
                    language="markdown",
                    show_line_numbers=False,
                    soft_wrap=True,
                    placeholder=(
                        "Type /help, /status, /clear, or /exit. "
                        "Enter submits, Ctrl+J adds a newline."
                    ),
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

        self.resize_composer()
        self._prompt().focus()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "prompt-input":
            self.resize_composer()

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
                    "[#7f8ea3]Enter[/]           Submit",
                    "[#7f8ea3]Ctrl+J[/]          New line",
                    "[#7f8ea3]Esc[/]             Clear composer",
                    "[#7f8ea3]Ctrl+Q[/]          Quit",
                ]
            )
        )