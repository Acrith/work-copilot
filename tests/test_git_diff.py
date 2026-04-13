import subprocess
from pathlib import Path

from functions.git_diff import git_diff


def init_git_repo(repo_path: Path):
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "Initial commit"],
        cwd=repo_path,
        check=True,
    )


def test_git_diff_modified_tracked_file(tmp_path: Path):
    init_git_repo(tmp_path)
    (tmp_path / "test_file.txt").write_text("initial content")
    subprocess.run(["git", "add", "test_file.txt"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add test_file"], cwd=tmp_path, check=True
    )

    (tmp_path / "test_file.txt").write_text("modified content")

    diff = git_diff(str(tmp_path))

    assert "diff --git" in diff
    assert "--- a/test_file.txt" in diff
    assert "+++ b/test_file.txt" in diff
    assert "-initial content" in diff
    assert "+modified content" in diff


def test_git_diff_clean_repo(tmp_path: Path):
    init_git_repo(tmp_path)

    diff = git_diff(str(tmp_path))

    assert diff == "No diff in repository."


def test_git_diff_not_a_git_repository(tmp_path: Path):
    diff = git_diff(str(tmp_path))

    assert diff == "Error: Not a git repository."


def test_git_diff_git_not_installed(monkeypatch, tmp_path: Path):
    def mock_subprocess_run(*args, **kwargs):
        if "git" in args[0]:
            raise FileNotFoundError
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    diff = git_diff(str(tmp_path))

    assert diff == "Error: Git command not found. Is Git installed and in PATH?"