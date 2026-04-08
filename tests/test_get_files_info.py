from functions.get_files_info import get_files_info


def test_get_files_info_empty_directory(tmp_path):
    result = get_files_info(str(tmp_path))
    assert result == ""


def test_get_files_info_files_and_directories(tmp_path):
    (tmp_path / "file1.txt").write_text("content1")
    (tmp_path / "dir1").mkdir()
    (tmp_path / "dir1" / "file2.txt").write_text("content2")

    result = get_files_info(str(tmp_path))
    lines = sorted(result.splitlines())
    expected_lines = sorted([
        f"- dir1: file_size={(tmp_path / 'dir1').stat().st_size} bytes, is_dir=True",
        f"- file1.txt: file_size={(tmp_path / 'file1.txt').stat().st_size} bytes, is_dir=False",
    ])
    assert lines == expected_lines


def test_get_files_info_specific_directory(tmp_path):
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "subfile1.txt").write_text("subcontent1")

    result = get_files_info(str(tmp_path), "subdir")
    expected_line = f"- subfile1.txt: file_size={(subdir / 'subfile1.txt').stat().st_size} bytes, is_dir=False"
    assert result == expected_line


def test_get_files_info_non_existent_directory(tmp_path):
    result = get_files_info(str(tmp_path), "nonexistent_dir")
    assert 'Error: "nonexistent_dir"' in result


def test_get_files_info_invalid_path(tmp_path):
    (tmp_path / "file1.txt").write_text("content1")

    result = get_files_info(str(tmp_path), "file1.txt")
    assert 'Error: "file1.txt"' in result