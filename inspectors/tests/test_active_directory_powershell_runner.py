import subprocess

import pytest

from inspectors.active_directory_command_runner import (
    ActiveDirectoryCommand,
    ActiveDirectoryCommandValidationError,
)
from inspectors.active_directory_config import (
    ActiveDirectoryInspectorBackend,
    ActiveDirectoryInspectorConfigError,
    ActiveDirectoryInspectorRuntimeConfig,
)
from inspectors.active_directory_powershell_runner import (
    ActiveDirectoryPowerShellRunnerConfig,
    ActiveDirectoryPowerShellSubprocessRunner,
    validate_active_directory_powershell_runner_config,
)
from inspectors.active_directory_powershell_runner import (
    subprocess as runner_subprocess,
)


def make_runtime_config(
    *,
    backend: ActiveDirectoryInspectorBackend = (
        ActiveDirectoryInspectorBackend.ACTIVE_DIRECTORY_POWERSHELL
    ),
    allow_real_external_calls: bool = True,
) -> ActiveDirectoryInspectorRuntimeConfig:
    return ActiveDirectoryInspectorRuntimeConfig(
        backend=backend,
        allow_real_external_calls=allow_real_external_calls,
    )


def make_runner(
    *,
    executable: str = "powershell.exe",
    timeout_seconds: int = 60,
):
    return ActiveDirectoryPowerShellSubprocessRunner(
        ActiveDirectoryPowerShellRunnerConfig(
            runtime_config=make_runtime_config(),
            executable=executable,
            timeout_seconds=timeout_seconds,
        )
    )


def make_command(
    name: str = "Get-ADUser",
    parameters: dict[str, object] | None = None,
) -> ActiveDirectoryCommand:
    return ActiveDirectoryCommand(
        name=name,
        parameters=parameters or {"Identity": "user@example.com"},
    )


# ---------------------- Config validation -----------------------


def test_validate_runner_config_allows_explicit_real_backend():
    config = ActiveDirectoryPowerShellRunnerConfig(
        runtime_config=make_runtime_config(),
    )

    validate_active_directory_powershell_runner_config(config)


def test_validate_runner_config_rejects_mock_backend():
    config = ActiveDirectoryPowerShellRunnerConfig(
        runtime_config=make_runtime_config(
            backend=ActiveDirectoryInspectorBackend.MOCK,
            allow_real_external_calls=False,
        ),
    )

    with pytest.raises(
        ActiveDirectoryInspectorConfigError,
        match="active_directory_powershell backend",
    ):
        validate_active_directory_powershell_runner_config(config)


def test_validate_runner_config_rejects_disabled_backend():
    config = ActiveDirectoryPowerShellRunnerConfig(
        runtime_config=make_runtime_config(
            backend=ActiveDirectoryInspectorBackend.DISABLED,
            allow_real_external_calls=False,
        ),
    )

    with pytest.raises(
        ActiveDirectoryInspectorConfigError,
        match="active_directory_powershell backend",
    ):
        validate_active_directory_powershell_runner_config(config)


def test_validate_runner_config_rejects_real_backend_without_opt_in():
    config = ActiveDirectoryPowerShellRunnerConfig(
        runtime_config=make_runtime_config(allow_real_external_calls=False),
    )

    with pytest.raises(
        ActiveDirectoryInspectorConfigError,
        match="real external calls",
    ):
        validate_active_directory_powershell_runner_config(config)


def test_validate_runner_config_rejects_empty_executable():
    config = ActiveDirectoryPowerShellRunnerConfig(
        runtime_config=make_runtime_config(),
        executable="   ",
    )

    with pytest.raises(
        ActiveDirectoryInspectorConfigError,
        match="executable cannot be empty",
    ):
        validate_active_directory_powershell_runner_config(config)


@pytest.mark.parametrize("timeout", [0, -1, -60])
def test_validate_runner_config_rejects_non_positive_timeout(timeout):
    config = ActiveDirectoryPowerShellRunnerConfig(
        runtime_config=make_runtime_config(),
        timeout_seconds=timeout,
    )

    with pytest.raises(
        ActiveDirectoryInspectorConfigError,
        match="timeout must be greater than zero",
    ):
        validate_active_directory_powershell_runner_config(config)


# ---------------------- Runner success paths --------------------


def test_runner_invokes_powershell_with_expected_argv(monkeypatch):
    captured = {}

    def fake_run(argv, capture_output, text, timeout, check, encoding=None, errors=None):
        captured["argv"] = argv
        captured["capture_output"] = capture_output
        captured["text"] = text
        captured["timeout"] = timeout
        captured["check"] = check
        captured["encoding"] = encoding
        captured["errors"] = errors
        return subprocess.CompletedProcess(
            argv,
            0,
            '{"DisplayName": "Example User"}',
            "",
        )

    monkeypatch.setattr(runner_subprocess, "run", fake_run)

    runner = make_runner()
    result = runner.run(make_command())

    assert result.ok is True
    assert result.data == {"DisplayName": "Example User"}
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
    assert captured["timeout"] == 60
    assert captured["check"] is False
    argv = captured["argv"]
    assert argv[0] == "powershell.exe"
    assert "-NoProfile" in argv
    assert "-NonInteractive" in argv
    assert "-Command" in argv


def test_runner_uses_configured_executable(monkeypatch):
    captured = {}

    def fake_run(argv, capture_output, text, timeout, check, encoding=None, errors=None):
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, "{}", "")

    monkeypatch.setattr(runner_subprocess, "run", fake_run)

    runner = make_runner(executable="pwsh")
    runner.run(make_command())

    assert captured["argv"][0] == "pwsh"


def test_runner_accepts_list_of_dicts_json(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check, encoding=None, errors=None):
        return subprocess.CompletedProcess(
            argv,
            0,
            '[{"Name": "Engineers"}, {"Name": "Operations"}]',
            "",
        )

    monkeypatch.setattr(runner_subprocess, "run", fake_run)

    result = make_runner().run(
        make_command(name="Get-ADPrincipalGroupMembership")
    )

    assert result.ok is True
    assert result.data == [
        {"Name": "Engineers"},
        {"Name": "Operations"},
    ]


def test_runner_returns_data_none_for_empty_stdout(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check, encoding=None, errors=None):
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(runner_subprocess, "run", fake_run)

    result = make_runner().run(make_command())

    assert result.ok is True
    assert result.data is None


# ---------------------- Runner safety paths --------------------


def test_runner_rejects_forbidden_command_before_subprocess(monkeypatch):
    def fake_run(*args, **kwargs):
        raise AssertionError(
            "subprocess.run must not be called for forbidden commands"
        )

    monkeypatch.setattr(runner_subprocess, "run", fake_run)

    runner = make_runner()

    with pytest.raises(
        ActiveDirectoryCommandValidationError,
        match="forbidden for inspectors",
    ):
        runner.run(
            ActiveDirectoryCommand(
                name="Set-ADUser",
                parameters={"Identity": "user@example.com"},
            )
        )


def test_runner_rejects_unknown_get_command_before_subprocess(monkeypatch):
    def fake_run(*args, **kwargs):
        raise AssertionError(
            "subprocess.run must not be called for non-allowlisted commands"
        )

    monkeypatch.setattr(runner_subprocess, "run", fake_run)

    runner = make_runner()

    with pytest.raises(
        ActiveDirectoryCommandValidationError,
        match="not allowlisted for inspectors",
    ):
        runner.run(
            ActiveDirectoryCommand(
                name="Get-ADGroupMember",
                parameters={"Identity": "Engineers"},
            )
        )


# ---------------------- Runner failure paths -------------------


def test_runner_returns_formatted_error_for_nonzero_exit(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check, encoding=None, errors=None):
        return subprocess.CompletedProcess(
            argv,
            1,
            "",
            "Access is denied.",
        )

    monkeypatch.setattr(runner_subprocess, "run", fake_run)

    result = make_runner().run(make_command())

    assert result.ok is False
    assert result.error is not None
    assert "exit code 1" in result.error
    assert "Access is denied." in result.error


def test_runner_falls_back_to_stdout_when_stderr_empty(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check, encoding=None, errors=None):
        return subprocess.CompletedProcess(
            argv,
            5,
            "Some failure detail on stdout.",
            "",
        )

    monkeypatch.setattr(runner_subprocess, "run", fake_run)

    result = make_runner().run(make_command())

    assert result.ok is False
    assert "exit code 5" in (result.error or "")
    assert "Some failure detail on stdout." in (result.error or "")


def test_runner_truncates_long_process_error(monkeypatch):
    long_stderr = "X" * 5000

    def fake_run(argv, capture_output, text, timeout, check, encoding=None, errors=None):
        return subprocess.CompletedProcess(argv, 1, "", long_stderr)

    monkeypatch.setattr(runner_subprocess, "run", fake_run)

    result = make_runner().run(make_command())

    assert result.ok is False
    assert "...<truncated>" in (result.error or "")
    assert len(result.error or "") < 5000


def test_runner_returns_invalid_json_error(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check, encoding=None, errors=None):
        return subprocess.CompletedProcess(argv, 0, "not-json", "")

    monkeypatch.setattr(runner_subprocess, "run", fake_run)

    result = make_runner().run(make_command())

    assert result.ok is False
    assert result.error == (
        "Active Directory PowerShell returned invalid JSON output."
    )


def test_runner_handles_replacement_character_output_without_raising(monkeypatch):
    # Simulate stdout that has already been decoded with errors="replace"
    # and now contains a U+FFFD replacement character, leaving invalid JSON.
    # The runner must surface this as a typed invalid-JSON result instead
    # of letting an exception bubble into the TUI.
    polluted_stdout = '{"DisplayName": "Test�Account"'  # missing closing brace too

    def fake_run(argv, capture_output, text, timeout, check, encoding=None, errors=None):
        assert encoding == "utf-8"
        assert errors == "replace"
        return subprocess.CompletedProcess(argv, 0, polluted_stdout, "")

    monkeypatch.setattr(runner_subprocess, "run", fake_run)

    result = make_runner().run(make_command())

    assert result.ok is False
    assert result.error == (
        "Active Directory PowerShell returned invalid JSON output."
    )


def test_runner_decodes_utf8_output_with_replacement_chars(monkeypatch):
    # Even when stdout was decoded with errors="replace" and contains a
    # U+FFFD inside a string value, valid JSON should still parse and the
    # replaced character should make it through into the snapshot.
    payload = '{"DisplayName": "Test�Account"}'

    def fake_run(argv, capture_output, text, timeout, check, encoding=None, errors=None):
        return subprocess.CompletedProcess(argv, 0, payload, "")

    monkeypatch.setattr(runner_subprocess, "run", fake_run)

    result = make_runner().run(make_command())

    assert result.ok is True
    assert result.data == {"DisplayName": "Test�Account"}


def test_runner_returns_unsupported_shape_error(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check, encoding=None, errors=None):
        return subprocess.CompletedProcess(argv, 0, '"just-a-string"', "")

    monkeypatch.setattr(runner_subprocess, "run", fake_run)

    result = make_runner().run(make_command())

    assert result.ok is False
    assert result.error == (
        "Active Directory PowerShell returned unsupported JSON data shape."
    )


def test_runner_returns_unsupported_shape_for_list_with_nondict_items(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check, encoding=None, errors=None):
        return subprocess.CompletedProcess(argv, 0, '[{"a": 1}, "string"]', "")

    monkeypatch.setattr(runner_subprocess, "run", fake_run)

    result = make_runner().run(make_command())

    assert result.ok is False
    assert result.error == (
        "Active Directory PowerShell returned unsupported JSON data shape."
    )


def test_runner_returns_timeout_error(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check, encoding=None, errors=None):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    monkeypatch.setattr(runner_subprocess, "run", fake_run)

    result = make_runner(timeout_seconds=42).run(make_command())

    assert result.ok is False
    assert result.error == (
        "Active Directory PowerShell command timed out after 42 seconds."
    )


def test_runner_returns_oserror_error(monkeypatch):
    def fake_run(argv, capture_output, text, timeout, check, encoding=None, errors=None):
        raise OSError("powershell.exe: not found")

    monkeypatch.setattr(runner_subprocess, "run", fake_run)

    result = make_runner().run(make_command())

    assert result.ok is False
    assert (
        "Could not start Active Directory PowerShell executable" in (result.error or "")
    )
    assert "powershell.exe: not found" in (result.error or "")
