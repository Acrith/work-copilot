from datetime import UTC, datetime

from draft_exports import (
    NO_REQUESTER_REPLY_RECOMMENDED,
    build_servicedesk_context_path,
    build_servicedesk_draft_note_path,
    build_servicedesk_draft_note_preview_lines,
    build_servicedesk_draft_path,
    build_servicedesk_draft_subject,
    build_servicedesk_latest_context_path,
    build_servicedesk_latest_draft_path,
    build_servicedesk_latest_skill_plan_json_path,
    build_servicedesk_latest_skill_plan_path,
    build_servicedesk_output_dir,
    build_servicedesk_skill_plan_path,
    extract_markdown_section,
    extract_servicedesk_draft_reply,
    extract_servicedesk_note_body,
    extract_servicedesk_request_subject,
    is_no_requester_reply_recommended,
    read_text_if_exists,
    safe_filename_part,
    save_text_draft,
)


def test_safe_filename_part_removes_unsafe_characters():
    assert safe_filename_part("  ticket / 123:abc  ") == "ticket_123_abc"


def test_safe_filename_part_falls_back_for_empty_value():
    assert safe_filename_part("   ") == "draft"


def test_build_servicedesk_output_dir(tmp_path):
    path = build_servicedesk_output_dir(
        workspace=str(tmp_path),
        request_id="55/478",
    )

    assert path == tmp_path / ".work_copilot" / "servicedesk" / "55_478"


def test_build_servicedesk_draft_path(tmp_path):
    path = build_servicedesk_draft_path(
        workspace=str(tmp_path),
        request_id="55478",
        now=datetime(2026, 4, 26, 20, 0, 0, tzinfo=UTC),
    )

    assert path == (
        tmp_path
        / ".work_copilot"
        / "servicedesk"
        / "55478"
        / "reply_20260426_200000.md"
    )


def test_build_servicedesk_context_path(tmp_path):
    path = build_servicedesk_context_path(
        workspace=str(tmp_path),
        request_id="55853",
        now=datetime(2026, 4, 27, 7, 41, 18, tzinfo=UTC),
    )

    assert path == (
        tmp_path
        / ".work_copilot"
        / "servicedesk"
        / "55853"
        / "context_20260427_074118.md"
    )


def test_build_servicedesk_latest_paths(tmp_path):
    latest_context = build_servicedesk_latest_context_path(
        workspace=str(tmp_path),
        request_id="55853",
    )
    latest_reply = build_servicedesk_latest_draft_path(
        workspace=str(tmp_path),
        request_id="55853",
    )

    assert latest_context == (
        tmp_path
        / ".work_copilot"
        / "servicedesk"
        / "55853"
        / "latest_context.md"
    )
    assert latest_reply == (
        tmp_path
        / ".work_copilot"
        / "servicedesk"
        / "55853"
        / "latest_reply.md"
    )


def test_save_text_draft_creates_parent_directory(tmp_path):
    path = tmp_path / ".work_copilot" / "servicedesk" / "55478" / "reply.md"

    result = save_text_draft(path, "hello")

    assert result == path
    assert path.read_text(encoding="utf-8") == "hello"


def test_read_text_if_exists_returns_none_for_missing_file(tmp_path):
    path = tmp_path / "missing.md"

    assert read_text_if_exists(path) is None


def test_read_text_if_exists_reads_existing_file(tmp_path):
    path = tmp_path / "context.md"
    path.write_text("saved context", encoding="utf-8")

    assert read_text_if_exists(path) == "saved context"


def test_extract_markdown_section_extracts_named_section():
    markdown = """# Title

## Draft reply

Hello requester.

Line two.

## Internal reasoning

Reasoning here.
"""

    assert extract_markdown_section(markdown, "Draft reply") == (
        "Hello requester.\n\nLine two."
    )


def test_extract_markdown_section_returns_none_when_missing():
    markdown = "# Title\n\n## Other\n\nNo draft here."

    assert extract_markdown_section(markdown, "Draft reply") is None


def test_extract_servicedesk_draft_reply():
    markdown = """# ServiceDesk reply draft

## Draft reply

Please confirm this works.

## Safety notes

None.
"""

    assert extract_servicedesk_draft_reply(markdown) == "Please confirm this works."


def test_is_no_requester_reply_recommended():
    assert is_no_requester_reply_recommended(NO_REQUESTER_REPLY_RECOMMENDED)
    assert is_no_requester_reply_recommended(
        "No requester-facing reply recommended at this time"
    )
    assert not is_no_requester_reply_recommended("Please confirm this works.")


def test_build_servicedesk_draft_subject_falls_back_to_request_id():
    assert build_servicedesk_draft_subject("55776") == "Re: ServiceDesk request 55776"


def test_build_servicedesk_draft_subject_uses_original_subject():
    assert (
        build_servicedesk_draft_subject("55776", original_subject="VPN access")
        == "Re: VPN access"
    )


def test_build_servicedesk_draft_subject_does_not_duplicate_re_prefix():
    assert (
        build_servicedesk_draft_subject("55776", original_subject="Re: VPN access")
        == "Re: VPN access"
    )


def test_extract_servicedesk_request_subject_from_metadata():
    context = """
# ServiceDesk request context

## Metadata

- request_id: 55776
- request_subject: VPN access

## Current state

needs_work
"""

    assert extract_servicedesk_request_subject(context) == "VPN access"


def test_build_servicedesk_skill_plan_path(tmp_path):
    path = build_servicedesk_skill_plan_path(
        workspace=str(tmp_path),
        request_id="55853",
    )

    assert path.parent == tmp_path / ".work_copilot" / "servicedesk" / "55853"
    assert path.name.startswith("skill_plan_")
    assert path.name.endswith(".md")


def test_build_servicedesk_latest_skill_plan_path(tmp_path):
    path = build_servicedesk_latest_skill_plan_path(
        workspace=str(tmp_path),
        request_id="55853",
    )

    assert path == (
        tmp_path
        / ".work_copilot"
        / "servicedesk"
        / "55853"
        / "latest_skill_plan.md"
    )


def test_build_servicedesk_latest_skill_plan_json_path(tmp_path):
    path = build_servicedesk_latest_skill_plan_json_path(
        workspace=str(tmp_path),
        request_id="55853",
    )

    assert path == (
        tmp_path
        / ".work_copilot"
        / "servicedesk"
        / "55853"
        / "latest_skill_plan.json"
    )


def test_build_servicedesk_latest_skill_plan_json_path_sanitizes_request_id(
    tmp_path,
):
    path = build_servicedesk_latest_skill_plan_json_path(
        workspace=str(tmp_path),
        request_id="55/853",
    )

    assert path == (
        tmp_path
        / ".work_copilot"
        / "servicedesk"
        / "55_853"
        / "latest_skill_plan.json"
    )


def test_build_servicedesk_draft_note_path(tmp_path):
    path = build_servicedesk_draft_note_path(
        workspace=str(tmp_path),
        request_id="55948",
    )

    assert path == (
        tmp_path / ".work_copilot" / "servicedesk" / "55948" / "draft_note.md"
    )


SAMPLE_DRAFT_NOTE = """\
# ServiceDesk internal note draft

- Ticket: 55948
- Note type: internal technician note
- Inspection report used: yes

## Note body

Read-only mailbox inspection completed for `user@example.com`.

Findings:
- Mailbox exists: yes
- Display name: Example User
- Mailbox size: 136.7 MB

Scope:
- No changes were made.
- Mailbox content and attachments were not inspected.

## Local draft metadata

- Generated locally by Work Copilot.
- Not posted to ServiceDesk yet.
- Source files used: saved context, inspection report
"""


def test_extract_servicedesk_note_body_returns_only_note_body_section():
    body = extract_servicedesk_note_body(SAMPLE_DRAFT_NOTE)

    assert body is not None
    assert body.startswith(
        "Read-only mailbox inspection completed for `user@example.com`."
    )
    assert "Findings:" in body
    assert "- Mailbox exists: yes" in body
    assert "Scope:" in body
    # Local draft metadata must NOT be part of the postable body.
    assert "Local draft metadata" not in body
    assert "Generated locally by Work Copilot." not in body
    assert "Not posted to ServiceDesk yet." not in body
    assert "Source files used:" not in body


def test_extract_servicedesk_note_body_returns_none_when_section_missing():
    text = (
        "# ServiceDesk internal note draft\n\n"
        "- Ticket: 55948\n\n"
        "## Local draft metadata\n\n"
        "- Generated locally by Work Copilot.\n"
    )

    assert extract_servicedesk_note_body(text) is None


def test_extract_servicedesk_note_body_returns_none_when_section_empty():
    text = (
        "# ServiceDesk internal note draft\n\n"
        "## Note body\n\n"
        "## Local draft metadata\n\n"
        "- Not posted to ServiceDesk yet.\n"
    )

    assert extract_servicedesk_note_body(text) is None

# --------------------- build_servicedesk_draft_note_preview_lines -------


def test_build_servicedesk_draft_note_preview_lines_missing_file(tmp_path):
    lines = build_servicedesk_draft_note_preview_lines(
        workspace=str(tmp_path),
        request_id="56050",
    )

    assert len(lines) == 1
    assert lines[0].startswith("No local draft note found at ")
    assert "draft_note.md" in lines[0]


def test_build_servicedesk_draft_note_preview_lines_prefers_note_body(
    tmp_path,
):
    path = build_servicedesk_draft_note_path(
        workspace=str(tmp_path), request_id="56050"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# ServiceDesk internal note draft\n\n"
        "## Local draft metadata\n\n"
        "- Not posted to ServiceDesk yet.\n\n"
        "## Note body\n\n"
        "Findings:\n"
        "- AD user exists.\n"
        "- Group membership confirmed.\n\n"
        "Suggested next step:\n"
        "- Review and approve.\n",
        encoding="utf-8",
    )

    lines = build_servicedesk_draft_note_preview_lines(
        workspace=str(tmp_path),
        request_id="56050",
    )

    assert lines[0] == f"Local draft note: {path}"
    assert lines[1] == "Draft note preview:"

    body = lines[2:]
    # The preview must be sourced from the `## Note body` section so
    # the metadata header is not previewed.
    joined = "\n".join(body)
    assert "Local draft metadata" not in joined
    assert "Findings:" in joined
    assert "- AD user exists." in joined
    # All preview lines are indented by two spaces.
    assert all(line.startswith("  ") for line in body)
    # No truncation marker for a short note.
    assert "... (preview truncated)" not in joined


def test_build_servicedesk_draft_note_preview_lines_truncates_long_note(
    tmp_path,
):
    path = build_servicedesk_draft_note_path(
        workspace=str(tmp_path), request_id="56050"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    body_lines = "\n".join(f"line {n}" for n in range(50))
    path.write_text(
        f"## Note body\n\n{body_lines}\n",
        encoding="utf-8",
    )

    lines = build_servicedesk_draft_note_preview_lines(
        workspace=str(tmp_path),
        request_id="56050",
        line_limit=8,
    )

    # Header + "preview:" + 8 capped body lines + truncation marker.
    assert len(lines) == 2 + 8 + 1
    assert lines[-1] == "  ... (preview truncated)"
    # First previewed line is the first non-empty body line.
    assert lines[2] == "  line 0"
    assert lines[2 + 7] == "  line 7"


def test_build_servicedesk_draft_note_preview_lines_falls_back_to_full_text(
    tmp_path,
):
    """If the draft has no `## Note body` section, the helper should
    preview the full Markdown rather than refuse.
    """
    path = build_servicedesk_draft_note_path(
        workspace=str(tmp_path), request_id="56050"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Draft note\n\n"
        "Plain freeform draft without a Note body section.\n",
        encoding="utf-8",
    )

    lines = build_servicedesk_draft_note_preview_lines(
        workspace=str(tmp_path),
        request_id="56050",
    )

    assert lines[0] == f"Local draft note: {path}"
    assert lines[1] == "Draft note preview:"
    joined = "\n".join(lines[2:])
    assert "Plain freeform draft" in joined


def test_build_servicedesk_draft_note_preview_lines_handles_empty_file(
    tmp_path,
):
    path = build_servicedesk_draft_note_path(
        workspace=str(tmp_path), request_id="56050"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")

    lines = build_servicedesk_draft_note_preview_lines(
        workspace=str(tmp_path),
        request_id="56050",
    )

    assert lines == [
        f"Local draft note: {path}",
        "Draft note has no preview content.",
    ]


def test_build_servicedesk_draft_note_preview_lines_does_not_raise_on_read_error(
    tmp_path, monkeypatch
):
    path = build_servicedesk_draft_note_path(
        workspace=str(tmp_path), request_id="56050"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("## Note body\n\nHello.\n", encoding="utf-8")

    from pathlib import Path as _Path

    import draft_exports as draft_exports_module

    real_read_text = _Path.read_text

    def _boom(self, *args, **kwargs):
        if self.name == "draft_note.md":
            raise OSError("synthetic read failure")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(draft_exports_module.Path, "read_text", _boom)

    lines = build_servicedesk_draft_note_preview_lines(
        workspace=str(tmp_path),
        request_id="56050",
    )

    assert len(lines) == 1
    assert "could not be read" in lines[0]
    assert "synthetic read failure" in lines[0]
