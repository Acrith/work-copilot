# tests/test_interactive_commands.py

from interactive_commands import (
    build_servicedesk_context_prompt,
    build_servicedesk_draft_note_prompt,
    build_servicedesk_draft_reply_prompt,
    build_servicedesk_skill_plan_prompt,
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
    assert "/sdp save-draft <id>" in help_text
    assert "/sdp inspect-skill" in help_text
    assert "/sdp inspection-report" in help_text
    assert "/sdp draft-note" in help_text
    assert "/sdp save-note" in help_text
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


def test_build_servicedesk_draft_reply_prompt_includes_reply_decision_labels():
    prompt = build_servicedesk_draft_reply_prompt("55478")

    assert "Reply recommended:" in prompt
    assert "Detected reply intent:" in prompt
    assert "Allowed reply_recommended labels:" in prompt
    assert "Allowed reply_intent labels:" in prompt
    assert "`no_reply_recommended`" in prompt
    assert "No requester-facing reply recommended at this time." in prompt
    assert "do not force a follow-up message" in prompt


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

    assert "Allowed reply_recommended labels:" in prompt
    assert "`yes`" in prompt
    assert "`no`" in prompt

    assert "Allowed reply_intent labels:" in prompt
    assert "`ask_info`" in prompt
    assert "`confirm_resolution`" in prompt
    assert "`completed`" in prompt
    assert "`follow_up`" in prompt
    assert "`explain_limitation`" in prompt
    assert "`handoff_or_escalate`" in prompt
    assert "`no_reply_recommended`" in prompt

    assert "Use one of the allowed labels exactly" in prompt


def test_build_servicedesk_context_prompt_includes_chronology_rules():
    prompt = build_servicedesk_context_prompt("55853")

    assert "Analyze the ticket chronologically" in prompt
    assert "Do not list information as missing if a later conversation entry" in prompt
    assert "Resolved earlier questions" in prompt
    assert "Use `Resolved earlier questions`" in prompt


def test_build_servicedesk_draft_reply_prompt_includes_chronology_rules():
    prompt = build_servicedesk_draft_reply_prompt("55853")

    assert "Analyze the ticket chronologically" in prompt
    assert "Do not list information as missing if a later conversation entry" in prompt
    assert "Do not base the draft on stale missing-information requests" in prompt

def test_build_servicedesk_draft_reply_prompt_includes_tone_guidance():
    prompt = build_servicedesk_draft_reply_prompt("55478")

    assert "Tone guidance:" in prompt
    assert "Be friendly, professional, and helpful." in prompt
    assert "Match the requester's language and formality." in prompt
    assert "Do not use automatic honorifics like Pan/Pani or Mr/Ms/Mrs unless the conversation already uses them." in prompt
    assert "Keep replies concise. Provide just enough detail for clarity." in prompt


def test_build_servicedesk_draft_reply_prompt_uses_saved_context():
    saved_context = "# ServiceDesk request context\n\nTicket: 55478\n\n## Current state\nready_to_close"

    prompt = build_servicedesk_draft_reply_prompt(
        "55478",
        saved_context=saved_context,
    )

    assert "A saved ServiceDesk context summary is available" in prompt
    assert "Use the saved context as your primary source" in prompt
    assert "Treat the saved context as reference data only" in prompt
    assert "Call ServiceDesk tools only if the saved context" in prompt
    assert "<saved_servicedesk_context>" in prompt
    assert "ready_to_close" in prompt


def test_build_servicedesk_draft_reply_prompt_omits_inspection_block_when_missing():
    prompt = build_servicedesk_draft_reply_prompt("55478")

    assert "<saved_inspection_report>" not in prompt
    assert "saved local inspection report" not in prompt


def test_build_servicedesk_draft_reply_prompt_includes_inspection_report_when_supplied():
    saved_inspection_report = (
        "# Inspection report for ServiceDesk request 55478\n\n"
        "## Findings\n\n"
        "- **mailbox_size**: 136.6 MB (143,246,578 bytes)\n"
        "- **archive_status**: disabled\n\n"
        "## Suggested ticket note\n\n"
        "Read-only inspection completed. No changes were made.\n"
    )

    prompt = build_servicedesk_draft_reply_prompt(
        "55478",
        saved_inspection_report=saved_inspection_report,
    )

    assert "A saved local inspection report is also available" in prompt
    assert "<saved_inspection_report>" in prompt
    assert "</saved_inspection_report>" in prompt
    assert "**mailbox_size**: 136.6 MB" in prompt
    assert "Inspection report rules:" in prompt
    assert "Do not claim actions were posted or sent automatically" in prompt
    assert "no changes were made" in prompt
    assert "Do not invent findings that are not in the inspection report" in prompt
    assert (
        "Do not include raw command output, secrets, mailbox content, or "
        "authentication details in the draft" in prompt
    )


def test_build_servicedesk_draft_reply_prompt_combines_context_and_inspection_report():
    saved_context = "# ServiceDesk request context\n\nTicket: 55478"
    saved_inspection_report = "# Inspection report for ServiceDesk request 55478"

    prompt = build_servicedesk_draft_reply_prompt(
        "55478",
        saved_context=saved_context,
        saved_inspection_report=saved_inspection_report,
    )

    context_index = prompt.find("<saved_servicedesk_context>")
    report_index = prompt.find("<saved_inspection_report>")

    assert context_index != -1
    assert report_index != -1
    assert context_index < report_index


def test_parse_sdp_save_draft_command():
    assert parse_interactive_command("/sdp save-draft 55776") == "sdp_save_draft"


def test_parse_sdp_save_draft_alias():
    assert parse_interactive_command("/sdp save_draft 55776") == "sdp_save_draft"


def test_parse_sdp_skill_plan_command():
    assert parse_interactive_command("/sdp skill-plan 55853") == "sdp_skill_plan"


def test_build_servicedesk_skill_plan_prompt_contains_read_only_rules():
    prompt = build_servicedesk_skill_plan_prompt(
        request_id="55853",
        saved_context="# ServiceDesk request context\n\nExample context",
        skill_definitions_text="## active_directory.create_user\n\nExample skill",
    )

    assert "Prepare a read-only skill plan" in prompt
    assert "Skills represent the operational work to do, not ServiceDesk tools" in prompt
    assert "active_directory.create_user" in prompt
    assert "Do not execute commands" in prompt
    assert "Do not modify ServiceDesk" in prompt
    assert "Do not call connector-write tools" in prompt


def test_build_servicedesk_skill_plan_prompt_distinguishes_current_issue_from_history():
    prompt = build_servicedesk_skill_plan_prompt(
        request_id="55853",
        saved_context="# ServiceDesk request context\n\nExample context",
        skill_definitions_text="## active_directory.create_user\n\nExample skill",
    )

    assert "Distinguish the original work type from the current unresolved issue" in prompt
    assert "Skill relevance" in prompt
    assert "primary/secondary/historical/no_match" in prompt
    assert "Work status" in prompt
    assert "Current unresolved issue" in prompt
    assert "Missing information needed now" in prompt
    assert "not_needed_now" in prompt
    assert "Do not ask the requester for missing skill information unless it is needed" in prompt


def test_build_servicedesk_skill_plan_prompt_lists_active_directory_inspector_ids():
    prompt = build_servicedesk_skill_plan_prompt(
        request_id="55853",
        saved_context="# ServiceDesk request context\n\nExample context",
        skill_definitions_text="## active_directory.user.inspect\n\nExample skill",
    )

    assert "Suggested inspector tools" in prompt
    assert "`exchange.mailbox.inspect`" in prompt
    assert "`active_directory.user.inspect`" in prompt
    assert "`active_directory.group.inspect`" in prompt
    assert "`active_directory.group_membership.inspect`" in prompt
    assert "do not invent granular" in prompt.lower()


def test_build_servicedesk_skill_plan_prompt_separates_requester_from_target_identity():
    prompt = build_servicedesk_skill_plan_prompt(
        request_id="55853",
        saved_context="# ServiceDesk request context\n\nExample context",
        skill_definitions_text="## active_directory.user.inspect\n\nExample skill",
    )

    assert "Requester-vs-target rules:" in prompt
    # Forbid using requester metadata as the inspection target by default.
    assert "Do not use the ServiceDesk requester's name or email" in prompt
    assert "`target_user`" in prompt
    assert "`target_user_email`" in prompt
    assert "`mailbox_address`" in prompt
    assert "`target_group`" in prompt
    assert (
        "unless the request body explicitly says the requester is the "
        "account/mailbox/group" in prompt
    )

    # Prefer body-mentioned identifiers over requester metadata.
    assert (
        "Prefer identifiers that appear in the request body or "
        "conversation content over identifiers from requester metadata"
        in prompt
    )

    # Per-family identity guidance: AD prefers account-like, Exchange
    # keeps mailbox/email semantics.
    assert (
        "For Active Directory inspectors, prefer explicit account-like "
        "values mentioned in the request body" in prompt
    )
    assert "`sam_account_name`" in prompt
    assert "`distinguished_name`" in prompt
    assert (
        "For Exchange mailbox inspectors, mailbox/email identifiers"
        in prompt
    )


def test_build_servicedesk_skill_plan_prompt_requires_inspector_input_extraction_on_no_match():
    prompt = build_servicedesk_skill_plan_prompt(
        request_id="55853",
        saved_context="# ServiceDesk request context\n\nExample context",
        skill_definitions_text="## active_directory.user.inspect\n\nExample skill",
    )

    assert "Inspector input extraction rules:" in prompt
    # Must call out the no_match / inspection-only case explicitly.
    assert "`Skill match` is `none`" in prompt
    assert "`no_match`" in prompt
    assert "Do not write `- none` under `Extracted inputs`" in prompt
    # Per-inspector required-input fields must be enumerated.
    assert "`active_directory.user.inspect` requires one user identifier" in prompt
    assert "`target_user`" in prompt
    assert "`user_principal_name`" in prompt
    assert "`sam_account_name`" in prompt
    assert "`active_directory.group.inspect` requires one group identifier" in prompt
    assert "`target_group`" in prompt
    assert "`group_name`" in prompt
    assert (
        "`active_directory.group_membership.inspect` requires BOTH a user "
        "identifier" in prompt
    )
    assert "`exchange.mailbox.inspect` requires `mailbox_address`" in prompt
    assert "Multiple inspector IDs may be listed" in prompt
    assert "Do not invent identifier values." in prompt


def test_parse_sdp_inspect_skill_command():
    assert parse_interactive_command("/sdp inspect-skill 55948") == "sdp_inspect_skill"


def test_parse_sdp_inspection_report_command():
    assert (
        parse_interactive_command("/sdp inspection-report 55948")
        == "sdp_inspection_report"
    )


def test_parse_sdp_inspection_report_underscore_alias():
    assert (
        parse_interactive_command("/sdp inspection_report 55948")
        == "sdp_inspection_report"
    )


def test_parse_sdp_draft_note_command():
    assert parse_interactive_command("/sdp draft-note 55948") == "sdp_draft_note"


def test_parse_sdp_draft_note_underscore_alias():
    assert parse_interactive_command("/sdp draft_note 55948") == "sdp_draft_note"


def test_parse_sdp_note_short_alias():
    assert parse_interactive_command("/sdp note 55948") == "sdp_draft_note"


def test_parse_sdp_save_note_command():
    assert parse_interactive_command("/sdp save-note 55948") == "sdp_save_note"


def test_parse_sdp_save_note_underscore_alias():
    assert parse_interactive_command("/sdp save_note 55948") == "sdp_save_note"


def test_build_servicedesk_draft_note_prompt_is_internal_and_local_only():
    prompt = build_servicedesk_draft_note_prompt("55948")

    assert "internal technician note draft" in prompt
    assert (
        "internal technician work-log entry, not a requester-facing reply"
        in prompt
    )
    assert "ServiceDesk internal note draft" in prompt
    assert "Ticket: 55948" in prompt
    assert "Note type: internal technician note" in prompt
    # The "local-only draft" parenthetical must NOT appear in the title — it
    # belongs only in the Local draft metadata section.
    assert "Note type: internal technician note (local-only draft)" not in prompt
    # Must explicitly forbid claims that the note was posted/sent.
    assert (
        "Do not claim the note was posted, sent, or saved to ServiceDesk." in prompt
    )
    # Read-only + chronology rules from the shared blocks must be present.
    assert "Use only read-only ServiceDesk tools." in prompt
    assert "Analyze the ticket chronologically" in prompt


def test_build_servicedesk_draft_note_prompt_separates_note_body_from_metadata():
    prompt = build_servicedesk_draft_note_prompt("55948")

    # The structure must split postable content from local metadata so a
    # future /sdp save-note step can post only the Note body section.
    assert "## Note body" in prompt
    assert "## Local draft metadata" in prompt

    body_index = prompt.find("## Note body")
    metadata_index = prompt.find("## Local draft metadata")

    assert body_index != -1
    assert metadata_index != -1
    assert body_index < metadata_index

    # Local-draft commentary must be confined to the metadata section, not
    # echoed inside the Note body.
    assert "Generated locally by Work Copilot." in prompt
    assert "Not posted to ServiceDesk yet." in prompt
    assert "Source files used:" in prompt
    assert (
        "do not put local-draft commentary inside it" in prompt
        or "do not say 'local-only draft'" in prompt.lower()
    )

    # A future /sdp save-note workflow should be reflected in the prompt.
    assert "/sdp save-note" in prompt


def test_build_servicedesk_draft_note_prompt_requires_neutral_operational_body():
    prompt = build_servicedesk_draft_note_prompt("55948")

    # The Note body must be neutral, concise, operational, and free of
    # filler review steps.
    assert "neutral, concise, and operational" in prompt
    assert "Operational tone." in prompt
    assert "Review the inspection findings" in prompt  # explicitly forbidden filler
    assert "Confirm no changes should be made" in prompt  # explicitly forbidden filler
    assert (
        "If there is no real follow-up, omit the `Follow-up:` section entirely."
        in prompt
    )
    assert "No changes were made." in prompt
    assert "Mailbox content and attachments were not inspected." in prompt
    # Greetings/sign-offs are forbidden because this is technician-facing.
    assert "No greetings, sign-offs, or signatures." in prompt


def test_build_servicedesk_draft_note_prompt_requires_structured_note_body():
    prompt = build_servicedesk_draft_note_prompt("55948")

    # The Note body shape must be explicitly required: opening sentence,
    # Findings, optional Assessment, Scope, optional Follow-up.
    assert "Required Note body shape" in prompt
    assert "One opening sentence stating what was inspected" in prompt
    assert "`Findings:` label followed by a Markdown bullet list" in prompt
    assert "`Assessment:` label followed by a Markdown bullet list" in prompt
    assert "`Scope:` label followed by a Markdown bullet list" in prompt
    assert "`Follow-up:` label followed by a Markdown bullet list" in prompt

    # Assessment must come before Scope, and Scope must come before Follow-up.
    findings_index = prompt.find("`Findings:` label")
    assessment_index = prompt.find("`Assessment:` label")
    scope_index = prompt.find("`Scope:` label")
    followup_index = prompt.find("`Follow-up:` label")

    assert findings_index < assessment_index < scope_index < followup_index

    # One fact per bullet, no stacking.
    assert "One fact per bullet under `Findings:`." in prompt
    assert (
        "Do not stack multiple facts into one bullet or one paragraph." in prompt
    )

    # The illustrative example must reflect the desired technician-note
    # shape, including an Assessment block sourced from inspector
    # recommendations.
    assert (
        "Read-only mailbox inspection completed for `user@example.com`." in prompt
    )
    assert "Findings:\n- Mailbox exists: yes" in prompt
    assert "- Display name: Example User" in prompt
    assert "- Recipient type: UserMailbox" in prompt
    assert "- Mailbox size: 136.7 MB" in prompt
    assert "- Item count: 1210" in prompt
    assert "Assessment:\n- No archive-readiness recommendation was generated." in prompt
    assert "Scope:\n- No changes were made." in prompt
    assert "- Mailbox content and attachments were not inspected." in prompt


def test_build_servicedesk_draft_note_prompt_mentions_largest_folders_evidence():
    prompt = build_servicedesk_draft_note_prompt("55948")

    # Draft-note must allow technician-facing summarization of the bounded
    # folder evidence when the inspection report contains it, but must not
    # include item-level content.
    assert "### Largest folders" in prompt
    assert "1-3 indented sub-bullets" in prompt
    assert "Largest folders:" in prompt
    assert (
        "Do not include subjects, message bodies, attachment names, "
        "or any item-level content." in prompt
    )


def test_build_servicedesk_draft_note_prompt_separates_assessment_from_followup():
    prompt = build_servicedesk_draft_note_prompt("55948")

    # Follow-up is reserved for concrete operational actions, not
    # assessments or fallback recommendation text.
    assert (
        "`Follow-up:` is reserved for concrete operational next actions."
        in prompt
    )
    assert (
        "Do not put recommendation/fallback text such as `No archive-"
        "readiness recommendation was generated...` under `Follow-up:`."
        in prompt
    )
    assert "That text belongs under `Assessment:`." in prompt

    # Filler follow-ups stay forbidden, including the archive-readiness
    # fallback wording.
    assert (
        "Do not include filler follow-ups such as `Review "
        "the inspection findings`, `Confirm no changes should be made`, or "
        "`No archive-readiness recommendation was generated...`." in prompt
    )


def test_build_servicedesk_draft_note_prompt_uses_inspection_report_when_present():
    saved_inspection_report = (
        "# Inspection report for ServiceDesk request 55948\n\n"
        "## Findings\n\n"
        "- **mailbox_size**: 136.6 MB\n"
        "- **archive_status**: disabled\n\n"
        "## Suggested ticket note\n\n"
        "Read-only inspection completed. No changes were made.\n"
    )

    prompt = build_servicedesk_draft_note_prompt(
        "55948",
        saved_inspection_report=saved_inspection_report,
    )

    assert "<saved_inspection_report>" in prompt
    assert "</saved_inspection_report>" in prompt
    assert "**mailbox_size**: 136.6 MB" in prompt
    assert "Inspection report rules:" in prompt
    assert (
        "Do not claim actions were posted, sent, or applied automatically." in prompt
    )
    assert "If the inspection report indicates no changes were made" in prompt
    assert "Inspection report used: <yes/no>" in prompt


def test_build_servicedesk_draft_note_prompt_suggests_running_inspection_when_missing():
    prompt = build_servicedesk_draft_note_prompt("55948")

    assert "<saved_inspection_report>" not in prompt
    assert "No saved inspection report is available" in prompt
    assert "/sdp inspection-report 55948" in prompt
    assert "Do not invent technical findings." in prompt


def test_build_servicedesk_draft_note_prompt_combines_context_and_inspection():
    saved_context = "# ServiceDesk request context\n\nTicket: 55948"
    saved_inspection_report = "# Inspection report for ServiceDesk request 55948"

    prompt = build_servicedesk_draft_note_prompt(
        "55948",
        saved_context=saved_context,
        saved_inspection_report=saved_inspection_report,
    )

    context_index = prompt.find("<saved_servicedesk_context>")
    report_index = prompt.find("<saved_inspection_report>")

    assert context_index != -1
    assert report_index != -1
    assert context_index < report_index


def test_build_servicedesk_draft_note_prompt_forbids_secret_and_content_leakage():
    prompt = build_servicedesk_draft_note_prompt("55948")

    forbidden_lines = [
        "secrets",
        "authentication config",
        "certificate paths",
        "thumbprints",
        "tenant identifiers",
        "raw PowerShell transcripts",
        "mailbox content",
        "message subjects/bodies",
        "attachments",
    ]

    for token in forbidden_lines:
        assert token in prompt, f"Prompt missing safety mention: {token}"
