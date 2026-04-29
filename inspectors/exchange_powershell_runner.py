from dataclasses import dataclass

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


class ExchangePowerShellExecutionError(RuntimeError):
    """Raised when real Exchange PowerShell execution cannot proceed safely."""


@dataclass(frozen=True)
class ExchangePowerShellRunnerConfig:
    runtime_config: ExchangeInspectorRuntimeConfig
    executable: str = "pwsh"
    timeout_seconds: int = 60


class ExchangePowerShellSubprocessRunner(ExchangePowerShellCommandRunner):
    """Skeleton for future real Exchange Online PowerShell command execution.

    This class intentionally does not execute PowerShell yet. It only defines the
    configuration and safety gate for future implementation.
    """

    def __init__(self, config: ExchangePowerShellRunnerConfig) -> None:
        validate_exchange_powershell_runner_config(config)
        self.config = config

    def run(self, command: ExchangePowerShellCommand) -> ExchangePowerShellCommandResult:
        validate_read_only_exchange_command(command)

        raise ExchangePowerShellExecutionError(
            "Real Exchange PowerShell execution is not implemented yet."
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

    if not config.executable.strip():
        raise ExchangeInspectorConfigError(
            "Exchange PowerShell runner executable cannot be empty."
        )

    if config.timeout_seconds <= 0:
        raise ExchangeInspectorConfigError(
            "Exchange PowerShell runner timeout must be greater than zero."
        )