import json
import subprocess
from dataclasses import dataclass

from inspectors.active_directory_command_runner import (
    ActiveDirectoryCommand,
    ActiveDirectoryCommandResult,
    ActiveDirectoryCommandRunner,
    validate_read_only_active_directory_command,
)
from inspectors.active_directory_config import (
    ActiveDirectoryInspectorBackend,
    ActiveDirectoryInspectorConfigError,
    ActiveDirectoryInspectorRuntimeConfig,
)
from inspectors.active_directory_powershell_script import (
    build_active_directory_powershell_invocation,
)


class ActiveDirectoryPowerShellExecutionError(RuntimeError):
    """Raised when real Active Directory PowerShell execution cannot proceed safely."""


@dataclass(frozen=True)
class ActiveDirectoryPowerShellRunnerConfig:
    runtime_config: ActiveDirectoryInspectorRuntimeConfig
    executable: str = "powershell.exe"
    timeout_seconds: int = 60


class ActiveDirectoryPowerShellSubprocessRunner(ActiveDirectoryCommandRunner):
    """Runs allowlisted read-only Active Directory PowerShell inspector commands."""

    def __init__(self, config: ActiveDirectoryPowerShellRunnerConfig) -> None:
        validate_active_directory_powershell_runner_config(config)
        self.config = config

    def run(
        self, command: ActiveDirectoryCommand
    ) -> ActiveDirectoryCommandResult:
        validate_read_only_active_directory_command(command)

        invocation = build_active_directory_powershell_invocation(
            command,
            executable=self.config.executable,
        )

        try:
            completed = subprocess.run(
                invocation.argv,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ActiveDirectoryCommandResult(
                command=command.name,
                ok=False,
                error=(
                    "Active Directory PowerShell command timed out after "
                    f"{self.config.timeout_seconds} seconds."
                ),
            )
        except OSError as exc:
            return ActiveDirectoryCommandResult(
                command=command.name,
                ok=False,
                error=(
                    "Could not start Active Directory PowerShell executable: "
                    f"{exc}"
                ),
            )

        if completed.returncode != 0:
            return ActiveDirectoryCommandResult(
                command=command.name,
                ok=False,
                error=_format_process_error(completed),
            )

        stdout = (completed.stdout or "").strip()

        if not stdout:
            return ActiveDirectoryCommandResult(
                command=command.name,
                ok=True,
                data=None,
            )

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return ActiveDirectoryCommandResult(
                command=command.name,
                ok=False,
                error="Active Directory PowerShell returned invalid JSON output.",
            )

        if not _is_supported_json_data(data):
            return ActiveDirectoryCommandResult(
                command=command.name,
                ok=False,
                error=(
                    "Active Directory PowerShell returned unsupported JSON "
                    "data shape."
                ),
            )

        return ActiveDirectoryCommandResult(
            command=command.name,
            ok=True,
            data=data,
        )


def validate_active_directory_powershell_runner_config(
    config: ActiveDirectoryPowerShellRunnerConfig,
) -> None:
    runtime_config = config.runtime_config

    if (
        runtime_config.backend
        != ActiveDirectoryInspectorBackend.ACTIVE_DIRECTORY_POWERSHELL
    ):
        raise ActiveDirectoryInspectorConfigError(
            "Active Directory PowerShell runner requires "
            "active_directory_powershell backend."
        )

    if not runtime_config.allow_real_external_calls:
        raise ActiveDirectoryInspectorConfigError(
            "Active Directory PowerShell runner requires real external calls "
            "to be explicitly allowed."
        )

    if not config.executable.strip():
        raise ActiveDirectoryInspectorConfigError(
            "Active Directory PowerShell runner executable cannot be empty."
        )

    if config.timeout_seconds <= 0:
        raise ActiveDirectoryInspectorConfigError(
            "Active Directory PowerShell runner timeout must be greater than zero."
        )


def _is_supported_json_data(value: object) -> bool:
    if value is None:
        return True

    if isinstance(value, dict):
        return True

    if isinstance(value, list):
        return all(isinstance(item, dict) for item in value)

    return False


def _format_process_error(completed: subprocess.CompletedProcess[str]) -> str:
    stderr = (completed.stderr or "").strip()
    stdout = (completed.stdout or "").strip()

    if stderr:
        details = stderr
    elif stdout:
        details = stdout
    else:
        details = "No error output."

    return (
        "Active Directory PowerShell command failed with exit code "
        f"{completed.returncode}: {_truncate(details)}"
    )


def _truncate(value: str, *, limit: int = 2000) -> str:
    if len(value) <= limit:
        return value

    return value[:limit] + "...<truncated>"
