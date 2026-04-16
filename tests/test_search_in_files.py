import os

import pytest

from functions.search_in_files import search_in_files


@pytest.fixture
def setup_files(tmp_path):
    # Create a simple file
    (tmp_path / "file1.txt").write_text("This is a test file.")
    # Create another file with the query
    (tmp_path / "file2.txt").write_text("Another file with the query text.")
    # Create a nested directory and file
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "file3.txt").write_text("File in a subdirectory with query text.")
    # Create a file with no match
    (tmp_path / "nomatch.txt").write_text("This file has no matching content.")
    # Create skipped directories and files
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("query text in git config")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cache.pyc").write_text("query text in pycache")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "activate").write_text("query text in venv")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "some_module.js").write_text("query text in node_modules")
    (tmp_path / ".pytest_cache").mkdir()
    (tmp_path / ".pytest_cache" / "some_cache_file.txt").write_text("query text in pytest_cache")
    # Create an unreadable file (simulated by non-utf8 content)
    (tmp_path / "unreadable.txt").write_bytes(b"\x80\x81")
    # Create a file with a complex query
    (tmp_path / "complex_query.md").write_text("Here's a complex query string with multiple words.")

    return tmp_path


def test_one_matching_file(setup_files):
    working_directory = setup_files
    query = "test file"
    result = search_in_files(working_directory, query)
    assert result == "file1.txt"


def test_multiple_matching_files(setup_files):
    working_directory = setup_files
    query = "query text"
    result = search_in_files(working_directory, query)
    expected_matches = sorted(["file2.txt", "subdir/file3.txt"])
    actual_matches = sorted(result.splitlines())
    assert actual_matches == expected_matches


def test_no_matches(setup_files):
    working_directory = setup_files
    query = "nonexistent_query"
    result = search_in_files(working_directory, query)
    assert result == "No matches found"


def test_nested_subdirectory_matches(setup_files):
    working_directory = setup_files
    query = "subdirectory with query"
    result = search_in_files(working_directory, query)
    assert result == "subdir/file3.txt"


def test_skipped_directories(setup_files):
    working_directory = setup_files
    query = "query text in"
    result = search_in_files(working_directory, query)
    # Assert that files in skipped directories are NOT found
    assert result == "No matches found"
    assert ".git/config" not in result
    assert "__pycache__/cache.pyc" not in result
    assert ".venv/activate" not in result
    assert "node_modules/some_module.js" not in result
    assert ".pytest_cache/some_cache_file.txt" not in result


def test_unreadable_or_non_utf8_files_skipped(setup_files):
    working_directory = setup_files
    # The 'unreadable.txt' contains non-UTF-8 bytes.
    # We expect it to be skipped and not raise an error.
    # No matching content is expected from this file, so a query that would
    # otherwise match elsewhere should still return only the other matches.
    query = "test file"
    result = search_in_files(working_directory, query)
    assert result == "file1.txt"
    assert "unreadable.txt" not in result


def test_returning_relative_file_paths(setup_files):
    working_directory = setup_files
    query = "subdirectory"
    result = search_in_files(working_directory, query)
    assert result == "subdir/file3.txt"
    assert not os.path.isabs(result)


def test_empty_query(setup_files):
    working_directory = setup_files
    query = ""
    result = search_in_files(working_directory, query)
    # An empty query should match all readable files.
    expected_matches = sorted(
        [
            "file1.txt",
            "file2.txt",
            "subdir/file3.txt",
            "nomatch.txt",
            "complex_query.md",
        ]
    )
    actual_matches = sorted(result.splitlines())
    assert actual_matches == expected_matches


def test_complex_query(setup_files):
    working_directory = setup_files
    query = "complex query string with multiple words"
    result = search_in_files(working_directory, query)
    assert result == "complex_query.md"
