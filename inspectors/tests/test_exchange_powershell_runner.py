import subprocess

import pytest

from inspectors.exchange_command_runner import ExchangePowerShellCommand
from inspectors.exchange_config import (
    ExchangeInspectorBackend,
    ExchangeInspectorConfigError,
    ExchangeInspectorRuntimeConfig,
)
from inspectors.exchange_powershell_runner import (
    ExchangePowerShellRunnerConfig,
    ExchangePowerShellSubprocessRunner,
    validate_exchange_powershell_runner_config,
)


def make_runtime_config(
    *,
    backend: ExchangeInspectorBackend = ExchangeInspectorBackend.EXCHANGE_ONLINE_POWERSHELL,
    allow_real_external_calls: bool = True,
) -> ExchangeInspectorRuntimeConfig:
    return ExchangeInspectorRuntimeConfig(
        backend=backend,
        allow_real_external_calls=allow_real_external_calls,
    )


def make_runner(*, executable: str = "pwsh", timeout_seconds: int = 60):
    return ExchangePowerShellSubprocessRunner(
        ExchangePowerShellRunnerConfig(
            runtime_config=make_runtime_config(),
            executable=executable,
            timeout_seconds=timeout_seconds,
        )
    )


def test_validate_exchange_powershell_runner_config_allows_explicit_real_backend():
    config = ExchangePowerShellRunnerConfig(
        runtime_config=make_runtime_config(),
    )

    validate_exchange_powershell_runner_config(config)


def test_exchange_powershell_runner_requires_exchange_backend():
    config = ExchangePowerShellRunnerConfig(
        runtime_config=make_runtime_config(
            backend=ExchangeInspectorBackend.MOCK,
            allow_real_external_calls=True,
        ),
    )

    with pytest.raises(
        ExchangeInspectorConfigError,
        match="requires exchange_online_powershell backend",
    ):
        ExchangePowerShellSubprocessRunner(config)


def test_exchange_powershell_runner_requires_real_external_calls_allowed():
    config = ExchangePowerShellRunnerConfig(
        runtime_config=make_runtime_config(
            allow_real_external_calls=False,
        ),
    )

    with pytest.raises(
        ExchangeInspectorConfigError,
        match="requires real external calls",
    ):
        ExchangePowerShellSubprocessRunner(config)


def test_exchange_powershell_runner_rejects_empty_executable():
    config = ExchangePowerShellRunnerConfig(
        runtime_config=make_runtime_config(),
        executable="   ",
    )

    with pytest.raises(
        ExchangeInspectorConfigError,
        match="executable cannot be empty",
    ):
        ExchangePowerShellSubprocessRunner(config)


def test_exchange_powershell_runner_rejects_non_positive_timeout():
    config = ExchangePowerShellRunnerConfig(
        runtime_config=make_runtime_config(),
        timeout_seconds=0,
    )

    with pytest.raises(
        ExchangeInspectorConfigError,
        match="timeout must be greater than zero",
    ):
        ExchangePowerShellSubprocessRunner(config)


def test_exchange_powershell_runner_runs_allowlisted_command(monkeypatch):
    captured = {}

    def fake_run(argv, capture_output, text, timeout, check):
        captured["argv"] = argv
        captured["capture_output"] = capture_output
        captured["text"] = text
        captured["timeout"] = timeout
        captured["check"] = check

        return subprocess.CompletedProcess(
            argv,
            0,
            '{"DisplayName":"Example User","PrimarySmtpAddress":"user@example.com"}',
            "",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = make_runner(timeout_seconds=42)
    result = runner.run(
        ExchangePowerShellCommand(
            name="Get-EXOMailbox",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert result.command == "Get-EXOMailbox"
    assert result.ok is True
    assert result.error is None
    assert result.data == {
        "DisplayName": "Example User",
        "PrimarySmtpAddress": "user@example.com",
    }

    assert captured["argv"][0] == "pwsh"
    assert "-NoProfile" in captured["argv"]
    assert "-NonInteractive" in captured["argv"]
    assert "-Command" in captured["argv"]
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["timeout"] == 42
    assert captured["check"] is False


def test_exchange_powershell_runner_uses_configured_executable(monkeypatch):
    captured = {}

    def fake_run(argv, capture_output, text, timeout, check):
        captured["argv"] = argv

        return subprocess.CompletedProcess(argv, 0, "{}", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = make_runner(executable="/usr/bin/pwsh")
    runner.run(
        ExchangePowerShellCommand(
            name="Get-EXOMailbox",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert captured["argv"][0] == "/usr/bin/pwsh"


def test_exchange_powershell_runner_accepts_list_json(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(
            argv,
            0,
            '[{"DisplayName":"Example User","ItemCount":123}]',
            "",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = make_runner()
    result = runner.run(
        ExchangePowerShellCommand(
            name="Get-EXOMailboxStatistics",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert result.ok is True
    assert result.data == [
        {
            "DisplayName": "Example User",
            "ItemCount": 123,
        }
    ]


def test_exchange_powershell_runner_accepts_empty_stdout_as_none(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = make_runner()
    result = runner.run(
        ExchangePowerShellCommand(
            name="Get-EXOMailbox",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert result.ok is True
    assert result.data is None


def test_exchange_powershell_runner_rejects_forbidden_command_before_subprocess(monkeypatch):
    called = False

    def fake_run(argv, capture_output, text, timeout, check):
        nonlocal called
        called = True
        return subprocess.CompletedProcess(argv, 0, "{}", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = make_runner()

    with pytest.raises(
        ValueError,
        match="forbidden for inspectors",
    ):
        runner.run(
            ExchangePowerShellCommand(
                name="Set-Mailbox",
                parameters={"Identity": "user@example.com"},
            )
        )

    assert called is False


def test_exchange_powershell_runner_returns_error_for_nonzero_exit(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(
            argv,
            1,
            "",
            "Authentication failed.",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = make_runner()
    result = runner.run(
        ExchangePowerShellCommand(
            name="Get-EXOMailbox",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert result.ok is False
    assert result.error == (
        "Exchange PowerShell command failed with exit code 1: Authentication failed."
    )


def test_exchange_powershell_runner_uses_stdout_when_stderr_is_empty(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(
            argv,
            1,
            "Failure details from stdout.",
            "",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = make_runner()
    result = runner.run(
        ExchangePowerShellCommand(
            name="Get-EXOMailbox",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert result.ok is False
    assert result.error == (
        "Exchange PowerShell command failed with exit code 1: "
        "Failure details from stdout."
    )


def test_exchange_powershell_runner_returns_error_for_invalid_json(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(argv, 0, "not-json", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = make_runner()
    result = runner.run(
        ExchangePowerShellCommand(
            name="Get-EXOMailbox",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert result.ok is False
    assert result.error == "Exchange PowerShell returned invalid JSON output."


def test_exchange_powershell_runner_returns_error_for_unsupported_json_shape(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(argv, 0, '"plain string"', "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = make_runner()
    result = runner.run(
        ExchangePowerShellCommand(
            name="Get-EXOMailbox",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert result.ok is False
    assert result.error == "Exchange PowerShell returned unsupported JSON data shape."


def test_exchange_powershell_runner_returns_error_for_timeout(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = make_runner(timeout_seconds=5)
    result = runner.run(
        ExchangePowerShellCommand(
            name="Get-EXOMailbox",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert result.ok is False
    assert result.error == "Exchange PowerShell command timed out after 5 seconds."


def test_exchange_powershell_runner_returns_error_for_os_error(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check):
        raise OSError("pwsh not found")

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = make_runner()
    result = runner.run(
        ExchangePowerShellCommand(
            name="Get-EXOMailbox",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert result.ok is False
    assert result.error == "Could not start Exchange PowerShell executable: pwsh not found"


def test_exchange_powershell_runner_truncates_long_process_errors(monkeypatch):
    long_error = "x" * 2100

    def fake_run(argv, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(argv, 1, "", long_error)

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = make_runner()
    result = runner.run(
        ExchangePowerShellCommand(
            name="Get-EXOMailbox",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.endswith("...<truncated>")
    assert len(result.error) < 2100