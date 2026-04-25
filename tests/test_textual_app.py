# tests/test_textual_app.py

from interactive_session import build_interactive_session_config
from textual_app import WorkCopilotTextualApp


class DummyProvider:
    pass


def test_textual_app_constructs(tmp_path):
    config = build_interactive_session_config(
        provider_name="gemini",
        model="gemini-2.5-flash",
        workspace=str(tmp_path),
        permission_mode="default",
        verbose=False,
        verbose_functions=False,
        max_iterations=20,
        log_run=False,
        log_dir=".work_copilot/runs",
    )

    app = WorkCopilotTextualApp(
        config=config,
        provider_factory=DummyProvider,
    )

    assert app.config is config
    assert app.state.provider.__class__ is DummyProvider