import os
import pytest
from functions.write_file import write_file

def test_write_new_file_success(tmp_path):
    working_directory = tmp_path
    file_path = "new_file.txt"
    content = "Hello, world!"
    expected_output = f'Successfully wrote to "{file_path}" (13 characters written)'

    result = write_file(str(working_directory), file_path, content)
    assert result == expected_output

    target_file = tmp_path / file_path
    assert target_file.exists()
    assert target_file.read_text() == content

def test_overwrite_existing_file_success(tmp_path):
    working_directory = tmp_path
    file_path = "existing_file.txt"
    initial_content = "Old content."
    updated_content = "New content here."
    expected_output = f'Successfully wrote to "{file_path}" (17 characters written)'

    # Create the initial file
    initial_file = tmp_path / file_path
    initial_file.write_text(initial_content)

    result = write_file(str(working_directory), file_path, updated_content)
    assert result == expected_output

    assert initial_file.exists()
    assert initial_file.read_text() == updated_content

def test_write_to_nested_path(tmp_path):
    working_directory = tmp_path
    file_path = "nested/dir/deep_file.txt"
    content = "Content in a nested path."
    expected_output = f'Successfully wrote to "{file_path}" (25 characters written)'

    result = write_file(str(working_directory), file_path, content)
    assert result == expected_output

    target_file = tmp_path / file_path
    assert target_file.exists()
    assert target_file.read_text() == content
    assert target_file.parent.exists()
    assert target_file.parent.name == "dir"
    assert target_file.parent.parent.name == "nested"

def test_fail_path_traversal_outside_working_directory(tmp_path):
    working_directory = tmp_path / "subdir"
    # Ensure subdir exists for os.path.abspath to resolve correctly relative to it
    working_directory.mkdir() 

    file_path = "../outside.txt"
    content = "This should not be written."
    expected_error = f'Error: Cannot write to "{file_path}" as it is outside the permitted working directory'

    result = write_file(str(working_directory), file_path, content)
    assert result == expected_error

    outside_file = tmp_path / "outside.txt"
    assert not outside_file.exists()

def test_write_empty_content(tmp_path):
    working_directory = tmp_path
    file_path = "empty.txt"
    content = ""
    expected_output = f'Successfully wrote to "{file_path}" (0 characters written)'

    result = write_file(str(working_directory), file_path, content)
    assert result == expected_output

    target_file = tmp_path / file_path
    assert target_file.exists()
    assert target_file.read_text() == ""

def test_write_content_with_special_characters_and_newlines(tmp_path):
    working_directory = tmp_path
    file_path = "special_content.txt"
    content = "Line 1\nLine 2 with special chars: !@#$%^&*()_+-=[]{}|;:'\",.<>/?`~ and unicode: éàçü"
    expected_output = f'Successfully wrote to "{file_path}" ({len(content)} characters written)'

    result = write_file(str(working_directory), file_path, content)
    assert result == expected_output

    target_file = tmp_path / file_path
    assert target_file.exists()
    assert target_file.read_text() == content

def test_write_to_non_existent_working_directory(tmp_path):
    # This test verifies the current behavior: if working_directory does not exist,
    # os.makedirs will create it if needed during the file creation process.
    non_existent_dir_name = "non_existent_work_dir"
    working_directory = tmp_path / non_existent_dir_name
    file_path = "file_in_non_existent.txt"
    content = "Content for non-existent working dir."
    expected_output = f'Successfully wrote to "{file_path}" (37 characters written)'

    result = write_file(str(working_directory), file_path, content)
    assert result == expected_output

    # The file should be created inside the newly created working_directory
    target_file = working_directory / file_path
    assert target_file.exists()
    assert target_file.read_text() == content
    assert working_directory.is_dir()

def test_fail_when_writing_to_an_existing_directory(tmp_path):
    working_directory = tmp_path
    dir_path = "my_directory"
    
    # Create a directory that we will try to write into as if it were a file
    (tmp_path / dir_path).mkdir()

    content = "This should fail."
    expected_error = f'Error: Cannot write to "{dir_path}" as it is a directory'

    result = write_file(str(working_directory), dir_path, content)
    assert result == expected_error

    # Ensure no file was created with the directory's name
    target_file = tmp_path / dir_path
    assert target_file.is_dir()
    # If the function tried to write to it, it would raise an exception,
    # but the check `if os.path.isdir(target_file)` should prevent it and return the error string.
