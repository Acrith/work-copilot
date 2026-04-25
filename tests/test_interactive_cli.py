# tests/test_interactive_cli.py
import interactive_cli
from interactive_cli import (
    InteractiveSessionConfig,
    InteractiveSessionState,
    build_interactive_log_dir,
    parse_interactive_command,
    run_interactive_model_turn,
)
from permissions import PermissionContext, PermissionMode, PermissionRuleSet


class DummyProvider:
    pass


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


def test_interactive_session_config_stores_settings(tmp_path):
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

    assert config.provider_name == "gemini"
    assert config.workspace == str(tmp_path)
    assert config.max_iterations == 20


def test_interactive_session_state_defaults():
    state = InteractiveSessionState(
        provider=DummyProvider(),
        interactive_session_id="abc123",
    )

    assert state.interactive_session_id == "abc123"
    assert state.context_index == 1
    assert state.turn_index == 0


def test_build_interactive_log_dir_groups_logs_by_session():
    assert build_interactive_log_dir("logs", "abc123").as_posix() == (
        "logs/interactive/abc123"
    )


def test_run_interactive_model_turn_increments_turn_index(tmp_path, monkeypatch):
    captured = {}

    def fake_run_agent(
        *,
        provider,
        user_prompt,
        workspace,
        permission_context,
        verbose,
        verbose_functions,
        max_iterations,
        run_logger,
    ):
        captured["provider"] = provider
        captured["user_prompt"] = user_prompt
        captured["workspace"] = workspace
        captured["permission_context"] = permission_context
        captured["verbose"] = verbose
        captured["verbose_functions"] = verbose_functions
        captured["max_iterations"] = max_iterations
        captured["run_logger"] = run_logger
        return "done"

    monkeypatch.setattr(interactive_cli, "run_agent", fake_run_agent)

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

    permission_context = PermissionContext(
        mode=PermissionMode.DEFAULT,
        workspace=str(tmp_path),
        rules=PermissionRuleSet(),
    )

    result = run_interactive_model_turn(
        config=config,
        state=state,
        permission_context=permission_context,
        user_prompt="Hello",
    )

    assert result == "done"
    assert state.turn_index == 1
    assert captured["provider"] is state.provider
    assert captured["user_prompt"] == "Hello"
    assert captured["workspace"] == str(tmp_path)
    assert captured["permission_context"] is permission_context
    assert captured["max_iterations"] == 20
    assert captured["run_logger"] is None