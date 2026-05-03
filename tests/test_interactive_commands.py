# tests/test_interactive_commands.py

from interactive_commands import (
    build_servicedesk_context_prompt,
    build_servicedesk_draft_note_prompt,
    build_servicedesk_draft_reply_prompt,
    build_servicedesk_skill_plan_prompt,
    build_servicedesk_skill_plan_repair_prompt,
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
    assert "/sdp repair-skill-plan" in help_text
    assert "/sdp status <id>" in help_text
    assert "/sdp work <id>" in help_text
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


def test_build_servicedesk_skill_plan_prompt_requires_clean_identifier_values_for_inspector_inputs():
    prompt = build_servicedesk_skill_plan_prompt(
        request_id="60020",
        saved_context=(
            "# ServiceDesk request context\n\n"
            "Surname change for Agata Piątek (agata.piatek@example.com).\n"
        ),
        skill_definitions_text="## active_directory.user.update_attributes\n",
    )

    # The clean-identifier rule block must be present and explicitly
    # bound to the inspector-bound input fields the request builders
    # consume.
    assert "Clean identifier rule for inspector-bound" in prompt
    for inspector_field in (
        "`target_user`",
        "`target_user_email`",
        "`user_principal_name`",
        "`sam_account_name`",
        "`mailbox_address`",
        "`target_group`",
        "`group_name`",
    ):
        assert inspector_field in prompt

    # Explicit ban on wrapping identifiers with display names, labels,
    # parentheses, prefixes, or trailing notes.
    assert (
        "MUST be clean machine identifiers only" in prompt
    )
    assert (
        "Do not wrap identifiers with display names, labels, comments, "
        "parentheses, surrounding quotes, prefixes like `user:` / "
        "`mailbox:` / `group:`, or trailing notes." in prompt
    )

    # Good and bad examples that the smoke test discovered must both be
    # present so the model has them as anchors.
    assert "Good: `agata.piatek@exactforestall.com`" in prompt
    assert "Good: `agata.piatek`" in prompt
    assert "Bad: `Agata Piątek (agata.piatek@exactforestall.com)`" in prompt
    assert "Bad: `user: agata.piatek@exactforestall.com`" in prompt

    # Human-readable display-name + email combinations must land in
    # identity_confirmation or evidence, never in inspector-bound value
    # fields.
    assert "`identity_confirmation`" in prompt
    assert "or into the `evidence:` line of the inspector-bound bullet" in prompt
    assert "never into" in prompt
    for forbidden_landing_field in (
        "`target_user`",
        "`target_user_email`",
        "`mailbox_address`",
        "`target_group`",
        "`group_name`",
    ):
        assert forbidden_landing_field in prompt

    # Requester-vs-target / per-system preferences still apply.
    assert "for AD, prefer SAM/account-style identifiers" in prompt
    assert (
        "for Exchange, mailbox/email identifiers remain expected." in prompt
    )


def test_build_servicedesk_skill_plan_prompt_distinguishes_ad_lookup_vs_canonical_modification_identifiers():
    prompt = build_servicedesk_skill_plan_prompt(
        request_id="60030",
        saved_context=(
            "# ServiceDesk request context\n\n"
            "Please update surname for agata.piatek@example.com.\n"
        ),
        skill_definitions_text=(
            "## active_directory.user.update_profile_attributes\n"
        ),
    )

    assert (
        "Active Directory lookup vs canonical-modification identifier "
        "rules:" in prompt
    )

    # Lookup vs canonical-modification distinction is named and the two
    # canonical AD modification identifiers are explicit.
    assert "AD lookup identifiers used to *find* the right AD object" in prompt
    assert (
        "AD canonical modification identifiers used to *modify* the "
        "right AD object: `sam_account_name` and `distinguished_name`"
        in prompt
    )
    assert "`target_user_email`" in prompt
    assert "`user_principal_name`" in prompt
    assert (
        "valid inputs to `active_directory.user.inspect`" in prompt
    )

    # Read-only AD inspection-only requests still allow target_user as a
    # clean SAM/account-style identifier.
    assert (
        "For read-only AD inspection-only requests" in prompt
    )
    assert (
        "`target_user` may still be a clean SAM/account-style "
        "identifier when the request body provides one directly." in prompt
    )

    # Write-shaped / manual-update AD skills must follow the lookup-then-
    # canonical-target flow.
    assert (
        "For Active Directory write-shaped or manual-update skills "
        in prompt
    )
    assert "`active_directory.user.update_profile_attributes`" in prompt

    # Email/UPN must be extracted as target_user_email / user_principal_name
    # — not as target_user — when the AD target is a modification skill.
    assert (
        "If only an email or UPN is available in the request, extract "
        "it as `target_user_email` or `user_principal_name`, NOT as "
        "`target_user`." in prompt
    )

    # sam_account_name / distinguished_name should be marked missing and
    # surfaced in Missing information needed now when not directly given.
    assert (
        "list them as separate `Extracted inputs` bullets with "
        "`status: missing` and `needed_now: yes`" in prompt
    )
    assert (
        "call them out under `Missing information needed now`" in prompt
    )

    # Suggest active_directory.user.inspect when enough lookup info is
    # present, so the inspector resolves the canonical AD identifiers.
    assert (
        "suggest `active_directory.user.inspect` under `Suggested "
        "inspector tools` so the inspector resolves the canonical "
        "`sam_account_name` / `distinguished_name`." in prompt
    )

    # Internal work plan / Proposed next action must require using the
    # inspector result's canonical identifier before any manual ADUC
    # change.
    assert (
        "`Internal work plan` and `Proposed next action` MUST direct "
        "the technician to use the inspector result's "
        "`sam_account_name` / `distinguished_name` as the canonical AD "
        "target before any manual ADUC update." in prompt
    )


def test_build_servicedesk_skill_plan_prompt_capability_classification_label_set():
    prompt = build_servicedesk_skill_plan_prompt(
        request_id="55853",
        saved_context="# ServiceDesk request context\n\nExample context",
        skill_definitions_text="## active_directory.user.inspect\n\nExample skill",
    )

    # Allowed-labels block must enumerate the five buckets exactly once.
    assert "Allowed capability_classification labels:" in prompt
    for label in (
        "`read_only_inspection_now`",
        "`draft_only_manual_now`",
        "`blocked_missing_information`",
        "`unsupported_no_safe_capability`",
        "`future_automation_candidate`",
    ):
        assert label in prompt

    # Metadata block must surface the field with a placeholder pointing at
    # the allowed labels.
    assert (
        "- Capability classification: <one allowed "
        "capability_classification label>" in prompt
    )


def test_build_servicedesk_skill_plan_prompt_describes_read_only_inspection_now_bucket():
    prompt = build_servicedesk_skill_plan_prompt(
        request_id="56104",
        saved_context=(
            "# ServiceDesk request context\n\n"
            "Read-only AD inspection requested for user name.surname and "
            "group usr.podpis.test.\n"
        ),
        skill_definitions_text="## active_directory.user.inspect\n",
    )

    assert "Capability classification rules:" in prompt
    # read_only_inspection_now is gated on registered inspector(s) + all
    # required inputs being present, with Ready for inspection: yes.
    assert "`read_only_inspection_now`" in prompt
    assert (
        "at least one registered inspector ID is listed under "
        "`Suggested inspector tools` AND every required input for those "
        "inspectors is `status: present`" in prompt
    )
    assert "Set `Ready for inspection: yes`" in prompt
    # The three AD inspectors are referenced as concrete examples.
    assert "all three AD inspectors" in prompt
    assert "`exchange.mailbox.inspect`" in prompt


def test_build_servicedesk_skill_plan_prompt_describes_draft_only_manual_now_bucket():
    prompt = build_servicedesk_skill_plan_prompt(
        request_id="60001",
        saved_context=(
            "# ServiceDesk request context\n\n"
            "Please add user name.surname to AD group usr.podpis.test.\n"
        ),
        skill_definitions_text="## active_directory.group.add_member\n",
    )

    # Group membership add/remove etc. live here while no executor is
    # wired. Ready for execution must stay no, Suggested execute tools
    # must remain none.
    assert "`draft_only_manual_now`" in prompt
    assert (
        "Write-shaped skills that have no implemented executor (for "
        "example AD group membership add/remove" in prompt
    )
    # Profile/surname/attribute updates must also be called out as a
    # draft_only_manual_now case so they don't bleed into execute tools.
    assert "AD profile/surname/attribute update" in prompt
    assert "Set `Ready for execution: no`" in prompt
    assert "leave `Suggested execute tools: none`" in prompt

    # Manual-work wording for the next action and the work plan is
    # required for draft_only_manual_now.
    assert (
        "`Proposed next action` and `Internal work plan` MUST be phrased "
        "as manual technician steps" in prompt
    )
    assert "manual change in ADUC / Exchange admin / target system" in prompt
    assert (
        "MUST NOT be phrased as if Work Copilot will perform the external "
        "modification" in prompt
    )


def test_build_servicedesk_skill_plan_prompt_forbids_yaml_or_future_tool_names_in_suggested_execute_tools():
    prompt = build_servicedesk_skill_plan_prompt(
        request_id="60010",
        saved_context=(
            "# ServiceDesk request context\n\n"
            "Please update surname for user name.surname.\n"
        ),
        skill_definitions_text="## active_directory.user.update_attributes\n",
    )

    # Cross-cutting rule: only implemented, registered, approval-gated
    # execute tools may appear; YAML/future tool names must not.
    assert (
        "`Suggested execute tools` must be `none` unless the tool is an "
        "implemented, registered, approval-gated execute tool in Work "
        "Copilot." in prompt
    )
    assert (
        "YAML skill ids, `future_tool_bindings` entries, and hypothetical "
        "tool names are NOT executable tools and MUST NOT be copied into "
        "`Suggested execute tools`." in prompt
    )

    # Concrete examples of forbidden names (the bug this patch addresses
    # was active_directory.user.update_attributes leaking through).
    for forbidden_name in (
        "`active_directory.user.update_attributes`",
        "`active_directory.group.add_member`",
        "`active_directory.group.remove_member`",
        "`active_directory.user.reset_password`",
        "`exchange.archive.enable`",
    ):
        assert forbidden_name in prompt, (
            f"Expected forbidden execute-tool name {forbidden_name} to be "
            "called out in the prompt"
        )

    # Across every classification, including draft_only_manual_now, the
    # correct value while no executor exists is `none`.
    assert (
        "Across every classification — including "
        "`draft_only_manual_now` — the correct value while no executor "
        "exists is `none`." in prompt
    )

    # The placeholder for the field itself must reinforce the rule.
    assert "Suggested execute tools: <comma-separated implemented" in prompt
    assert (
        "YAML skill ids, `future_tool_bindings` entries, and hypothetical "
        "tool names (for example "
        "`active_directory.user.update_attributes`) MUST NOT appear here"
        in prompt
    )
    assert "use `none` while no executor is implemented." in prompt


def test_build_servicedesk_skill_plan_prompt_describes_blocked_missing_information_bucket():
    prompt = build_servicedesk_skill_plan_prompt(
        request_id="60002",
        saved_context=(
            "# ServiceDesk request context\n\n"
            "Please inspect mailbox of the affected user (no email or "
            "username given).\n"
        ),
        skill_definitions_text="## exchange.mailbox.inspect\n",
    )

    assert "`blocked_missing_information`" in prompt
    assert "`status: missing` or `status: unclear`" in prompt
    # The plan must reflect the missing input and avoid suggesting
    # inspectors whose inputs are not present.
    assert "Reflect it in `Missing information needed now`" in prompt
    assert (
        "Do not list inspector tools whose required inputs are missing"
        in prompt
    )
    assert "set `Ready for inspection: no`" in prompt


def test_build_servicedesk_skill_plan_prompt_describes_unsupported_no_safe_capability_bucket():
    prompt = build_servicedesk_skill_plan_prompt(
        request_id="60003",
        saved_context=(
            "# ServiceDesk request context\n\n"
            "Please dump every member of every distribution group in the "
            "organisation and email them as a CSV.\n"
        ),
        skill_definitions_text="## active_directory.group.inspect\n",
    )

    assert "`unsupported_no_safe_capability`" in prompt
    # Out-of-scope examples must include broad/destructive ops and mass
    # enumeration (Get-ADGroupMember-style requests).
    assert (
        "broad/destructive operations, mass enumeration" in prompt
    )
    assert "Use `Skill match: none`" in prompt


def test_build_servicedesk_skill_plan_prompt_describes_future_automation_candidate_bucket():
    prompt = build_servicedesk_skill_plan_prompt(
        request_id="60004",
        saved_context=(
            "# ServiceDesk request context\n\n"
            "Recurring shared mailbox provisioning request — no current "
            "skill matches.\n"
        ),
        skill_definitions_text="## exchange.mailbox.inspect\n",
    )

    assert "`future_automation_candidate`" in prompt
    assert "does not yet have a registered skill or executor" in prompt
    assert (
        "do not list any unsupported tool name under `Suggested inspector "
        "tools` or `Suggested execute tools`" in prompt
    )


def test_build_servicedesk_skill_plan_prompt_forbids_inspector_suggestions_for_unsupported_or_future():
    prompt = build_servicedesk_skill_plan_prompt(
        request_id="60005",
        saved_context="# ServiceDesk request context\n\nExample context",
        skill_definitions_text="## active_directory.user.inspect\n",
    )

    assert (
        "Inspector tools must NEVER be suggested for "
        "`unsupported_no_safe_capability` or `future_automation_"
        "candidate`." in prompt
    )
    # Inspector suggestions for the other three labels are conditioned on
    # required inputs being present.
    assert (
        "They may be suggested for the other three labels only when the "
        "inputs that those inspectors require are present." in prompt
    )
    # Ready for execution stays "no" across the board.
    assert (
        "`Ready for execution` must remain `no` for every classification"
        in prompt
    )


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
    # Scope wording is system-aware: a no-change bullet must appear when
    # the report says so, but the literal phrasing comes from the report
    # itself (e.g. AD reports use "No changes were made to Active
    # Directory."). Assert the system-aware rule rather than locking the
    # prompt to a single generic phrase.
    assert (
        "Always include a no-change Scope bullet when the inspection "
        "report indicates no changes were made" in prompt
    )
    assert "system-specific wording from the report" in prompt
    assert "`No changes were made to Active Directory.`" in prompt
    assert "`No changes were made.`" in prompt
    assert "Mailbox content and attachments were not inspected." in prompt
    assert (
        "`Sensitive Active Directory attributes were not inspected.`"
        in prompt
    )
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


def test_build_servicedesk_draft_note_prompt_understands_combined_inspection_report():
    saved_inspection_report = (
        "# Inspection report for ServiceDesk request 56104\n\n"
        "## Overview\n\n- Inspectors run: 3\n- Overall status: `ok`\n\n"
        "## active_directory.user.inspect\n\n## active_directory.group.inspect\n\n"
        "## active_directory.group_membership.inspect\n"
    )
    prompt = build_servicedesk_draft_note_prompt(
        "56104",
        saved_inspection_report=saved_inspection_report,
    )

    # The prompt explains that inspection reports may be single or combined
    # and what a combined report looks like.
    assert (
        "single-inspector report or a combined report" in prompt
    )
    assert (
        "one `## <inspector_id>` section per inspector that was run"
        in prompt
    )
    assert "## active_directory.user.inspect" in prompt
    assert "## active_directory.group.inspect" in prompt
    assert "## active_directory.group_membership.inspect" in prompt

    # Already-completed inspector sections must be summarised under
    # Findings, never proposed under Follow-up.
    assert (
        "every inspector section that is present with status `ok` "
        "represents work that was already completed" in prompt
    )
    assert (
        'Do NOT propose "perform user inspection", "run group inspection", '
        '"check membership"' in prompt
    )

    # Per-family wording: AD wording for AD inspector sections, mailbox
    # wording for Exchange mailbox sections only.
    assert (
        "Use Active Directory wording (account/user/group/membership) "
        "for AD inspector sections" in prompt
    )
    assert (
        "Use mailbox wording only for Exchange mailbox inspector sections."
        in prompt
    )

    # The combined-AD example shape is present and uses NESTED Markdown
    # bullets so Rich/Textual renderers don't collapse the inspector
    # groupings into a single inline paragraph.
    assert (
        "Read-only Active Directory inspection completed for user "
        in prompt
    )
    # Top-level bullets per inspector group.
    assert "- User:" in prompt
    assert "- Group:" in prompt
    assert "- Membership:" in prompt
    # Indented sub-bullets for facts under each inspector group.
    assert "  - User exists: yes" in prompt
    assert "  - Display name: Name Surname" in prompt
    assert "  - Group exists: yes" in prompt
    assert "  - Name: usr.podpis.test" in prompt
    assert "  - User identifier: name.surname" in prompt
    assert "  - Is member: yes" in prompt

    # The flat-grouping shape that Rich collapses must NOT be suggested
    # for combined reports.
    assert "User:\n- User exists: yes" not in prompt
    assert "Group:\n- Group exists: yes" not in prompt
    assert "Membership:\n- User identifier:" not in prompt

    # Combined-report Findings rule must call out NESTED Markdown bullets
    # explicitly and ban plain standalone group labels.
    assert (
        "group bullets by inspector using NESTED Markdown bullets" in prompt
    )
    assert "`- User:`" in prompt
    assert "`- Group:`" in prompt
    assert "`- Membership:`" in prompt
    assert (
        "Do NOT use plain standalone `User:` / `Group:` / `Membership:` "
        "lines for combined reports" in prompt
    )

    # The Scope still uses AD-specific no-change wording.
    assert "- No changes were made to Active Directory." in prompt
    assert (
        "- Sensitive Active Directory attributes were not inspected."
        in prompt
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
    # fallback wording and per-inspector "do this work again" phrases.
    assert "`Review the inspection findings`" in prompt
    assert "`Confirm no changes should be made`" in prompt
    assert "`No archive-readiness recommendation was generated...`" in prompt
    assert "`Perform user inspection`" in prompt
    assert "`Run group inspection`" in prompt
    assert "`Check membership`" in prompt
    # Already-completed inspector sections must not be moved under Follow-up.
    assert (
        "If an inspector section is already present with status `ok` in "
        "the report, do not put it under `Follow-up:`." in prompt
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


# --------------------- /sdp repair-skill-plan parsing -------------------


def test_parse_sdp_repair_skill_plan_command():
    assert (
        parse_interactive_command("/sdp repair-skill-plan 123")
        == "sdp_repair_skill_plan"
    )


def test_parse_sdp_repair_skill_plan_underscore_alias():
    assert (
        parse_interactive_command("/sdp repair_skill_plan 123")
        == "sdp_repair_skill_plan"
    )


def test_parse_sdp_repair_plan_short_alias():
    assert (
        parse_interactive_command("/sdp repair-plan 123")
        == "sdp_repair_skill_plan"
    )


def test_parse_sdp_repair_plan_short_underscore_alias():
    assert (
        parse_interactive_command("/sdp repair_plan 123")
        == "sdp_repair_skill_plan"
    )


# --------------------- Repair prompt builder ----------------------------


def test_build_servicedesk_skill_plan_repair_prompt_includes_saved_plan_and_validation():
    saved_plan = "# ServiceDesk skill plan\n\n## Metadata\n\n- Ticket: 56999\n"
    validation_lines = [
        "Skill plan validation: found 2 issue(s).",
        "- ERROR [ready_for_execution_must_be_no]: Automation handoff `Ready for execution` must be `no`; got `yes`.",
        "- WARNING [clean_identifier_values]: Inspector-bound field `target_user` value `user: x` is prefixed.",
    ]

    prompt = build_servicedesk_skill_plan_repair_prompt(
        request_id="56999",
        saved_skill_plan=saved_plan,
        validation_lines=validation_lines,
    )

    # Saved plan and validation findings appear inside dedicated blocks.
    assert "<saved_skill_plan>" in prompt
    assert "</saved_skill_plan>" in prompt
    assert saved_plan.strip() in prompt
    assert "<validation_findings>" in prompt
    assert "</validation_findings>" in prompt
    for line in validation_lines:
        assert line in prompt

    # Local-only / no-side-effects framing.
    assert "local-only repair" in prompt
    assert "Do not run any inspector." in prompt
    assert "Do not contact Active Directory or Exchange." in prompt
    assert "Do not modify ServiceDesk." in prompt


def test_build_servicedesk_skill_plan_repair_prompt_fix_only_validation_issues():
    prompt = build_servicedesk_skill_plan_repair_prompt(
        request_id="56999",
        saved_skill_plan="## Metadata\n\n- Ticket: 56999\n",
        validation_lines=["Skill plan validation: no issues found."],
    )

    assert (
        "Fix ONLY the parts of the saved skill plan that the validation "
        "findings flagged." in prompt
    )
    assert "Preserve every other section" in prompt
    assert "Do not invent facts" in prompt


def test_build_servicedesk_skill_plan_repair_prompt_blocks_unsupported_inspectors_and_execute_tools():
    prompt = build_servicedesk_skill_plan_repair_prompt(
        request_id="56999",
        saved_skill_plan="## Metadata\n",
        validation_lines=["Skill plan validation: no issues found."],
    )

    # Unsupported inspector IDs must be dropped, not added.
    assert (
        "Do not add unsupported inspector IDs to `Suggested inspector "
        "tools`." in prompt
    )
    assert "`exchange.mailbox.inspect`" in prompt
    assert "`active_directory.user.inspect`" in prompt
    assert "`active_directory.group.inspect`" in prompt
    assert "`active_directory.group_membership.inspect`" in prompt

    # No execute tools may be added.
    assert "Do not add any execute tools." in prompt
    assert "`Suggested execute tools` must be `none`" in prompt
    assert "Keep `Ready for execution: no`" in prompt


def test_build_servicedesk_skill_plan_repair_prompt_returns_only_repaired_markdown():
    prompt = build_servicedesk_skill_plan_repair_prompt(
        request_id="56999",
        saved_skill_plan="## Metadata\n",
        validation_lines=["Skill plan validation: no issues found."],
    )

    assert "Return ONLY the repaired skill plan Markdown." in prompt
    assert (
        "Do not add commentary, explanations, diffs, or surrounding "
        "prose before or after the Markdown." in prompt
    )
    # Output structure preservation reminder.
    assert "Keep `# ServiceDesk skill plan`" in prompt
    assert "## Metadata" in prompt
    assert "## Automation handoff" in prompt


# --------------------- Repair handler source-level guard ---------------


def test_textual_app_repair_skill_plan_branch_is_validation_gated():
    """Source-level guard: the /sdp repair-skill-plan handler must
    validate before building any repair prompt or running a model turn,
    must not run inspectors, and must save through the existing
    skill-plan paths.
    """
    from pathlib import Path

    source = Path("textual_app.py").read_text(encoding="utf-8")

    assert 'if command == "sdp_repair_skill_plan":' in source

    branch_index = source.index('if command == "sdp_repair_skill_plan":')
    next_branch_index = source.index(
        'if command == "sdp_inspect_skill":', branch_index
    )
    branch = source[branch_index:next_branch_index]

    # Validation runs before the repair prompt is built.
    assert "validate_skill_plan_text_for_inspection(" in branch
    validation_call = branch.index("validate_skill_plan_text_for_inspection(")
    repair_prompt_call = branch.index(
        "build_servicedesk_skill_plan_repair_prompt("
    )
    assert validation_call < repair_prompt_call

    # No inspector path is reached from the repair branch.
    assert "select_inspectors_for_skill_plan(" not in branch
    assert "create_configured_inspector_registry_from_env(" not in branch
    assert "run_inspector_and_save(" not in branch

    # Repair output goes through the existing skill-plan save paths so
    # /sdp inspect-skill picks up the repaired version.
    assert "build_servicedesk_skill_plan_path(" in branch
    assert "build_servicedesk_latest_skill_plan_path(" in branch

    # Post-save validation runs again so the user sees whether repair
    # succeeded.
    assert (
        "post_save_callback=build_persisting_validation_callback(" in branch
    )

    # No-error and validation-unavailable short circuits are present.
    # (Source uses Python adjacent-string-literal concatenation; assert
    # against the individual literals rather than the joined runtime string.)
    assert "No skill plan repair needed; no validation errors " in branch
    assert "were found." in branch
    assert "Skill plan repair unavailable because validation " in branch
    assert "could not be completed." in branch


# --------------------- /sdp inspect-skill structured-source guard -------


def test_textual_app_sdp_inspect_skill_branch_prefers_structured_sidecar():
    """Source-level guard for /sdp inspect-skill structured-plan path.

    Required behavior:
    - branch loads latest_skill_plan.json via load_skill_plan_json_sidecar(...).
    - if the structured sidecar is readable+plan, inspector selection and
      validation use the parsed-plan helpers
      (select_inspectors_for_parsed_skill_plan,
      validate_parsed_skill_plan_for_inspection).
    - if the sidecar exists but is stale/unreadable, an advisory line is
      logged and the branch falls back to the Markdown helpers.
    - if the sidecar is missing, the branch silently uses the Markdown
      helpers as before.
    - validation gate is preserved before inspector execution.
    """
    from pathlib import Path

    source = Path("textual_app.py").read_text(encoding="utf-8")

    assert 'if command == "sdp_inspect_skill":' in source

    branch_index = source.index('if command == "sdp_inspect_skill":')
    # Slice to the next top-level command branch or the end of file.
    after = source[branch_index:]
    next_marker = "        if command == "
    next_offset = after.find(next_marker, len("        if command == "))
    branch = after if next_offset == -1 else after[:next_offset]

    # Loader is invoked for the structured sidecar.
    assert "load_skill_plan_json_sidecar(" in branch

    # Both validation surfaces are referenced: parsed-plan path and
    # Markdown fallback.
    assert "validate_parsed_skill_plan_for_inspection(" in branch
    assert "validate_skill_plan_text_for_inspection(" in branch

    # Both inspector-selection surfaces are referenced.
    assert "select_inspectors_for_parsed_skill_plan(" in branch
    assert "select_inspectors_for_skill_plan(" in branch

    # Stale/unreadable sidecar emits a fallback advisory mentioning
    # latest_skill_plan.md.
    assert "Structured skill plan sidecar could not be used" in branch
    assert "latest_skill_plan.md" in branch

    # Validation gate still blocks inspector execution.
    assert "validation_result.has_errors" in branch
    block_index = branch.index("Skill plan inspection blocked")
    inspector_run_index = branch.index("run_inspector_and_save(")
    assert block_index < inspector_run_index

    # Both request builders are referenced. Structured-source path uses
    # build_inspector_request_from_parsed_skill_plan; Markdown fallback
    # path uses build_inspector_request_from_skill_plan.
    assert "build_inspector_request_from_parsed_skill_plan(" in branch
    assert "build_inspector_request_from_skill_plan(" in branch
    assert "skill_plan_text=latest_skill_plan" in branch
    assert "plan=sidecar_load_result.plan" in branch

    # The dispatch is gated on the same flag that selected validation /
    # selection source, so structured and Markdown paths stay in lockstep.
    assert "if use_structured_plan:" in branch

    # run_inspector_and_save still runs after request building.
    request_build_index = branch.index(
        "build_inspector_request_from_parsed_skill_plan("
    )
    inspector_run_index_2 = branch.index("run_inspector_and_save(")
    assert request_build_index < inspector_run_index_2


# --------------------- /sdp status parsing ------------------------------


def test_parse_sdp_status_command():
    assert parse_interactive_command("/sdp status 56050") == "sdp_status"
    assert parse_sdp_request_id("/sdp status 56050") == "56050"


def test_parse_sdp_workflow_status_alias():
    assert (
        parse_interactive_command("/sdp workflow-status 56050") == "sdp_status"
    )
    assert (
        parse_interactive_command("/sdp workflow_status 56050") == "sdp_status"
    )


# --------------------- /sdp status handler source guard -----------------


def test_textual_app_sdp_status_branch_is_local_read_only():
    """Source-level guard: /sdp status must read the local workflow
    state and must not run inspectors, model turns, or external calls.
    """
    from pathlib import Path

    source = Path("textual_app.py").read_text(encoding="utf-8")

    assert 'if command == "sdp_status":' in source

    branch_start = source.index('if command == "sdp_status":')
    next_branch = source.index('if command == "unknown":', branch_start)
    branch = source[branch_start:next_branch]

    # Reads local workflow state.
    assert "read_servicedesk_workflow_state(" in branch
    assert "workspace=self.config.workspace" in branch
    assert "request_id=request_id," in branch

    # Maps via the helper and only when one is available.
    assert "suggested_next_command_for_next_action(" in branch
    assert "next_action=state.next_action" in branch

    # Local read-only: must not run model turns, inspectors, or
    # connector writes from this branch.
    assert "_run_model_turn_worker(" not in branch
    assert "_save_servicedesk_note_worker(" not in branch
    assert "_save_servicedesk_draft_worker(" not in branch
    assert "select_inspectors_for_skill_plan(" not in branch
    assert "create_configured_inspector_registry_from_env(" not in branch
    assert "run_inspector_and_save(" not in branch
    assert "build_servicedesk_inspection_report(" not in branch


# --------------------- /sdp work parsing --------------------------------


def test_parse_sdp_work_command():
    assert parse_interactive_command("/sdp work 56050") == "sdp_work"
    assert parse_sdp_request_id("/sdp work 56050") == "56050"


def test_parse_sdp_continue_alias():
    assert parse_interactive_command("/sdp continue 56050") == "sdp_work"


# --------------------- /sdp work handler safety guards ------------------


def test_textual_app_sdp_work_branch_is_state_driven_and_save_safe():
    """Source-level guard: /sdp work must read local workflow state,
    advance at most one step by re-dispatching the existing branch for
    the next action, and must never auto-save an internal note.
    """
    from pathlib import Path

    source = Path("textual_app.py").read_text(encoding="utf-8")

    assert 'if command == "sdp_work":' in source

    branch_start = source.index('if command == "sdp_work":')
    next_branch = source.index('if command == "unknown":', branch_start)
    branch = source[branch_start:next_branch]

    # Reads local workflow state; never invents an action without it.
    assert "read_servicedesk_workflow_state(" in branch
    assert "workspace=self.config.workspace" in branch
    assert "request_id=request_id," in branch

    # Single clear header is printed up front; the duplicate
    # "ServiceDesk workflow state for request <id>" title from the
    # status_lines list is skipped.
    assert "ServiceDesk work for request " in branch
    assert "duplicate_title = (" in branch
    assert (
        'f"ServiceDesk workflow state for request {request_id}"' in branch
    )
    assert "if line == duplicate_title:" in branch
    assert "continue" in branch

    # Branches explicitly on review/save/none so it never auto-dispatches
    # the underlying save-note worker.
    assert "ServiceDeskWorkflowNextAction.SAVE_NOTE" in branch
    assert "ServiceDeskWorkflowNextAction.REVIEW_DRAFT_NOTE" in branch
    assert "ServiceDeskWorkflowNextAction.NONE" in branch

    # The save-note branch never invokes the approval-gated worker and
    # tells the user to review-and-save manually with the exact
    # `/sdp save-note <id>` line.
    assert "_save_servicedesk_note_worker(" not in branch
    assert "servicedesk_add_request_note" not in branch
    assert "Draft note is ready. Review it, then run " in branch
    assert "`/sdp save-note {request_id}` if approved." in branch
    assert "if approved." in branch

    # Review-only short-circuit also points at the manual save command.
    assert "Draft note is ready for review. Review the local " in branch

    # NONE short-circuit points at /sdp status, no dispatch.
    assert "No next workflow action is available." in branch
    assert "`/sdp status {request_id}` for details." in branch

    # /sdp work must not directly call any write helper or invent an
    # inspector run; it must delegate via _submit_prompt so existing
    # safety gates fire unchanged.
    assert "_save_servicedesk_draft_worker(" not in branch
    assert "select_inspectors_for_skill_plan(" not in branch
    assert "create_configured_inspector_registry_from_env(" not in branch
    assert "run_inspector_and_save(" not in branch
    assert "build_servicedesk_inspection_report(" not in branch
    assert "_run_model_turn_worker(" not in branch

    # Single-step dispatch: synthesize a single /sdp <command> <id> line
    # via the workflow-state mapping helper, log the new "Next safe
    # step:" / "Running:" / "run `/sdp work <id>` again to continue."
    # lines, and re-enter _submit_prompt exactly once.
    assert "suggested_next_command_for_next_action(" in branch
    assert "Next safe step: " in branch
    assert "Running: " in branch
    assert (
        "After this step completes, run " in branch
        and "`/sdp work {request_id}` again to continue." in branch
    )
    assert "self._submit_prompt(suggested_command)" in branch
    assert branch.count("self._submit_prompt(") == 1

    # Old wording must not appear anywhere in the branch.
    assert "Advancing one step: " not in branch
    assert "Dispatching: " not in branch
    assert "Draft note appears ready" not in branch
    assert '_log_system_message("ServiceDesk workflow state:")' not in branch
