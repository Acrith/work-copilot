from draft_exports import build_servicedesk_draft_note_path
from servicedesk_draft_note_validation import (
    DraftNoteValidationFinding,
    draft_note_findings_have_errors,
    format_draft_note_validation_findings,
    validate_servicedesk_draft_note_file,
    validate_servicedesk_draft_note_text,
)

_VALID_DRAFT = """\
# ServiceDesk internal note draft

- Ticket: 56050
- Note type: internal technician note

## Note body

Read-only AD inspection completed for `name.surname@example.com`.

Findings:
- AD user exists.
- Group membership confirmed.

Suggested next step:
- Manual technician action.
"""


_NOTE_BODY_MISSING = """\
# ServiceDesk internal note draft

- Ticket: 56050

## Local draft metadata

- Not posted to ServiceDesk yet.
"""


_NOTE_BODY_EMPTY = """\
## Note body

   \t

## Other section

content
"""


_NOTE_BODY_WITH_TODO = """\
## Note body

Inspection summary.

TODO: rewrite this section before saving.
"""


_NOTE_BODY_WITH_TBD = """\
## Note body

Mailbox size: TBD.
"""


_NOTE_BODY_WITH_FILL_IN = """\
## Note body

Group membership: <fill in>.
"""


_NOTE_BODY_WITH_BRACKET_FILL_IN = """\
## Note body

Display name: [fill in].
"""


_NOTE_BODY_WITH_LOREM = """\
## Note body

Lorem ipsum dolor sit amet.
"""


_NOTE_BODY_WITH_AD_WRITE_CLAIM = """\
## Note body

I changed Active Directory to add the user to the group.
"""


_NOTE_BODY_WITH_MAILBOX_WRITE_CLAIM = """\
## Note body

I modified the mailbox quota policy.
"""


_NOTE_BODY_WITH_ARCHIVE_WRITE_CLAIM = """\
## Note body

I enabled archive on the shared mailbox.
"""


# --------------------- validate_servicedesk_draft_note_text -------------


def test_valid_draft_has_no_findings():
    findings = validate_servicedesk_draft_note_text(_VALID_DRAFT)

    assert findings == []
    assert draft_note_findings_have_errors(findings) is False


def test_missing_note_body_section_returns_error():
    findings = validate_servicedesk_draft_note_text(_NOTE_BODY_MISSING)

    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert findings[0].code == "note_body_missing"
    assert draft_note_findings_have_errors(findings) is True


def test_empty_note_body_returns_error():
    findings = validate_servicedesk_draft_note_text(_NOTE_BODY_EMPTY)

    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert findings[0].code == "note_body_empty"
    assert draft_note_findings_have_errors(findings) is True


def test_todo_placeholder_returns_error():
    findings = validate_servicedesk_draft_note_text(_NOTE_BODY_WITH_TODO)

    codes = [f.code for f in findings]
    assert "placeholder_text_present" in codes
    assert any("TODO" in f.message for f in findings)
    assert draft_note_findings_have_errors(findings) is True


def test_tbd_placeholder_returns_error():
    findings = validate_servicedesk_draft_note_text(_NOTE_BODY_WITH_TBD)

    codes = [f.code for f in findings]
    assert "placeholder_text_present" in codes
    assert any("TBD" in f.message for f in findings)


def test_angle_fill_in_placeholder_returns_error():
    findings = validate_servicedesk_draft_note_text(
        _NOTE_BODY_WITH_FILL_IN
    )

    codes = [f.code for f in findings]
    assert "placeholder_text_present" in codes
    assert any("<fill in>" in f.message for f in findings)


def test_bracket_fill_in_placeholder_returns_error():
    findings = validate_servicedesk_draft_note_text(
        _NOTE_BODY_WITH_BRACKET_FILL_IN
    )

    codes = [f.code for f in findings]
    assert "placeholder_text_present" in codes
    assert any("[fill in]" in f.message for f in findings)


def test_lorem_ipsum_placeholder_returns_error():
    findings = validate_servicedesk_draft_note_text(_NOTE_BODY_WITH_LOREM)

    codes = [f.code for f in findings]
    assert "placeholder_text_present" in codes


def test_forbidden_ad_write_claim_returns_error():
    findings = validate_servicedesk_draft_note_text(
        _NOTE_BODY_WITH_AD_WRITE_CLAIM
    )

    codes = [f.code for f in findings]
    assert "forbidden_write_claim" in codes
    assert any(
        "I changed Active Directory" in f.message for f in findings
    )


def test_forbidden_mailbox_write_claim_returns_error():
    findings = validate_servicedesk_draft_note_text(
        _NOTE_BODY_WITH_MAILBOX_WRITE_CLAIM
    )

    codes = [f.code for f in findings]
    assert "forbidden_write_claim" in codes


def test_forbidden_archive_write_claim_returns_error():
    findings = validate_servicedesk_draft_note_text(
        _NOTE_BODY_WITH_ARCHIVE_WRITE_CLAIM
    )

    codes = [f.code for f in findings]
    assert "forbidden_write_claim" in codes


def test_inspection_summary_with_word_overlap_does_not_false_positive():
    """Words that contain TODO/TBD as substrings (e.g. methodology,
    tbd-suffixed identifiers) must not trigger the placeholder check —
    only real placeholders should.
    """
    safe_body = (
        "## Note body\n\n"
        "Findings:\n"
        "- methodology applied: read-only inspection\n"
        "- account is xyztbdservice (sanitized identifier)\n"
        "- mailbox archive is enabled by policy (existing state)\n"
    )

    findings = validate_servicedesk_draft_note_text(safe_body)

    placeholder_findings = [
        f for f in findings if f.code == "placeholder_text_present"
    ]
    write_claim_findings = [
        f for f in findings if f.code == "forbidden_write_claim"
    ]
    assert placeholder_findings == []
    # "archive is enabled" is past tense / observational, not "I
    # enabled archive" — must not trigger the write-claim heuristic.
    assert write_claim_findings == []


# --------------------- validate_servicedesk_draft_note_file -------------


def test_validate_file_missing_draft(tmp_path):
    findings = validate_servicedesk_draft_note_file(
        workspace=str(tmp_path),
        request_id="56050",
    )

    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert findings[0].code == "draft_note_missing"
    assert draft_note_findings_have_errors(findings) is True


def test_validate_file_reads_and_validates_draft(tmp_path):
    path = build_servicedesk_draft_note_path(
        workspace=str(tmp_path), request_id="56050"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_VALID_DRAFT, encoding="utf-8")

    findings = validate_servicedesk_draft_note_file(
        workspace=str(tmp_path),
        request_id="56050",
    )

    assert findings == []


def test_validate_file_propagates_text_errors(tmp_path):
    path = build_servicedesk_draft_note_path(
        workspace=str(tmp_path), request_id="56050"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_NOTE_BODY_WITH_TODO, encoding="utf-8")

    findings = validate_servicedesk_draft_note_file(
        workspace=str(tmp_path),
        request_id="56050",
    )

    codes = [f.code for f in findings]
    assert "placeholder_text_present" in codes


def test_validate_file_unreadable_returns_error_without_raising(
    tmp_path, monkeypatch
):
    from pathlib import Path

    import servicedesk_draft_note_validation as validation_module

    path = build_servicedesk_draft_note_path(
        workspace=str(tmp_path), request_id="56050"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_VALID_DRAFT, encoding="utf-8")

    real_read_text = Path.read_text

    def _boom(self, *args, **kwargs):
        if self.name == "draft_note.md":
            raise OSError("synthetic read failure")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(
        validation_module.build_servicedesk_draft_note_path.__globals__[
            "Path"
        ],
        "read_text",
        _boom,
    )

    findings = validate_servicedesk_draft_note_file(
        workspace=str(tmp_path),
        request_id="56050",
    )

    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert findings[0].code == "draft_note_unreadable"
    assert "synthetic read failure" in findings[0].message


# --------------------- format_draft_note_validation_findings ------------


def test_format_no_findings_returns_clean_line():
    assert format_draft_note_validation_findings([]) == [
        "Draft note validation: no issues found."
    ]


def test_format_findings_lists_severity_code_and_message():
    lines = format_draft_note_validation_findings(
        [
            DraftNoteValidationFinding(
                severity="error",
                code="note_body_missing",
                message="Draft note has no `## Note body` section.",
            ),
            DraftNoteValidationFinding(
                severity="warning",
                code="suspicious_thing",
                message="Suspicious thing found.",
            ),
        ]
    )

    assert lines[0] == "Draft note validation: found 2 finding(s)."
    assert "ERROR [note_body_missing]" in lines[1]
    assert "WARNING [suspicious_thing]" in lines[2]


# --------------------- /sdp save-note source-level guard ----------------


def test_textual_app_save_note_branch_validates_before_writing():
    """Source-level guard: the /sdp save-note branch must run local
    draft-note validation before any approval-gated ServiceDesk write
    helper. Validation errors must block the save before
    _save_servicedesk_note_worker / servicedesk_add_request_note are
    invoked, and clean validation must still allow the existing save
    path.
    """
    from pathlib import Path

    source = Path("textual_app.py").read_text(encoding="utf-8")

    assert 'if command == "sdp_save_note":' in source

    branch_start = source.index('if command == "sdp_save_note":')
    next_branch = source.index('if command == ', branch_start + 1)
    branch = source[branch_start:next_branch]

    # Validator helpers are imported and invoked.
    assert "validate_servicedesk_draft_note_text(" in branch
    assert "format_draft_note_validation_findings(" in branch
    assert "draft_note_findings_have_errors(" in branch

    # Validation runs before the save worker is called.
    validate_index = branch.index(
        "validate_servicedesk_draft_note_text("
    )
    save_worker_index = branch.index(
        "self._save_servicedesk_note_worker("
    )
    assert validate_index < save_worker_index

    # Errors-block branch logs the documented blocking advisory and
    # returns before the save worker can be reached.
    assert (
        "ServiceDesk note save blocked because draft note "
    ) in branch
    assert "validation errors were found." in branch
    block_index = branch.index(
        "ServiceDesk note save blocked because draft note "
    )
    assert block_index < save_worker_index

    # The save worker is still called exactly once (the clean path).
    assert branch.count("self._save_servicedesk_note_worker(") == 1


# --------------------- post-save validation callback -------------------


def test_post_save_callback_clean_draft_returns_clean_line(tmp_path):
    from servicedesk_draft_note_validation import (
        build_post_save_draft_note_validation_callback,
    )

    path = build_servicedesk_draft_note_path(
        workspace=str(tmp_path), request_id="56050"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_VALID_DRAFT, encoding="utf-8")

    callback = build_post_save_draft_note_validation_callback(
        workspace=str(tmp_path),
        request_id="56050",
    )

    lines = callback("ignored saved text — callback validates the file")

    assert lines == ["Draft note validation: no issues found."]


def test_post_save_callback_invalid_draft_returns_findings_and_advisory(
    tmp_path,
):
    from servicedesk_draft_note_validation import (
        build_post_save_draft_note_validation_callback,
    )

    path = build_servicedesk_draft_note_path(
        workspace=str(tmp_path), request_id="56050"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_NOTE_BODY_WITH_TODO, encoding="utf-8")

    callback = build_post_save_draft_note_validation_callback(
        workspace=str(tmp_path),
        request_id="56050",
    )

    lines = callback("ignored saved text")

    # Header comes first, then per-finding lines, then the trailing
    # advisory.
    assert lines[0].startswith("Draft note validation: found ")
    joined = "\n".join(lines)
    assert "ERROR [placeholder_text_present]" in joined
    assert lines[-1] == (
        "Draft note has validation errors. Regenerate or edit the "
        "draft before saving."
    )


def test_post_save_callback_missing_draft_returns_findings_and_advisory(
    tmp_path,
):
    from servicedesk_draft_note_validation import (
        build_post_save_draft_note_validation_callback,
    )

    callback = build_post_save_draft_note_validation_callback(
        workspace=str(tmp_path),
        request_id="56050",
    )

    lines = callback("ignored saved text")

    # The validator emits a `draft_note_missing` error, the formatter
    # renders it, and the callback appends the advisory.
    joined = "\n".join(lines)
    assert "ERROR [draft_note_missing]" in joined
    assert lines[-1] == (
        "Draft note has validation errors. Regenerate or edit the "
        "draft before saving."
    )


# --------------------- /sdp draft-note source-level guard --------------


def test_textual_app_draft_note_branch_runs_post_save_validation():
    """Source-level guard: the /sdp draft-note branch must wire the
    post-save validation callback so validation runs immediately after
    the draft is written. Validation must not run before generation,
    must not call ServiceDesk save workers, and must not call any
    inspector helpers.
    """
    from pathlib import Path

    source = Path("textual_app.py").read_text(encoding="utf-8")

    assert 'if command == "sdp_draft_note":' in source

    branch_start = source.index('if command == "sdp_draft_note":')
    next_branch = source.index('if command == ', branch_start + 1)
    branch = source[branch_start:next_branch]

    # The post-save callback builder is referenced in this branch.
    assert (
        "build_post_save_draft_note_validation_callback("
        in branch
    )

    # The callback is passed as the post_save_callback to the
    # model-turn worker.
    assert "post_save_callback=" in branch
    callback_index = branch.index(
        "build_post_save_draft_note_validation_callback("
    )
    worker_index = branch.index("self._run_model_turn_worker(")
    # Callback is constructed inside the worker call kwargs, so the
    # builder reference appears after `_run_model_turn_worker(`.
    assert worker_index < callback_index

    # The text validator must not be called directly in this branch —
    # the post-save callback handles in-memory validation of the
    # just-saved draft via the file validator instead.
    assert "validate_servicedesk_draft_note_text(" not in branch

    # The file validator IS called once before prompt construction so
    # that, when an existing draft is invalid, its findings can be
    # included in the regeneration prompt. It must not be used to
    # block draft generation; it only feeds prompt context.
    assert "validate_servicedesk_draft_note_file(" in branch
    file_validator_index = branch.index(
        "validate_servicedesk_draft_note_file("
    )
    prompt_build_index = branch.index(
        "build_servicedesk_draft_note_prompt("
    )
    assert file_validator_index < prompt_build_index, (
        "previous-draft validation must run before prompt construction "
        "so its findings can be passed into the prompt builder"
    )
    # And it must run before the model worker dispatches.
    assert file_validator_index < worker_index

    # /sdp draft-note must not invoke any ServiceDesk write helpers,
    # save workers, or inspector helpers.
    assert "_save_servicedesk_note_worker(" not in branch
    assert "_save_servicedesk_draft_worker(" not in branch
    assert "servicedesk_add_request_note" not in branch
    assert "select_inspectors_for_skill_plan(" not in branch
    assert "select_inspectors_for_parsed_skill_plan(" not in branch
    assert "create_configured_inspector_registry_from_env(" not in branch
    assert "run_inspector_and_save(" not in branch


def test_textual_app_draft_note_branch_passes_previous_validation_to_prompt():
    """Source-level guard: when a previous local draft fails
    validation, /sdp draft-note must include the formatted findings in
    the prompt sent to the model so the regenerated draft can avoid
    repeating the same mistakes. Validation-feedback discovery must
    not contact ServiceDesk, AD, or Exchange and must not run any
    inspector — it is filesystem-only.
    """
    from pathlib import Path

    source = Path("textual_app.py").read_text(encoding="utf-8")

    branch_start = source.index('if command == "sdp_draft_note":')
    next_branch = source.index("if command == ", branch_start + 1)
    branch = source[branch_start:next_branch]

    # The file validator and the formatter are both invoked in the
    # branch so previous findings can be turned into prompt context.
    assert "validate_servicedesk_draft_note_file(" in branch
    assert "format_draft_note_validation_findings(" in branch
    assert "draft_note_findings_have_errors(" in branch

    # The formatted lines are passed to the prompt builder via the
    # new keyword.
    assert "previous_validation_lines=" in branch
    assert "build_servicedesk_draft_note_prompt(" in branch
    prompt_index = branch.index("build_servicedesk_draft_note_prompt(")
    previous_kwarg_index = branch.index("previous_validation_lines=")
    assert prompt_index < previous_kwarg_index, (
        "the previous_validation_lines kwarg must be inside the "
        "build_servicedesk_draft_note_prompt(...) call"
    )

    # A concise advisory is logged when previous-validation context
    # is being attached. Source uses adjacent-string-literal layout —
    # assert each literal piece rather than the joined runtime string.
    assert "Previous draft note validation errors will be " in branch
    assert "provided to the model" in branch

    # The new validation-feedback discovery must not introduce any
    # ServiceDesk save worker, ServiceDesk write helper, or inspector
    # runner into the draft-note branch.
    assert "_save_servicedesk_note_worker(" not in branch
    assert "_save_servicedesk_draft_worker(" not in branch
    assert "servicedesk_add_request_note" not in branch
    assert "run_inspector_and_save(" not in branch

    # Post-save validation callback is still wired so the regenerated
    # draft is validated immediately after save.
    assert (
        "build_post_save_draft_note_validation_callback("
        in branch
    )
