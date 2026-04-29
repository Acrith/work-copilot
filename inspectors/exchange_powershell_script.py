import base64
import json
from dataclasses import dataclass

from inspectors.exchange_command_runner import (
    ExchangePowerShellCommand,
    validate_read_only_exchange_command,
)


@dataclass(frozen=True)
class ExchangePowerShellInvocation:
    executable: str
    argv: list[str]
    script: str


def build_exchange_powershell_script(command: ExchangePowerShellCommand) -> str:
    validate_read_only_exchange_command(command)

    payload_base64 = encode_exchange_command_payload(command)

    return "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            f"$payloadBase64 = '{payload_base64}'",
            "$payloadJson = [System.Text.Encoding]::UTF8.GetString("
            "[System.Convert]::FromBase64String($payloadBase64)"
            ")",
            "$payload = $payloadJson | ConvertFrom-Json -AsHashtable",
            "$params = @{}",
            "foreach ($key in $payload.parameters.Keys) {",
            "    $params[$key] = $payload.parameters[$key]",
            "}",
            "switch ($payload.name) {",
            "    'Get-EXOMailbox' { $result = Get-EXOMailbox @params; break }",
            "    'Get-EXOMailboxStatistics' { "
            "$result = Get-EXOMailboxStatistics @params; break "
            "}",
            "    'Get-Mailbox' { $result = Get-Mailbox @params; break }",
            "    default { throw \"Exchange command is not allowlisted for inspectors: "
            "$($payload.name)\" }",
            "}",
            "$result | ConvertTo-Json -Depth 8 -Compress",
            "",
        ]
    )


def build_exchange_powershell_invocation(
    command: ExchangePowerShellCommand,
    *,
    executable: str = "pwsh",
) -> ExchangePowerShellInvocation:
    executable = executable.strip()

    if not executable:
        raise ValueError("PowerShell executable cannot be empty.")

    script = build_exchange_powershell_script(command)

    return ExchangePowerShellInvocation(
        executable=executable,
        argv=[
            executable,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ],
        script=script,
    )


def encode_exchange_command_payload(command: ExchangePowerShellCommand) -> str:
    validate_read_only_exchange_command(command)

    payload = {
        "name": command.name.strip(),
        "parameters": command.parameters,
    }
    payload_json = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return base64.b64encode(payload_json.encode("utf-8")).decode("ascii")


def decode_exchange_command_payload(payload_base64: str) -> dict[str, object]:
    payload_json = base64.b64decode(payload_base64.encode("ascii")).decode("utf-8")
    payload = json.loads(payload_json)

    if not isinstance(payload, dict):
        raise ValueError("Exchange command payload must decode to a JSON object.")

    return payload