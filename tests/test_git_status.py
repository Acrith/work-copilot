import subprocess
from pathlib import Path

from functions.git_status import git_status


def init_git_repo(repo_path: Path):
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "Initial commit"],
        cwd=repo_path,
        check=True,
    )


def test_git_status_success_clean_repo(tmp_path: Path):
    init_git_repo(tmp_path)

    status = git_status(str(tmp_path))

    lines = status.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("## ")


def test_git_status_not_a_git_repository(tmp_path: Path):
    status = git_status(str(tmp_path))
    assert status.startswith("Error: Not a git repository.")


def test_git_status_modified_tracked_file(tmp_path: Path):
    init_git_repo(tmp_path)
    (tmp_path / "test_file.txt").write_text("initial content")
    subprocess.run(["git", "add", "test_file.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "Add test_file"], cwd=tmp_path, check=True)
    (tmp_path / "test_file.txt").write_text("modified content")
    status = git_status(str(tmp_path))
    assert " M test_file.txt" in status


def test_git_status_untracked_file(tmp_path: Path):
    init_git_repo(tmp_path)
    (tmp_path / "new_file.txt").write_text("untracked content")
    status = git_status(str(tmp_path))
    assert "?? new_file.txt" in status


def test_git_status_git_not_installed(monkeypatch, tmp_path: Path):
    def mock_subprocess_run(*args, **kwargs):
        if "git" in args[0]:
            raise FileNotFoundError
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
    status = git_status(str(tmp_path))
    assert status == "Error: Git command not found. Is Git installed and in PATH?"
