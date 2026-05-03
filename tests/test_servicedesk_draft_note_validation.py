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
