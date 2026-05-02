from previews import (
    ParsedDiffLine,
    build_connector_write_preview,
    build_exec_preview,
    build_write_preview,
    is_unified_diff_preview,
    parse_unified_diff,
)


def create_file(path, content=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_build_write_preview_existing_file_changed_content(tmp_path):
    file_path = tmp_path / "existing_file.txt"
    create_file(file_path, "line 1\nline 2\nline 3")
    new_content = "line A\nline 2\nline B"

    preview = build_write_preview(str(tmp_path), "existing_file.txt", new_content)

    assert "--- existing_file.txt (current)" in preview
    assert "+++ existing_file.txt (proposed)" in preview
    assert "-line 1" in preview
    assert "+line A" in preview
    assert " line 2" in preview
    assert "-line 3" in preview
    assert "+line B" in preview


def test_build_write_preview_no_op_write(tmp_path):
    file_path = tmp_path / "same_content.txt"
    existing_content = "This content is the same."
    create_file(file_path, existing_content)

    preview = build_write_preview(str(tmp_path), "same_content.txt", existing_content)

    assert 'No content changes for "same_content.txt".' in preview
    assert "---" not in preview
    assert "+++" not in preview


def test_build_write_preview_new_file(tmp_path):
    new_content = "Hello, new file!"

    preview = build_write_preview(str(tmp_path), "new_file.txt", new_content)

    assert is_unified_diff_preview(preview)
    assert "--- /dev/null" in preview
    assert "+++ new_file.txt (proposed)" in preview
    assert "@@ -0,0 +1 @@" in preview
    assert "+Hello, new file!" in preview


def test_build_write_preview_new_empty_file(tmp_path):
    preview = build_write_preview(str(tmp_path), "empty_new_file.txt", "")

    assert is_unified_diff_preview(preview)
    assert "--- /dev/null" in preview
    assert "+++ empty_new_file.txt (proposed)" in preview
    assert "@@ -0,0 +0,0 @@" in preview


def test_build_write_preview_path_is_directory(tmp_path):
    dir_path = tmp_path / "a_directory"
    dir_path.mkdir()

    preview = build_write_preview(str(tmp_path), "a_directory", "some content")

    assert 'Preview unavailable: "a_directory" is a directory.' in preview


def test_build_write_preview_path_outside_workspace_absolute(tmp_path):
    outside_path = tmp_path.parent / "outside_file.txt"
    create_file(outside_path, "content")

    preview = build_write_preview(str(tmp_path), str(outside_path), "new content")

    assert "outside the workspace" in preview


def test_build_write_preview_path_outside_workspace_relative(tmp_path):
    preview = build_write_preview(str(tmp_path), "../another_dir/outside.txt", "content")

    assert "outside the workspace" in preview


def test_build_write_preview_read_error(tmp_path, monkeypatch):
    file_path = tmp_path / "unreadable_file.txt"
    create_file(file_path, "content")

    def mock_open(*args, **kwargs):
        raise IOError("Permission denied")

    monkeypatch.setattr("builtins.open", mock_open)

    preview = build_write_preview(str(tmp_path), "unreadable_file.txt", "new content")

    assert "Could not read existing file for preview: Permission denied" in preview


def test_parse_unified_diff_basic_replacement():
    diff = """--- a.py (current)
+++ a.py (proposed)
@@ -1,3 +1,3 @@
 line1
-line2
+line2 changed
 line3"""

    parsed_diff = parse_unified_diff(diff)
    lines = parsed_diff.lines

    assert len(lines) == 7
    assert lines[0] == ParsedDiffLine(kind="meta", text="--- a.py (current)")
    assert lines[1] == ParsedDiffLine(kind="meta", text="+++ a.py (proposed)")
    assert lines[2] == ParsedDiffLine(kind="hunk", text="@@ -1,3 +1,3 @@")
    assert lines[3] == ParsedDiffLine(kind="context", text="line1", old_lineno=1, new_lineno=1)
    assert lines[4] == ParsedDiffLine(kind="remove", text="line2", old_lineno=2, new_lineno=None)
    assert lines[5] == ParsedDiffLine(
        kind="add", text="line2 changed", old_lineno=None, new_lineno=2
    )
    assert lines[6] == ParsedDiffLine(kind="context", text="line3", old_lineno=3, new_lineno=3)


def test_parse_unified_diff_pure_add():
    diff = """--- a.py (current)
+++ a.py (proposed)
@@ -1,2 +1,3 @@
 line1
+line_added
 line2"""

    parsed_diff = parse_unified_diff(diff)
    lines = parsed_diff.lines

    assert len(lines) == 6
    assert lines[0] == ParsedDiffLine(kind="meta", text="--- a.py (current)")
    assert lines[1] == ParsedDiffLine(kind="meta", text="+++ a.py (proposed)")
    assert lines[2] == ParsedDiffLine(kind="hunk", text="@@ -1,2 +1,3 @@")
    assert lines[3] == ParsedDiffLine(kind="context", text="line1", old_lineno=1, new_lineno=1)
    assert lines[4] == ParsedDiffLine(kind="add", text="line_added", old_lineno=None, new_lineno=2)
    assert lines[5] == ParsedDiffLine(kind="context", text="line2", old_lineno=2, new_lineno=3)


def test_parse_unified_diff_pure_remove():
    diff = """--- a.py (current)
+++ a.py (proposed)
@@ -1,3 +1,2 @@
 line1
-line_removed
 line2"""

    parsed_diff = parse_unified_diff(diff)
    lines = parsed_diff.lines

    assert len(lines) == 6
    assert lines[0] == ParsedDiffLine(kind="meta", text="--- a.py (current)")
    assert lines[1] == ParsedDiffLine(kind="meta", text="+++ a.py (proposed)")
    assert lines[2] == ParsedDiffLine(kind="hunk", text="@@ -1,3 +1,2 @@")
    assert lines[3] == ParsedDiffLine(kind="context", text="line1", old_lineno=1, new_lineno=1)
    assert lines[4] == ParsedDiffLine(
        kind="remove", text="line_removed", old_lineno=2, new_lineno=None
    )
    assert lines[5] == ParsedDiffLine(kind="context", text="line2", old_lineno=3, new_lineno=2)


def test_parse_unified_diff_multi_line_replace():
    diff = """--- a.py (current)
+++ a.py (proposed)
@@ -1,4 +1,4 @@
 line1
-line2_removed
-line3_removed
+line2_added
+line3_added
 line4"""

    parsed_diff = parse_unified_diff(diff)
    lines = parsed_diff.lines

    assert len(lines) == 9
    assert lines[0] == ParsedDiffLine(kind="meta", text="--- a.py (current)")
    assert lines[1] == ParsedDiffLine(kind="meta", text="+++ a.py (proposed)")
    assert lines[2] == ParsedDiffLine(kind="hunk", text="@@ -1,4 +1,4 @@")
    assert lines[3] == ParsedDiffLine(kind="context", text="line1", old_lineno=1, new_lineno=1)
    assert lines[4] == ParsedDiffLine(
        kind="remove", text="line2_removed", old_lineno=2, new_lineno=None
    )
    assert lines[5] == ParsedDiffLine(
        kind="remove", text="line3_removed", old_lineno=3, new_lineno=None
    )
    assert lines[6] == ParsedDiffLine(kind="add", text="line2_added", old_lineno=None, new_lineno=2)
    assert lines[7] == ParsedDiffLine(kind="add", text="line3_added", old_lineno=None, new_lineno=3)
    assert lines[8] == ParsedDiffLine(kind="context", text="line4", old_lineno=4, new_lineno=4)


def test_build_connector_write_preview_for_servicedesk_draft():
    preview = build_connector_write_preview(
        "servicedesk_add_request_draft",
        {
            "request_id": "55776",
            "subject": "Re: Test subject",
            "description": "Hello from draft",
            "draft_type": "reply",
        },
    )

    assert preview is not None
    assert "# ServiceDesk draft reply" in preview
    assert "- **Action:** Save draft reply" in preview
    assert "- **Ticket:** 55776" in preview
    assert "- **Type:** reply" in preview
    assert "## Subject" in preview
    assert "Re: Test subject" in preview
    assert "## Draft body" in preview
    assert "Hello from draft" in preview
    assert "## Safety" in preview
    assert "This will save a draft in ServiceDesk Plus." in preview
    assert "It will not send the reply to the requester." in preview


def test_build_connector_write_preview_for_servicedesk_internal_note():
    preview = build_connector_write_preview(
        "servicedesk_add_request_note",
        {
            "request_id": "55948",
            "description": (
                "Read-only mailbox inspection completed for `user@example.com`.\n\n"
                "Findings:\n- Mailbox exists: yes\n\n"
                "Scope:\n- No changes were made."
            ),
            "show_to_requester": False,
        },
    )

    assert preview is not None
    assert "# ServiceDesk internal note" in preview
    assert "- **Action:** Add internal note" in preview
    assert "- **Ticket:** 55948" in preview
    assert "- **Visibility:** internal-only" in preview
    assert "## Note body" in preview
    assert "Mailbox exists: yes" in preview
    assert "No changes were made." in preview
    # Local draft metadata wording must not leak into the approval preview.
    assert "Local draft metadata" not in preview
    assert "Generated locally by Work Copilot" not in preview
    assert "## Safety" in preview
    assert "This will post an internal note to ServiceDesk Plus." in preview
    assert "It will not send a reply to the requester." in preview


def test_build_connector_write_preview_returns_none_for_unknown_tool():
    preview = build_connector_write_preview(
        "some_other_tool",
        {
            "request_id": "55776",
        },
    )

    assert preview is None


def test_build_exec_preview_for_bash():
    preview = build_exec_preview(
        "bash",
        {
            "command": "uv run pytest",
            "cwd": ".",
            "timeout_seconds": 120,
        },
        "/workspace",
    )

    assert preview is not None
    assert "# Shell command" in preview
    assert "```bash" in preview
    assert "uv run pytest" in preview
    assert "## Working directory" in preview
    assert "`." in preview
    assert "## Timeout" in preview
    assert "`120s`" in preview
    assert "This command will execute locally if approved." in preview


def test_build_exec_preview_returns_none_for_unknown_exec_tool():
    preview = build_exec_preview(
        "some_other_exec_tool",
        {"command": "echo nope"},
        "/workspace",
    )

    assert preview is None


def test_build_write_preview_new_yaml_file_is_unified_diff(tmp_path):
    new_content = "\n".join(
        [
            "id: active_directory.group.add_member",
            "family: active_directory.group",
            "required_inputs:",
            "  - name: target_user",
            "    required: true",
        ]
    )

    preview = build_write_preview(
        str(tmp_path),
        "skills/definitions/active_directory.group.add_member.yaml",
        new_content,
    )

    assert is_unified_diff_preview(preview)
    assert "--- /dev/null" in preview
    assert "+++ skills/definitions/active_directory.group.add_member.yaml (proposed)" in preview
    assert "+id: active_directory.group.add_member" in preview
    assert "+required_inputs:" in preview
    assert "+  - name: target_user" in preview