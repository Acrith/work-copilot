# textual_app.py

from collections.abc import Callable

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, RichLog, Static

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


    def _run_model_turn(self, user_prompt: str) -> None:
        log = self.query_one("#activity-log", RichLog)
        event_sink = TextualEventSink(log)

        final_text = run_interactive_model_turn(
            config=self.config,
            state=self.state,
            permission_context=self.permission_context,
            user_prompt=user_prompt,
            extra_event_sinks=[event_sink],
            terminal_output=False,
        )

        self._refresh_sidebar()

        if final_text is None:
            self._log_system_message(
                "Turn ended without a final response. You can continue or use /clear."
            )


    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_prompt = event.value.strip()
        self._clear_prompt()

        if not user_prompt:
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
        self._run_model_turn(user_prompt)


    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="app-body"):
            yield Static(id="sidebar")

            with Vertical(id="main-area"):
                yield RichLog(id="activity-log", wrap=True)
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
            "This TUI layout is now wired, but model turns are not yet enabled here."
        )
        self._log_system_message(
            "Use the normal interactive CLI for agent execution for now."
        )
        self._log_blank()
        self._log_markup(
           "[#a3be8c]Ready.[/] Type [bold]/exit[/] or press [bold]Ctrl+Q[/] to quit."
        )

        self.query_one("#prompt-input", Input).focus()

    def _refresh_sidebar(self) -> None:
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
                    f"[#7f8ea3]Session id[/]      {self.state.interactive_session_id}",
                    f"[#7f8ea3]Context index[/]   {self.state.context_index}",
                    f"[#7f8ea3]Turn index[/]      {self.state.turn_index}",
                    "",
                    "[bold #88c0d0]Controls[/]",
                    "[#7f8ea3]Ctrl+Q[/]          Quit",
                ]
            )
        )