# tests/test_run_shell_command.py
import subprocess

from functions.run_shell_command import run_shell_command


def test_run_shell_command_success_in_workspace_root(tmp_path, monkeypatch):
    captured = {}

    def fake_run(argv, cwd, capture_output, text, timeout, check):
        captured["argv"] = argv
        captured["cwd"] = cwd
        captured["capture_output"] = capture_output
        captured["text"] = text
        captured["timeout"] = timeout
        captured["check"] = check
        return subprocess.CompletedProcess(argv, 0, "ok\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_shell_command(str(tmp_path), "git status")

    assert captured["argv"] == ["git", "status"]
    assert captured["cwd"] == str(tmp_path)
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["timeout"] == 30
    assert captured["check"] is False

    assert "Bash command: git status" in result
    assert "Cwd: ." in result
    assert "Exit code: 0" in result
    assert "--- stdout ---\nok\n" in result
    assert "--- stderr ---\n(empty)" in result


def test_run_shell_command_success_in_subdirectory(tmp_path, monkeypatch):
    subdir = tmp_path / "tests"
    subdir.mkdir()

    captured = {}

    def fake_run(argv, cwd, capture_output, text, timeout, check):
        captured["cwd"] = cwd
        return subprocess.CompletedProcess(argv, 0, "done\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_shell_command(str(tmp_path), "pytest", cwd="tests", timeout_seconds=10)

    assert captured["cwd"] == str(subdir)
    assert "Bash command: pytest" in result
    assert "Cwd: tests" in result
    assert "Exit code: 0" in result


def test_run_shell_command_nonzero_exit(tmp_path, monkeypatch):
    def fake_run(argv, cwd, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(argv, 3, "", "failed\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_shell_command(str(tmp_path), "python bad_script.py")

    assert "Bash command: python bad_script.py" in result
    assert "Exit code: 3" in result
    assert "--- stdout ---\n(empty)" in result
    assert "--- stderr ---\nfailed\n" in result


def test_run_shell_command_timeout(tmp_path, monkeypatch):
    def fake_run(argv, cwd, capture_output, text, timeout, check):
        raise subprocess.TimeoutExpired(
            argv, timeout, output="partial out\n", stderr="partial err\n"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_shell_command(str(tmp_path), "pytest", timeout_seconds=1)

    assert "Bash timed out after 1s" in result
    assert "Command: pytest" in result
    assert "Cwd: ." in result
    assert "--- stdout ---\npartial out\n" in result
    assert "--- stderr ---\npartial err\n" in result


def test_run_shell_command_empty_command(tmp_path):
    result = run_shell_command(str(tmp_path), "")

    assert result == "Bash error: command cannot be empty."


def test_run_shell_command_parse_error(tmp_path):
    result = run_shell_command(str(tmp_path), '"unterminated')

    assert "Bash error: invalid command syntax:" in result


def test_run_shell_command_denies_outside_workspace_cwd(tmp_path, monkeypatch):
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_shell_command(str(tmp_path), "git status", cwd="../outside")

    assert 'Bash denied: cwd "../outside" is outside the workspace.' in result
    assert called is False


def test_run_shell_command_denies_protected_cwd(tmp_path, monkeypatch):
    protected = tmp_path / ".git"
    protected.mkdir()

    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_shell_command(str(tmp_path), "git status", cwd=".git")

    assert 'Bash denied: cwd ".git" is a protected path.' in result
    assert called is False


def test_run_shell_command_truncates_large_output(tmp_path, monkeypatch):
    big_stdout = "a" * 5000
    big_stderr = "b" * 5000

    def fake_run(argv, cwd, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(argv, 0, big_stdout, big_stderr)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_shell_command(str(tmp_path), "git status")

    assert "--- stdout ---\n" + ("a" * 4000) in result
    assert ("a" * 4001) not in result
    assert "--- stderr ---\n" + ("b" * 4000) in result
    assert ("b" * 4001) not in result


def test_run_shell_command_rejects_negative_timeout(tmp_path):
    result = run_shell_command(str(tmp_path), "git status", timeout_seconds=-5)

    assert result == "Bash error: timeout_seconds must be greater than 0."
