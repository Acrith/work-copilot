# tests/test_interactive_commands.py

from interactive_commands import (
    build_servicedesk_context_prompt,
    build_servicedesk_draft_reply_prompt,
    build_servicedesk_triage_prompt,
    format_interactive_help,
    format_interactive_status,
    parse_interactive_command,
    parse_sdp_request_id,
    parse_triage_limit,
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
    help_text = "\n".join(lines)

    assert "Commands:" in lines
    assert "/help" in help_text
    assert "Show this help" in help_text
    assert "/status" in help_text
    assert "/clear" in help_text
    assert "/sdp triage <limit>" in help_text
    assert "/sdp draft-reply <id>" in help_text
    assert "/sdp context <id>" in help_text
    assert "/exit" in help_text


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


def test_parse_triage_servicedesk_command():
    assert parse_interactive_command("/triage servicedesk") == "triage_servicedesk"


def test_parse_triage_servicedesk_aliases():
    assert parse_interactive_command("/triage sdp") == "triage_servicedesk"
    assert parse_interactive_command("/triage tickets") == "triage_servicedesk"


def test_parse_sdp_triage_command():
    assert parse_interactive_command("/sdp triage") == "sdp_triage"


def test_parse_sdp_triage_with_limit():
    assert parse_interactive_command("/sdp triage 5") == "sdp_triage"


def test_parse_unknown_triage_target():
    assert parse_interactive_command("/triage coffee") == "unknown"


def test_parse_sdp_unknown_subcommand():
    assert parse_interactive_command("/sdp coffee") == "unknown"


def test_parse_triage_limit_defaults():
    assert parse_triage_limit("/triage servicedesk") == 10
    assert parse_triage_limit("/sdp triage") == 10


def test_parse_triage_limit_caps_maximum():
    assert parse_triage_limit("/triage servicedesk 999") == 20
    assert parse_triage_limit("/sdp triage 999") == 20


def test_parse_triage_limit_reads_sdp_limit():
    assert parse_triage_limit("/sdp triage 7") == 7


def test_build_servicedesk_triage_prompt_is_read_only():
    prompt = build_servicedesk_triage_prompt(5)

    assert "Read up to 5 requests" in prompt
    assert "Use only read-only ServiceDesk tools" in prompt
    assert "Do not update tickets" in prompt
    assert "Do not add notes" in prompt
    assert "Do not send replies" in prompt
    assert "Do not execute commands" in prompt
    assert "Do not download or inspect attachment contents" in prompt


def test_parse_sdp_draft_reply_command():
    assert parse_interactive_command("/sdp draft-reply 55478") == "sdp_draft_reply"


def test_parse_sdp_draft_reply_aliases():
    assert parse_interactive_command("/sdp draft_reply 55478") == "sdp_draft_reply"
    assert parse_interactive_command("/sdp reply 55478") == "sdp_draft_reply"


def test_parse_sdp_request_id():
    assert parse_sdp_request_id("/sdp draft-reply 55478") == "55478"


def test_parse_sdp_request_id_missing():
    assert parse_sdp_request_id("/sdp draft-reply") is None


def test_build_servicedesk_draft_reply_prompt_is_read_only():
    prompt = build_servicedesk_draft_reply_prompt("55478")

    assert "request 55478" in prompt
    assert "Draft reply" in prompt
    assert "Use only read-only ServiceDesk tools" in prompt
    assert "Do not update ServiceDesk" in prompt
    assert "Do not add notes" in prompt
    assert "Do not send replies" in prompt
    assert "Do not execute commands" in prompt
    assert "Do not claim attachment contents were inspected" in prompt


def test_build_servicedesk_draft_reply_prompt_includes_reply_intent_labels():
    prompt = build_servicedesk_draft_reply_prompt("55478")

    assert "Detected reply intent:" in prompt
    assert "Confidence:" in prompt
    assert "Allowed reply_intent labels:" in prompt
    assert "`ask_info`" in prompt
    assert "`confirm_resolution`" in prompt
    assert "`completed`" in prompt
    assert "`follow_up`" in prompt
    assert "`explain_limitation`" in prompt
    assert "`handoff_or_escalate`" in prompt
    assert "`no_reply_needed`" in prompt
    assert "`unclear`" in prompt
    assert "Use one of the allowed labels exactly" in prompt


def test_parse_sdp_context_command():
    assert parse_interactive_command("/sdp context 55478") == "sdp_context"


def test_parse_sdp_context_aliases():
    assert parse_interactive_command("/sdp summary 55478") == "sdp_context"
    assert parse_interactive_command("/sdp summarize 55478") == "sdp_context"


def test_build_servicedesk_context_prompt_is_read_only():
    prompt = build_servicedesk_context_prompt("55478")

    assert "request 55478" in prompt
    assert "ServiceDesk context summary" in prompt
    assert "Use only read-only ServiceDesk tools" in prompt
    assert "Do not update ServiceDesk" in prompt
    assert "Do not add notes" in prompt
    assert "Do not send replies" in prompt
    assert "Do not execute commands" in prompt
    assert "Do not claim attachment contents were inspected" in prompt


def test_build_servicedesk_context_prompt_includes_allowed_labels():
    prompt = build_servicedesk_context_prompt("55478")

    assert "Allowed current_state labels:" in prompt
    assert "`not_yet_processed`" in prompt
    assert "`needs_work`" in prompt
    assert "`waiting_for_requester`" in prompt
    assert "`waiting_for_internal`" in prompt
    assert "`ready_to_close`" in prompt
    assert "`blocked`" in prompt
    assert "`risky_manual`" in prompt
    assert "`unclear`" in prompt

    assert "Allowed reply_intent labels:" in prompt
    assert "`ask_info`" in prompt
    assert "`confirm_resolution`" in prompt
    assert "`completed`" in prompt
    assert "`follow_up`" in prompt
    assert "`explain_limitation`" in prompt
    assert "`handoff_or_escalate`" in prompt
    assert "`no_reply_needed`" in prompt

    assert "Allowed confidence labels:" in prompt
    assert "`low`" in prompt
    assert "`medium`" in prompt
    assert "`high`" in prompt

    assert "Allowed automation_candidate labels:" in prompt
    assert "`partial`" in prompt

    assert "Allowed risk_level labels:" in prompt
    assert "`risky`" in prompt

    assert "Use one of the allowed labels exactly" in prompt