# textual_app.py

from collections.abc import Callable

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, RichLog, Static

from interactive_session import (
    InteractiveSessionConfig,
    create_interactive_session_state,
)
from providers.base import Provider


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
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        *,
        config: InteractiveSessionConfig,
        provider_factory: Callable[[], Provider],
    ) -> None:
        super().__init__()
        self.config = config
        self.provider_factory = provider_factory
        self.state = create_interactive_session_state(provider_factory)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="app-body"):
            yield Static(id="sidebar")

            with Vertical(id="main-area"):
                yield RichLog(id="activity-log", wrap=True)
                yield Input(
                    placeholder="TUI input is visual-only for now. Press q to quit.",
                    id="prompt-input",
                    disabled=True,
                )

        yield Footer()

    def on_mount(self) -> None:
        self.title = "Work Copilot"
        self.sub_title = "Experimental Textual shell"

        self._refresh_sidebar()

        log = self.query_one("#activity-log", RichLog)
        log.write(Text.from_markup("[bold #88c0d0]Work Copilot Textual shell[/]"))
        log.write("")
        log.write(
            Text.from_markup(
                "[#7f8ea3]This TUI layout is now wired, but model turns are not yet enabled here.[/]"
            )
        )
        log.write(
            Text.from_markup(
                "[#7f8ea3]Use the normal interactive CLI for agent execution for now.[/]"
            )
        )
        log.write("")
        log.write(Text.from_markup("[#a3be8c]Ready.[/] Press [bold]q[/] to quit."))

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
                    "[#7f8ea3]q[/]               Quit",
                ]
            )
        )