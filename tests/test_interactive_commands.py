# tests/test_interactive_commands.py

from interactive_commands import (
    format_interactive_help,
    format_interactive_status,
    parse_interactive_command,
)
from interactive_session import InteractiveSessionConfig, InteractiveSessionState


def test_parse_interactive_command_returns_none_for_normal_prompt():
    assert parse_interactive_command("Read README.md") is None


def test_parse_interactive_command_handles_exit():
    assert parse_interactive_command("/exit") == "exit"


def test_parse_interactive_command_handles_quit_alias():
    assert parse_interactive_command("/quit") == "exit"


def test_parse_interactive_command_handles_clear():
    assert parse_interactive_command("/clear") == "clear"


def test_parse_interactive_command_handles_help():
    assert parse_interactive_command("/help") == "help"


def test_parse_interactive_command_is_case_insensitive():
    assert parse_interactive_command("/CLEAR") == "clear"


def test_parse_interactive_command_ignores_command_arguments():
    assert parse_interactive_command("/clear now please") == "clear"


def test_parse_interactive_command_handles_unknown_command():
    assert parse_interactive_command("/wat") == "unknown"


def test_parse_interactive_command_handles_status():
    assert parse_interactive_command("/status") == "status"


def test_parse_interactive_command_handles_status_case_insensitive():
    assert parse_interactive_command("/STATUS") == "status"


class DummyProvider:
    pass


def test_format_interactive_help_includes_supported_commands():
    lines = format_interactive_help()

    assert "Commands:" in lines
    assert "  /help    Show this help" in lines
    assert "  /status  Show current session settings" in lines
    assert "  /clear   Reset provider/session state" in lines
    assert "  /exit    Exit interactive mode" in lines


def test_format_interactive_status_includes_session_state(tmp_path):
    config = InteractiveSessionConfig(
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
    state = InteractiveSessionState(
        provider=DummyProvider(),
        interactive_session_id="abc123",
    )

    lines = format_interactive_status(config=config, state=state)

    assert "Interactive session status" in lines
    assert "  Provider:        gemini" in lines
    assert "  Model:           gemini-2.5-flash" in lines
    assert f"  Workspace:       {tmp_path}" in lines
    assert "  Context index:   1" in lines
    assert "  Turn index:      0" in lines


def test_format_interactive_status_includes_log_dir_when_logging_enabled(tmp_path):
    config = InteractiveSessionConfig(
        provider_name="gemini",
        model="gemini-2.5-flash",
        workspace=str(tmp_path),
        permission_mode="default",
        verbose=False,
        verbose_functions=False,
        max_iterations=20,
        log_run=True,
        log_dir="logs",
    )
    state = InteractiveSessionState(
        provider=DummyProvider(),
        interactive_session_id="abc123",
    )

    lines = format_interactive_status(config=config, state=state)

    assert "  Logging:         enabled" in lines
    assert "  Log dir:         logs" in lines