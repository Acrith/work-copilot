import subprocess

import pytest

from functions.git_diff_file import git_diff_file


@pytest.fixture
def setup_git_repo(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
    )

    (tmp_path / "test_file.txt").write_text("initial content", encoding="utf-8")
    subprocess.run(["git", "add", "test_file.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True)

    return tmp_path


def test_git_diff_file_modified(setup_git_repo):
    repo_path = setup_git_repo
    (repo_path / "test_file.txt").write_text("modified content", encoding="utf-8")

    result = git_diff_file(str(repo_path), "test_file.txt")

    assert "diff --git" in result
    assert "--- a/test_file.txt" in result
    assert "+++ b/test_file.txt" in result
    assert "-initial content" in result
    assert "+modified content" in result


def test_git_diff_file_clean(setup_git_repo):
    repo_path = setup_git_repo

    result = git_diff_file(str(repo_path), "test_file.txt")

    assert result == 'No diff for "test_file.txt".'


def test_git_diff_file_non_existent_file(setup_git_repo):
    repo_path = setup_git_repo

    result = git_diff_file(str(repo_path), "non_existent.txt")

    assert result == 'No diff for "non_existent.txt".'


def test_git_diff_file_non_git_repo(tmp_path):
    result = git_diff_file(str(tmp_path), "test_file.txt")

    assert result == "Error: Not a git repository."


def test_git_diff_file_rejects_path_traversal(tmp_path):
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret", encoding="utf-8")

    working_directory = tmp_path / "repo"
    working_directory.mkdir()

    result = git_diff_file(str(working_directory), "../outside.txt")

    assert (
        result == 'Error: Cannot inspect diff for "../outside.txt" as it is outside the '
        "permitted working directory"
    )


def test_git_diff_file_git_not_installed(monkeypatch, tmp_path):
    def mock_run(*args, **kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(subprocess, "run", mock_run)

    result = git_diff_file(str(tmp_path), "test_file.txt")

    assert result == "Error: Git command not found. Is Git installed and in PATH?"
