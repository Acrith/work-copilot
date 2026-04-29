from dataclasses import dataclass
from typing import Protocol

READ_ONLY_EXCHANGE_COMMANDS = {
    "Get-EXOMailbox",
    "Get-EXOMailboxStatistics",
    "Get-Mailbox",
}

FORBIDDEN_EXCHANGE_COMMAND_PREFIXES = (
    "Set-",
    "New-",
    "Remove-",
    "Enable-",
    "Disable-",
    "Add-",
    "Clear-",
    "Update-",
    "Start-",
    "Stop-",
    "Restart-",
)


class ExchangeCommandValidationError(ValueError):
    """Raised when an Exchange command is not allowed for read-only inspection."""


@dataclass(frozen=True)
class ExchangePowerShellCommand:
    name: str
    parameters: dict[str, object]


@dataclass(frozen=True)
class ExchangePowerShellCommandResult:
    command: str
    ok: bool
    data: dict[str, object] | list[dict[str, object]] | None = None
    error: str | None = None


class ExchangePowerShellCommandRunner(Protocol):
    """Protocol for future Exchange Online PowerShell command runners."""

    def run(self, command: ExchangePowerShellCommand) -> ExchangePowerShellCommandResult:
        """Run a validated Exchange Online PowerShell command."""


class MockExchangePowerShellCommandRunner:
    """Deterministic command runner for tests. Does not call PowerShell."""

    def __init__(
        self,
        results: dict[str, ExchangePowerShellCommandResult] | None = None,
    ) -> None:
        self.results = results or {}
        self.commands: list[ExchangePowerShellCommand] = []

    def run(self, command: ExchangePowerShellCommand) -> ExchangePowerShellCommandResult:
        validate_read_only_exchange_command(command)
        self.commands.append(command)

        result = self.results.get(command.name)

        if result is None:
            return ExchangePowerShellCommandResult(
                command=command.name,
                ok=False,
                error=f"No mock result configured for command: {command.name}",
            )

        return result


def validate_read_only_exchange_command(command: ExchangePowerShellCommand) -> None:
    command_name = command.name.strip()

    if not command_name:
        raise ExchangeCommandValidationError("Exchange command name cannot be empty.")

    for prefix in FORBIDDEN_EXCHANGE_COMMAND_PREFIXES:
        if command_name.startswith(prefix):
            raise ExchangeCommandValidationError(
                f"Exchange command is forbidden for inspectors: {command_name}"
            )

    if command_name not in READ_ONLY_EXCHANGE_COMMANDS:
        raise ExchangeCommandValidationError(
            f"Exchange command is not allowlisted for inspectors: {command_name}"
        )


def is_read_only_exchange_command(command: ExchangePowerShellCommand) -> bool:
    try:
        validate_read_only_exchange_command(command)
    except ExchangeCommandValidationError:
        return False

    return True