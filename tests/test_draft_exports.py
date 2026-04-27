from datetime import UTC, datetime

from draft_exports import (
    build_servicedesk_context_path,
    build_servicedesk_draft_path,
    safe_filename_part,
    save_text_draft,
)


def test_safe_filename_part_removes_unsafe_characters():
    assert safe_filename_part("  ticket / 123:abc  ") == "ticket_123_abc"


def test_safe_filename_part_falls_back_for_empty_value():
    assert safe_filename_part("   ") == "draft"


def test_build_servicedesk_draft_path(tmp_path):
    path = build_servicedesk_draft_path(
        workspace=str(tmp_path),
        request_id="55478",
        now=datetime(2026, 4, 26, 20, 0, 0, tzinfo=UTC),
    )

    assert path == (
        tmp_path
        / ".work_copilot"
        / "drafts"
        / "servicedesk_55478_reply_20260426_200000.md"
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
        / "drafts"
        / "servicedesk_55853_context_20260427_074118.md"
    )


def test_save_text_draft_creates_parent_directory(tmp_path):
    path = tmp_path / ".work_copilot" / "drafts" / "draft.md"

    result = save_text_draft(path, "hello")

    assert result == path
    assert path.read_text(encoding="utf-8") == "hello"