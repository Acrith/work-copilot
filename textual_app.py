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
    build_servicedesk_draft_note_path,
    build_servicedesk_draft_path,
    build_servicedesk_draft_subject,
    build_servicedesk_latest_context_path,
    build_servicedesk_latest_draft_path,
    build_servicedesk_latest_skill_plan_path,
    build_servicedesk_skill_plan_path,
    extract_servicedesk_draft_reply,
    extract_servicedesk_note_body,
    extract_servicedesk_request_subject,
    is_no_requester_reply_recommended,
    read_text_if_exists,
    save_text_draft,
)
from inspectors.active_directory_config import (
    ActiveDirectoryInspectorConfigError,
)
from inspectors.exchange_config import ExchangeInspectorConfigError
from inspectors.factory import create_configured_inspector_registry_from_env
from inspectors.inspection_report import (
    InspectionReportError,
    InspectionReportNotFoundError,
    build_servicedesk_inspection_report,
    build_servicedesk_inspection_report_path,
)
from inspectors.runner import run_inspector_and_save
from inspectors.skill_plan import (
    SUPPORTED_INSPECTOR_IDS,
    build_inspector_request_from_skill_plan,
    parse_suggested_inspector_tools,
    select_inspectors_for_skill_plan,
)
from interactive_commands import (
    build_interactive_help_renderable,
    build_servicedesk_context_prompt,
    build_servicedesk_draft_note_prompt,
    build_servicedesk_draft_reply_prompt,
    build_servicedesk_skill_plan_prompt,
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
from skills.loader import format_skill_definitions_for_prompt, load_skill_definitions
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

    @work(thread=True)
    def _save_servicedesk_note_worker(
        self,
        *,
        request_id: str,
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
                    name="servicedesk_add_request_note",
                    args={
                        "request_id": request_id,
                        "description": description,
                        "show_to_requester": False,
                    },
                ),
                self.config.workspace,
                self.permission_context,
                approval_handler=approval_handler,
            )

            if "error" in result.payload:
                self.call_from_thread(
                    self._log_system_message,
                    f"Could not save ServiceDesk note: {result.payload['error']}",
                )
                return

            self.call_from_thread(
                self._log_system_message,
                f"ServiceDesk internal note saved for request {request_id}.",
            )
        except Exception as exc:
            self.call_from_thread(
                self._log_system_message,
                f"ServiceDesk note save error: {exc}",
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

            inspection_report_path = build_servicedesk_inspection_report_path(
                workspace=self.config.workspace,
                request_id=request_id,
            )
            saved_inspection_report = read_text_if_exists(inspection_report_path)

            draft_prompt = build_servicedesk_draft_reply_prompt(
                request_id,
                saved_context=saved_context,
                saved_inspection_report=saved_inspection_report,
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

            if saved_inspection_report is not None:
                self._log_system_message(
                    f"Including local inspection report: {inspection_report_path}"
                )

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

            latest_context_path = build_servicedesk_latest_context_path(
                workspace=self.config.workspace,
                request_id=request_id,
            )
            latest_context = read_text_if_exists(latest_context_path)
            original_subject = extract_servicedesk_request_subject(latest_context)
            subject = build_servicedesk_draft_subject(
                request_id,
                original_subject=original_subject,
            )

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

        if command == "sdp_skill_plan":
            request_id = parse_sdp_request_id(user_prompt)

            if request_id is None:
                self._log_blank()
                self._log("Usage: /sdp skill-plan <request_id>")
                return

            latest_context_path = build_servicedesk_latest_context_path(
                workspace=self.config.workspace,
                request_id=request_id,
            )
            saved_context = read_text_if_exists(latest_context_path)

            if saved_context is None:
                self._log_blank()
                self._log(
                    f"No saved context found for request {request_id}. "
                    f"Run /sdp context {request_id} first."
                )
                return

            skills = load_skill_definitions()
            skill_definitions_text = format_skill_definitions_for_prompt(skills)

            skill_plan_prompt = build_servicedesk_skill_plan_prompt(
                request_id=request_id,
                saved_context=saved_context,
                skill_definitions_text=skill_definitions_text,
            )

            skill_plan_path = build_servicedesk_skill_plan_path(
                workspace=self.config.workspace,
                request_id=request_id,
            )
            latest_skill_plan_path = build_servicedesk_latest_skill_plan_path(
                workspace=self.config.workspace,
                request_id=request_id,
            )

            self._log_user_message(user_prompt)
            self._log_system_message(
                f"Preparing read-only skill plan for ServiceDesk request {request_id}."
            )
            self._log_system_message(f"Saved context: {latest_context_path}")

            self._set_running(True)
            self._run_model_turn_worker(
                skill_plan_prompt,
                save_output_path=str(skill_plan_path),
                save_latest_path=str(latest_skill_plan_path),
            )
            return

        if command == "sdp_inspect_skill":
            request_id = parse_sdp_request_id(user_prompt)

            if request_id is None:
                self._log_blank()
                self._log("Usage: /sdp inspect-skill <request_id>")
                return

            latest_skill_plan_path = build_servicedesk_latest_skill_plan_path(
                workspace=self.config.workspace,
                request_id=request_id,
            )
            latest_skill_plan = read_text_if_exists(latest_skill_plan_path)

            if latest_skill_plan is None:
                self._log_blank()
                self._log(
                    f"No local skill plan found for request {request_id}. "
                    f"Run /sdp skill-plan {request_id} first."
                )
                return

            suggested_tools = parse_suggested_inspector_tools(latest_skill_plan)
            selections = select_inspectors_for_skill_plan(latest_skill_plan)

            if not selections:
                self._log_blank()
                supported_list = ", ".join(sorted(SUPPORTED_INSPECTOR_IDS))
                self._log(
                    "No registered inspector found in the latest skill plan. "
                    f"Currently registered inspector(s): {supported_list}."
                )

                if suggested_tools:
                    self._log(f"Suggested inspectors were: {', '.join(suggested_tools)}")
                else:
                    self._log("The skill plan did not suggest any inspector tools.")

                return

            try:
                configured_registry = create_configured_inspector_registry_from_env()
            except ExchangeInspectorConfigError as exc:
                self._log_blank()
                self._log(f"Exchange inspector configuration error: {exc}")
                return
            except ActiveDirectoryInspectorConfigError as exc:
                self._log_blank()
                self._log(f"Active Directory inspector configuration error: {exc}")
                return

            self._log_user_message(user_prompt)

            if configured_registry.uses_real_external_backend:
                self._log_system_message(
                    "Running real Exchange read-only inspector(s). "
                    "External Exchange Online will be contacted when called."
                )

            if configured_registry.uses_real_active_directory_backend:
                self._log_system_message(
                    "Running real Active Directory read-only inspector(s). "
                    "On-prem AD will be contacted via PowerShell when called."
                )

            if (
                not configured_registry.uses_real_external_backend
                and not configured_registry.uses_real_active_directory_backend
            ):
                self._log_system_message(
                    "Running mock/registered inspector(s) only. "
                    "No external systems will be contacted."
                )

            self._log_system_message(
                f"Exchange backend: {configured_registry.exchange_backend.value}"
            )
            self._log_system_message(
                "Active Directory backend: "
                f"{configured_registry.active_directory_backend.value}"
            )
            self._log_system_message(
                "Selected inspectors: "
                + ", ".join(selection.inspector_id for selection in selections)
            )

            for selection in selections:
                inspector_id = selection.inspector_id

                if selection.source == "skill_match":
                    self._log_system_message(
                        "Falling back to Skill match inspector "
                        f"({inspector_id}); no supported inspector was listed "
                        "under Suggested inspector tools."
                    )

                if configured_registry.registry.get(inspector_id) is None:
                    self._log_system_message(
                        f"Inspector {inspector_id} is not registered for the "
                        "current backend; skipping."
                    )
                    continue

                try:
                    inspector_request = build_inspector_request_from_skill_plan(
                        request_id=request_id,
                        skill_plan_text=latest_skill_plan,
                        inspector_id=inspector_id,
                    )
                except ValueError as exc:
                    self._log_system_message(
                        f"Could not build {inspector_id} request: {exc}"
                    )
                    continue

                try:
                    output = run_inspector_and_save(
                        registry=configured_registry.registry,
                        request=inspector_request,
                        workspace=self.config.workspace,
                    )
                except Exception as exc:
                    self._log_system_message(
                        f"Inspector {inspector_id} raised: {exc}"
                    )
                    continue

                self._log_system_message(f"Inspector: {inspector_id}")
                self._log_system_message(
                    f"Result: {output.result.status.value}"
                )
                self._log_system_message(f"Summary: {output.result.summary}")
                self._log_system_message(
                    f"Inspector result saved to: {output.saved_path}"
                )

            return

        if command == "sdp_inspection_report":
            request_id = parse_sdp_request_id(user_prompt)

            if request_id is None:
                self._log_blank()
                self._log("Usage: /sdp inspection-report <request_id>")
                return

            try:
                report_output = build_servicedesk_inspection_report(
                    workspace=self.config.workspace,
                    request_id=request_id,
                )
            except InspectionReportNotFoundError as exc:
                self._log_blank()
                self._log(str(exc))
                return
            except InspectionReportError as exc:
                self._log_blank()
                self._log(f"Could not build inspection report: {exc}")
                return

            self._log_user_message(user_prompt)
            self._log_system_message(
                f"Built local inspection report for request {request_id}."
            )
            self._log_system_message(
                f"Source inspector JSON: {report_output.source_json_path}"
            )
            self._log_system_message(
                f"Inspection report saved to: {report_output.report_path}"
            )
            self._log_system_message(
                "No ServiceDesk update was performed. Report is local-only."
            )
            return

        if command == "sdp_draft_note":
            request_id = parse_sdp_request_id(user_prompt)

            if request_id is None:
                self._log_blank()
                self._log("Usage: /sdp draft-note <request_id>")
                return

            latest_context_path = build_servicedesk_latest_context_path(
                workspace=self.config.workspace,
                request_id=request_id,
            )
            saved_context = read_text_if_exists(latest_context_path)

            inspection_report_path = build_servicedesk_inspection_report_path(
                workspace=self.config.workspace,
                request_id=request_id,
            )
            saved_inspection_report = read_text_if_exists(inspection_report_path)

            note_prompt = build_servicedesk_draft_note_prompt(
                request_id,
                saved_context=saved_context,
                saved_inspection_report=saved_inspection_report,
            )

            note_path = build_servicedesk_draft_note_path(
                workspace=self.config.workspace,
                request_id=request_id,
            )

            self._log_user_message(user_prompt)
            self._log_system_message(
                f"Drafting local internal note for ServiceDesk request {request_id}."
            )

            if saved_context is not None:
                self._log_system_message(f"Saved context: {latest_context_path}")
            else:
                self._log_system_message(
                    "No saved context found; ServiceDesk context may be read."
                )

            if saved_inspection_report is not None:
                self._log_system_message(
                    f"Including local inspection report: {inspection_report_path}"
                )
            else:
                self._log_system_message(
                    "No local inspection report found. "
                    f"Run /sdp inspection-report {request_id} for richer findings."
                )

            self._log_system_message(
                "Note is local-only. It will not be posted to ServiceDesk."
            )

            self._set_running(True)
            self._run_model_turn_worker(
                note_prompt,
                save_output_path=str(note_path),
                save_latest_path=str(note_path),
            )
            return

        if command == "sdp_save_note":
            request_id = parse_sdp_request_id(user_prompt)

            if request_id is None:
                self._log_blank()
                self._log("Usage: /sdp save-note <request_id>")
                return

            note_path = build_servicedesk_draft_note_path(
                workspace=self.config.workspace,
                request_id=request_id,
            )
            note_text = read_text_if_exists(note_path)

            if note_text is None:
                self._log_blank()
                self._log(
                    f"No local note draft found for request {request_id}. "
                    f"Run /sdp draft-note {request_id} first."
                )
                return

            note_body = extract_servicedesk_note_body(note_text)

            if note_body is None:
                self._log_blank()
                self._log(
                    f"Could not find a ## Note body section in {note_path}. "
                    "Note was not posted."
                )
                return

            if not note_body.strip():
                self._log_blank()
                self._log(
                    f"## Note body section is empty in {note_path}. "
                    "Note was not posted."
                )
                return

            self._log_user_message(user_prompt)
            self._log_system_message(
                f"Saving local note draft as an internal ServiceDesk note for "
                f"request {request_id}."
            )
            self._log_system_message(f"Source: {note_path}")
            self._log_system_message(
                "Local draft metadata will not be posted; only the Note body section."
            )

            self._set_running(True)
            self._save_servicedesk_note_worker(
                request_id=request_id,
                description=note_body,
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
