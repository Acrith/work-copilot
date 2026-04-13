from functions.update_file import update_file


def test_update_single_match_success(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    result = update_file(
        str(tmp_path),
        "sample.txt",
        "beta",
        "delta",
    )

    assert result == 'Successfully updated "sample.txt"'
    assert file_path.read_text(encoding="utf-8") == "alpha\ndelta\ngamma\n"


def test_update_missing_target_text(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    result = update_file(
        str(tmp_path),
        "sample.txt",
        "not-here",
        "delta",
    )

    assert (
        result
        == 'Error: Target text not found in "sample.txt". '
        "Read the file first and retry with a more exact old_text."
    )
    assert file_path.read_text(encoding="utf-8") == "alpha\nbeta\ngamma\n"


def test_update_multiple_matches_fails(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("beta\nalpha\nbeta\n", encoding="utf-8")

    result = update_file(
        str(tmp_path),
        "sample.txt",
        "beta",
        "delta",
    )

    assert (
        result
        == 'Error: Found 2 matches for old_text in "sample.txt". '
        "Provide a more specific old_text."
    )
    assert file_path.read_text(encoding="utf-8") == "beta\nalpha\nbeta\n"


def test_update_rejects_empty_old_text(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("hello", encoding="utf-8")

    result = update_file(
        str(tmp_path),
        "sample.txt",
        "",
        "world",
    )

    assert result == "Error: old_text must not be empty"
    assert file_path.read_text(encoding="utf-8") == "hello"


def test_update_allows_empty_new_text_for_deletion(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    result = update_file(
        str(tmp_path),
        "sample.txt",
        "beta\n",
        "",
    )

    assert result == 'Successfully updated "sample.txt"'
    assert file_path.read_text(encoding="utf-8") == "alpha\ngamma\n"


def test_update_rejects_path_traversal(tmp_path):
    working_directory = tmp_path / "subdir"
    working_directory.mkdir()

    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret", encoding="utf-8")

    result = update_file(
        str(working_directory),
        "../outside.txt",
        "secret",
        "changed",
    )

    assert (
        result
        == 'Error: Cannot update "../outside.txt" as it is outside the permitted '
        "working directory"
    )
    assert outside_file.read_text(encoding="utf-8") == "secret"


def test_update_rejects_directory_target(tmp_path):
    (tmp_path / "folder").mkdir()

    result = update_file(
        str(tmp_path),
        "folder",
        "a",
        "b",
    )

    assert result == 'Error: Cannot update "folder" as it is a directory'


def test_update_missing_file(tmp_path):
    result = update_file(
        str(tmp_path),
        "missing.txt",
        "a",
        "b",
    )

    assert (
        result
        == 'Error: File not found: "missing.txt". '
        "Use find_file or get_files_info to locate the correct path."
    )