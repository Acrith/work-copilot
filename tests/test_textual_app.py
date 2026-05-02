# tests/test_textual_app.py

from interactive_session import build_interactive_session_config
from permissions import PermissionContext, PermissionMode, PermissionRuleSet
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

    permission_context = PermissionContext(
        mode=PermissionMode.DEFAULT,
        workspace=str(tmp_path),
        rules=PermissionRuleSet(),
    )

    app = WorkCopilotTextualApp(
        config=config,
        provider_factory=DummyProvider,
        permission_context=permission_context,
    )

    assert app.config is config
    assert app.state.provider.__class__ is DummyProvider
    assert app.permission_context is permission_context
    assert app.is_agent_running is False


def test_textual_app_handles_active_directory_config_error_in_inspect_skill():
    """The /sdp inspect-skill flow must catch ActiveDirectoryInspectorConfigError
    raised by create_configured_inspector_registry_from_env() and log a clear
    AD-specific message instead of letting it bubble up.
    """
    from pathlib import Path

    source = Path("textual_app.py").read_text(encoding="utf-8")

    assert "from inspectors.active_directory_config import (" in source
    assert "ActiveDirectoryInspectorConfigError" in source
    assert "except ActiveDirectoryInspectorConfigError as exc:" in source
    # Adjacent-literal concatenation in the f-string keeps this on one line.
    assert "Active Directory inspector configuration error:" in source


def test_textual_app_logs_real_exchange_and_real_active_directory_separately():
    """Real Exchange and real AD must each have their own log line; the
    mock-only message must only appear when neither selected family will
    actually contact a real backend.
    """
    from pathlib import Path

    source = Path("textual_app.py").read_text(encoding="utf-8")

    # Source uses Python adjacent-string-literal concatenation, so check
    # for the individual literals rather than the joined runtime string.
    assert "Running real Exchange read-only inspector(s). " in source
    assert "External Exchange Online will be contacted when called." in source
    assert "Running real Active Directory read-only inspector(s). " in source
    assert "On-prem AD will be contacted via PowerShell when called." in source

    # Family-aware logging: real-backend log lines are gated on both the
    # selected inspector family AND the configured registry's real-backend
    # flag. This keeps "Exchange Online will be contacted" out of an
    # AD-only run when Exchange is configured real but unselected.
    assert 'inspector_id.startswith("exchange.")' in source
    assert 'inspector_id.startswith("active_directory.")' in source
    assert "real_exchange_will_be_contacted = (" in source
    assert "real_ad_will_be_contacted = (" in source
    assert "selected_includes_exchange" in source
    assert "selected_includes_ad" in source

    # The mock-only branch is now guarded by the family-aware flags.
    assert "not real_exchange_will_be_contacted" in source
    assert "not real_ad_will_be_contacted" in source
    assert "Running mock/registered inspector(s) only. " in source
    assert "No external systems will be contacted." in source
