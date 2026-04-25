# tests/test_interactive_session.py

import interactive_session
from interactive_session import (
    InteractiveSessionConfig,
    InteractiveSessionState,
    build_interactive_log_dir,
    build_interactive_session_config,
    create_interactive_session_state,
    reset_interactive_context,
    run_interactive_model_turn,
)
from permissions import PermissionContext, PermissionMode, PermissionRuleSet


class DummyProvider:
    pass


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
        extra_event_sinks,
        terminal_output,
        approval_handler,
    ):
        captured["provider"] = provider
        captured["user_prompt"] = user_prompt
        captured["workspace"] = workspace
        captured["permission_context"] = permission_context
        captured["verbose"] = verbose
        captured["verbose_functions"] = verbose_functions
        captured["max_iterations"] = max_iterations
        captured["run_logger"] = run_logger
        captured["extra_event_sinks"] = extra_event_sinks
        captured["terminal_output"] = terminal_output
        captured["approval_handler"] = approval_handler
        return "done"

    monkeypatch.setattr(interactive_session, "run_agent", fake_run_agent)

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
    assert captured["extra_event_sinks"] is None
    assert captured["terminal_output"] is True
    assert captured["approval_handler"] is None


def test_build_interactive_session_config_stores_settings(tmp_path):
    config = build_interactive_session_config(
        provider_name="gemini",
        model="gemini-2.5-flash",
        workspace=str(tmp_path),
        permission_mode="default",
        verbose=True,
        verbose_functions=False,
        max_iterations=25,
        log_run=True,
        log_dir="logs",
    )

    assert config.provider_name == "gemini"
    assert config.model == "gemini-2.5-flash"
    assert config.workspace == str(tmp_path)
    assert config.permission_mode == "default"
    assert config.verbose is True
    assert config.verbose_functions is False
    assert config.max_iterations == 25
    assert config.log_run is True
    assert config.log_dir == "logs"


def test_create_interactive_session_state_uses_provider_factory():
    provider = DummyProvider()

    def provider_factory():
        return provider

    state = create_interactive_session_state(provider_factory)

    assert state.provider is provider
    assert state.interactive_session_id
    assert state.context_index == 1
    assert state.turn_index == 0


def test_reset_interactive_context_replaces_provider_and_increments_context():
    old_provider = DummyProvider()
    new_provider = DummyProvider()

    state = InteractiveSessionState(
        provider=old_provider,
        interactive_session_id="abc123",
    )

    def provider_factory():
        return new_provider

    reset_interactive_context(
        state=state,
        provider_factory=provider_factory,
    )

    assert state.provider is new_provider
    assert state.context_index == 2
    assert state.turn_index == 0


def test_run_interactive_model_turn_passes_extra_event_sinks(tmp_path, monkeypatch):
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
        extra_event_sinks,
        terminal_output,
        approval_handler,
    ):
        captured["extra_event_sinks"] = extra_event_sinks
        captured["terminal_output"] = terminal_output
        return "done"

    monkeypatch.setattr(interactive_session, "run_agent", fake_run_agent)

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

    extra_sinks = []

    result = run_interactive_model_turn(
        config=config,
        state=state,
        permission_context=permission_context,
        user_prompt="Hello",
        extra_event_sinks=extra_sinks,
    )

    assert result == "done"
    assert captured["extra_event_sinks"] is extra_sinks
    assert captured["terminal_output"] is True