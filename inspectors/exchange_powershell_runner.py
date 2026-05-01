import json
import subprocess
from dataclasses import dataclass

from inspectors.exchange_auth_config import (
    ExchangePowerShellAuthConfig,
    ExchangePowerShellAuthConfigError,
    validate_exchange_powershell_auth_config,
)
from inspectors.exchange_command_runner import (
    ExchangePowerShellCommand,
    ExchangePowerShellCommandResult,
    ExchangePowerShellCommandRunner,
    validate_read_only_exchange_command,
)
from inspectors.exchange_config import (
    ExchangeInspectorBackend,
    ExchangeInspectorConfigError,
    ExchangeInspectorRuntimeConfig,
)
from inspectors.exchange_powershell_script import build_exchange_powershell_invocation


class ExchangePowerShellExecutionError(RuntimeError):
    """Raised when real Exchange PowerShell execution cannot proceed safely."""


@dataclass(frozen=True)
class ExchangePowerShellRunnerConfig:
    runtime_config: ExchangeInspectorRuntimeConfig
    executable: str = "pwsh"
    timeout_seconds: int = 60
    auth_config: ExchangePowerShellAuthConfig | None = None


class ExchangePowerShellSubprocessRunner(ExchangePowerShellCommandRunner):
    """Runs allowlisted read-only Exchange Online PowerShell inspector commands."""

    def __init__(self, config: ExchangePowerShellRunnerConfig) -> None:
        validate_exchange_powershell_runner_config(config)
        self.config = config

    def run(self, command: ExchangePowerShellCommand) -> ExchangePowerShellCommandResult:
        validate_read_only_exchange_command(command)

        invocation = build_exchange_powershell_invocation(
            command,
            executable=self.config.executable,
            auth_config=self.config.auth_config,
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
            return ExchangePowerShellCommandResult(
                command=command.name,
                ok=False,
                error=(
                    "Exchange PowerShell command timed out after "
                    f"{self.config.timeout_seconds} seconds."
                ),
            )
        except OSError as exc:
            return ExchangePowerShellCommandResult(
                command=command.name,
                ok=False,
                error=f"Could not start Exchange PowerShell executable: {exc}",
            )

        if completed.returncode != 0:
            return ExchangePowerShellCommandResult(
                command=command.name,
                ok=False,
                error=_format_process_error(completed),
            )

        stdout = completed.stdout.strip()

        if not stdout:
            return ExchangePowerShellCommandResult(
                command=command.name,
                ok=True,
                data=None,
            )

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return ExchangePowerShellCommandResult(
                command=command.name,
                ok=False,
                error="Exchange PowerShell returned invalid JSON output.",
            )

        if not _is_supported_json_data(data):
            return ExchangePowerShellCommandResult(
                command=command.name,
                ok=False,
                error="Exchange PowerShell returned unsupported JSON data shape.",
            )

        return ExchangePowerShellCommandResult(
            command=command.name,
            ok=True,
            data=data,
        )


def validate_exchange_powershell_runner_config(
    config: ExchangePowerShellRunnerConfig,
) -> None:
    runtime_config = config.runtime_config

    if runtime_config.backend != ExchangeInspectorBackend.EXCHANGE_ONLINE_POWERSHELL:
        raise ExchangeInspectorConfigError(
            "Exchange PowerShell runner requires exchange_online_powershell backend."
        )

    if not runtime_config.allow_real_external_calls:
        raise ExchangeInspectorConfigError(
            "Exchange PowerShell runner requires real external calls to be explicitly allowed."
        )

    if config.auth_config is None:
        raise ExchangeInspectorConfigError(
            "Exchange PowerShell runner requires Exchange PowerShell auth config."
        )

    try:
        validate_exchange_powershell_auth_config(config.auth_config)
    except ExchangePowerShellAuthConfigError as exc:
        raise ExchangeInspectorConfigError(
            f"Invalid Exchange PowerShell auth config: {exc}"
        ) from exc

    if not config.executable.strip():
        raise ExchangeInspectorConfigError(
            "Exchange PowerShell runner executable cannot be empty."
        )

    if config.timeout_seconds <= 0:
        raise ExchangeInspectorConfigError(
            "Exchange PowerShell runner timeout must be greater than zero."
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
        f"Exchange PowerShell command failed with exit code {completed.returncode}: "
        f"{_truncate(details)}"
    )


def _truncate(value: str, *, limit: int = 2000) -> str:
    if len(value) <= limit:
        return value

    return value[:limit] + "...<truncated>"