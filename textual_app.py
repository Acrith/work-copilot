# textual_app.py

from collections.abc import Callable

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, RichLog

from interactive_session import (
    InteractiveSessionConfig,
    create_interactive_session_state,
)
from providers.base import Provider


class WorkCopilotTextualApp(App):
    """Experimental Textual shell for Work Copilot."""

    CSS = """
    RichLog {
        height: 1fr;
        border: solid $primary;
        padding: 1;
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
        yield RichLog(id="main-log", wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#main-log", RichLog)
        log.write("Work Copilot Textual shell")
        log.write("")
        log.write(f"Provider:        {self.config.provider_name}")
        log.write(f"Model:           {self.config.model}")
        log.write(f"Workspace:       {self.config.workspace}")
        log.write(f"Permission mode: {self.config.permission_mode}")
        log.write(f"Max iterations:  {self.config.max_iterations}")
        log.write(f"Logging:         {'enabled' if self.config.log_run else 'disabled'}")
        log.write("")
        log.write("Model turns are not wired in this TUI yet.")
        log.write("Press q to quit.")