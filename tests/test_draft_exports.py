from datetime import UTC, datetime

from draft_exports import (
    build_servicedesk_context_path,
    build_servicedesk_draft_path,
    build_servicedesk_latest_context_path,
    build_servicedesk_latest_draft_path,
    build_servicedesk_output_dir,
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