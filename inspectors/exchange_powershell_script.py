import base64
import json
from dataclasses import dataclass

from inspectors.exchange_auth_config import (
    ExchangePowerShellAuthConfig,
    ExchangePowerShellAuthMode,
    validate_exchange_powershell_auth_config,
)
from inspectors.exchange_command_runner import (
    ExchangePowerShellCommand,
    validate_read_only_exchange_command,
)


@dataclass(frozen=True)
class ExchangePowerShellInvocation:
    executable: str
    argv: list[str]
    script: str


def build_exchange_powershell_script(
    command: ExchangePowerShellCommand,
    *,
    auth_config: ExchangePowerShellAuthConfig | None = None,
) -> str:
    validate_read_only_exchange_command(command)

    payload_base64 = encode_exchange_command_payload(command)
    lines = ["$ErrorActionPreference = 'Stop'"]

    if auth_config is not None and auth_config.is_enabled:
        lines.extend(build_exchange_connect_preamble(auth_config).splitlines())

    lines.extend(
        [
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
            "    'Get-EXOMailboxStatistics' {",
            "        $raw = Get-EXOMailboxStatistics @params",
            "        $result = $raw | Select-Object `",
            "            DisplayName, `",
            "            ItemCount, `",
            "            DeletedItemCount, `",
            "            StorageLimitStatus, `",
            "            LastLogonTime, `",
            "            @{Name='TotalItemSize'; Expression={ "
            "if ($null -ne $_.TotalItemSize) { $_.TotalItemSize.ToString() } "
            "else { $null } }}, `",
            "            @{Name='TotalDeletedItemSize'; Expression={ "
            "if ($null -ne $_.TotalDeletedItemSize) { $_.TotalDeletedItemSize.ToString() } "
            "else { $null } }}",
            "        break",
            "    }",
            "    'Get-Mailbox' { $result = Get-Mailbox @params; break }",
            "    default { throw \"Exchange command is not allowlisted for inspectors: "
            "$($payload.name)\" }",
            "}",
            "$result | ConvertTo-Json -Depth 8 -Compress",
            "",
        ]
    )

    return "\n".join(lines)


def build_exchange_connect_preamble(auth_config: ExchangePowerShellAuthConfig) -> str:
    validate_exchange_powershell_auth_config(auth_config)

    if not auth_config.is_enabled:
        raise ValueError("Exchange auth config is disabled.")

    auth_payload_base64 = encode_exchange_auth_payload(auth_config)

    return "\n".join(
        [
            "Import-Module ExchangeOnlineManagement -ErrorAction Stop",
            f"$authPayloadBase64 = '{auth_payload_base64}'",
            "$authPayloadJson = [System.Text.Encoding]::UTF8.GetString("
            "[System.Convert]::FromBase64String($authPayloadBase64)"
            ")",
            "$auth = $authPayloadJson | ConvertFrom-Json -AsHashtable",
            "switch ($auth.mode) {",
            "    'app_certificate_thumbprint' {",
            "        Connect-ExchangeOnline "
            "-AppId $auth.app_id "
            "-CertificateThumbprint $auth.certificate_thumbprint "
            "-Organization $auth.organization "
            "-ShowBanner:$false "
            "-ErrorAction Stop",
            "        break",
            "    }",
            "    'app_certificate_file' {",
            "        $certificatePasswordText = "
            "[Environment]::GetEnvironmentVariable($auth.certificate_password_env_var)",
            "        if ([string]::IsNullOrWhiteSpace($certificatePasswordText)) {",
            "            throw \"Exchange certificate password environment variable is not set: "
            "$($auth.certificate_password_env_var)\"",
            "        }",
            "        $certificatePassword = ConvertTo-SecureString "
            "-String $certificatePasswordText -AsPlainText -Force",
            "        Connect-ExchangeOnline "
            "-AppId $auth.app_id "
            "-CertificateFilePath $auth.certificate_path "
            "-CertificatePassword $certificatePassword "
            "-Organization $auth.organization "
            "-ShowBanner:$false "
            "-ErrorAction Stop",
            "        break",
            "    }",
            "    default { throw \"Unsupported Exchange auth mode: $($auth.mode)\" }",
            "}",
        ]
    )


def build_exchange_powershell_invocation(
    command: ExchangePowerShellCommand,
    *,
    executable: str = "pwsh",
    auth_config: ExchangePowerShellAuthConfig | None = None,
) -> ExchangePowerShellInvocation:
    executable = executable.strip()

    if not executable:
        raise ValueError("PowerShell executable cannot be empty.")

    script = build_exchange_powershell_script(command, auth_config=auth_config)

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


def encode_exchange_auth_payload(auth_config: ExchangePowerShellAuthConfig) -> str:
    validate_exchange_powershell_auth_config(auth_config)

    if auth_config.mode == ExchangePowerShellAuthMode.APP_CERTIFICATE_THUMBPRINT:
        payload = {
            "mode": auth_config.mode.value,
            "app_id": auth_config.app_id,
            "organization": auth_config.organization,
            "certificate_thumbprint": auth_config.certificate_thumbprint,
        }
    elif auth_config.mode == ExchangePowerShellAuthMode.APP_CERTIFICATE_FILE:
        payload = {
            "mode": auth_config.mode.value,
            "app_id": auth_config.app_id,
            "organization": auth_config.organization,
            "certificate_path": auth_config.certificate_path,
            "certificate_password_env_var": auth_config.certificate_password_env_var,
        }
    else:
        raise ValueError("Exchange auth config is disabled.")

    payload_json = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return base64.b64encode(payload_json.encode("utf-8")).decode("ascii")


def decode_exchange_auth_payload(payload_base64: str) -> dict[str, object]:
    payload_json = base64.b64decode(payload_base64.encode("ascii")).decode("utf-8")
    payload = json.loads(payload_json)

    if not isinstance(payload, dict):
        raise ValueError("Exchange auth payload must decode to a JSON object.")

    return payload