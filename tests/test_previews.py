from previews import build_write_preview


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

    assert 'New file: "new_file.txt"' in preview
    assert "Hello, new file!" in preview


def test_build_write_preview_new_empty_file(tmp_path):
    preview = build_write_preview(str(tmp_path), "empty_new_file.txt", "")

    assert 'New file: "empty_new_file.txt"' in preview
    assert "<empty file>" in preview


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
