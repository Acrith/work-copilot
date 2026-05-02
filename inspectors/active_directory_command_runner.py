from dataclasses import dataclass
from typing import Protocol

READ_ONLY_AD_COMMANDS = {
    "Get-ADUser",
    "Get-ADGroup",
    "Get-ADPrincipalGroupMembership",
}

FORBIDDEN_AD_COMMAND_PREFIXES = (
    "Set-",
    "New-",
    "Remove-",
    "Add-",
    "Clear-",
    "Enable-",
    "Disable-",
    "Unlock-",
    "Move-",
    "Rename-",
    "Reset-",
)


class ActiveDirectoryCommandValidationError(ValueError):
    """Raised when an AD command is not allowed for read-only inspection."""


@dataclass(frozen=True)
class ActiveDirectoryCommand:
    name: str
    parameters: dict[str, object]


@dataclass(frozen=True)
class ActiveDirectoryCommandResult:
    command: str
    ok: bool
    data: dict[str, object] | list[dict[str, object]] | None = None
    error: str | None = None


class ActiveDirectoryCommandRunner(Protocol):
    """Protocol for future Active Directory PowerShell command runners."""

    def run(self, command: ActiveDirectoryCommand) -> ActiveDirectoryCommandResult:
        """Run a validated read-only Active Directory command."""


class MockActiveDirectoryCommandRunner:
    """Deterministic command runner for tests. Does not call PowerShell."""

    def __init__(
        self,
        results: dict[str, ActiveDirectoryCommandResult] | None = None,
    ) -> None:
        self.results = results or {}
        self.commands: list[ActiveDirectoryCommand] = []

    def run(
        self, command: ActiveDirectoryCommand
    ) -> ActiveDirectoryCommandResult:
        validate_read_only_active_directory_command(command)
        self.commands.append(command)

        result = self.results.get(command.name)

        if result is None:
            return ActiveDirectoryCommandResult(
                command=command.name,
                ok=False,
                error=f"No mock result configured for command: {command.name}",
            )

        return result


def validate_read_only_active_directory_command(
    command: ActiveDirectoryCommand,
) -> None:
    command_name = command.name.strip()

    if not command_name:
        raise ActiveDirectoryCommandValidationError(
            "Active Directory command name cannot be empty."
        )

    for prefix in FORBIDDEN_AD_COMMAND_PREFIXES:
        if command_name.startswith(prefix):
            raise ActiveDirectoryCommandValidationError(
                "Active Directory command is forbidden for inspectors: "
                f"{command_name}"
            )

    if command_name not in READ_ONLY_AD_COMMANDS:
        raise ActiveDirectoryCommandValidationError(
            "Active Directory command is not allowlisted for inspectors: "
            f"{command_name}"
        )


def is_read_only_active_directory_command(
    command: ActiveDirectoryCommand,
) -> bool:
    try:
        validate_read_only_active_directory_command(command)
    except ActiveDirectoryCommandValidationError:
        return False

    return True
