from functions.get_file_content import get_file_content

MAX_CHARS = 10000


def test_existing_file(tmp_path):
    # Create a dummy file
    file_content = "This is a test file content."
    file_path = tmp_path / "test_file.txt"
    file_path.write_text(file_content)

    # Test reading the existing file
    result = get_file_content(str(tmp_path), "test_file.txt")
    assert result == file_content


def test_missing_file(tmp_path):
    # Test reading a non-existent file
    result = get_file_content(str(tmp_path), "non_existent_file.txt")
    assert "Error: File not found or is not a regular file" in result


def test_nested_file(tmp_path):
    # Create a nested directory and file
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    file_content = "Content of the nested file."
    file_path = nested_dir / "nested_file.txt"
    file_path.write_text(file_content)

    # Test reading the nested file
    result = get_file_content(str(tmp_path), "nested/nested_file.txt")
    assert result == file_content


def test_path_traversal_outside_working_directory(tmp_path):
    # Create a file outside the working directory (tmp_path)
    # This simulates a file that should not be accessible via path traversal
    parent_dir = tmp_path.parent
    malicious_file = parent_dir / "malicious_file.txt"
    malicious_file.write_text("Secret content")

    # Attempt to read the file using path traversal
    result = get_file_content(str(tmp_path), "../malicious_file.txt")
    assert "Error: Cannot read" in result
    assert "outside the permitted working directory" in result


def test_truncation_behavior(tmp_path):
    # Create a file with content larger than MAX_CHARS
    long_content = "a" * (MAX_CHARS + 100)
    file_path = tmp_path / "long_file.txt"
    file_path.write_text(long_content)

    # Test that the content is truncated
    result = get_file_content(str(tmp_path), "long_file.txt")
    expected_truncated_content = (
        long_content[:MAX_CHARS]
        + f'\n\n[...File "long_file.txt" truncated at {MAX_CHARS} characters]'
    )
    assert result == expected_truncated_content


def test_empty_file(tmp_path):
    # Create an empty file
    file_path = tmp_path / "empty.txt"
    file_path.write_text("")

    # Test reading the empty file
    result = get_file_content(str(tmp_path), "empty.txt")
    assert result == ""


def test_file_in_subdirectory_with_same_name(tmp_path):
    # Create a file in the root and a subdirectory with a file of the same name
    (tmp_path / "dir_a").mkdir()
    (tmp_path / "dir_b").mkdir()

    (tmp_path / "dir_a" / "file.txt").write_text("content A")
    (tmp_path / "dir_b" / "file.txt").write_text("content B")

    # Test reading the file in dir_a
    result_a = get_file_content(str(tmp_path), "dir_a/file.txt")
    assert result_a == "content A"

    # Test reading the file in dir_b
    result_b = get_file_content(str(tmp_path), "dir_b/file.txt")
    assert result_b == "content B"


def test_invalid_working_directory(tmp_path):
    # Test with a non-existent working directory
    non_existent_dir = tmp_path / "non_existent_dir"
    result = get_file_content(str(non_existent_dir), "some_file.txt")
    assert "Error:" in result
    assert "some_file.txt" in result


def test_file_with_special_characters_in_name(tmp_path):
    # Create a file with special characters in its name
    special_name = "file-with spaces&!@#.txt"
    file_path = tmp_path / special_name
    file_path.write_text("special content")

    # Test reading the file
    result = get_file_content(str(tmp_path), special_name)
    assert result == "special content"
