import base64
import json
from dataclasses import dataclass

from inspectors.active_directory_command_runner import (
    ActiveDirectoryCommand,
    validate_read_only_active_directory_command,
)

AD_USER_PROPERTIES = (
    "DisplayName",
    "GivenName",
    "Surname",
    "UserPrincipalName",
    "SamAccountName",
    "Mail",
    "Enabled",
    "DistinguishedName",
    "Title",
    "Department",
    "physicalDeliveryOfficeName",
    "telephoneNumber",
    "mobile",
    "Manager",
)

AD_USER_PROJECTION_FIELDS = (
    "DisplayName",
    "GivenName",
    "Surname",
    "UserPrincipalName",
    "SamAccountName",
    "Mail",
    "Enabled",
    "DistinguishedName",
    "Title",
    "Department",
    "Office",
    "OfficePhone",
    "MobilePhone",
    "Manager",
)

AD_GROUP_PROJECTION_FIELDS = (
    "Name",
    "SamAccountName",
    "Mail",
    "GroupScope",
    "GroupCategory",
    "DistinguishedName",
)

AD_PRINCIPAL_GROUP_MEMBERSHIP_PROJECTION_FIELDS = (
    "Name",
    "SamAccountName",
    "DistinguishedName",
    "GroupScope",
    "GroupCategory",
)


@dataclass(frozen=True)
class ActiveDirectoryPowerShellInvocation:
    executable: str
    argv: list[str]
    script: str


_AD_USER_PLAIN_PROJECTION_FIELDS = (
    "DisplayName",
    "GivenName",
    "Surname",
    "UserPrincipalName",
    "SamAccountName",
    "Mail",
    "Enabled",
    "DistinguishedName",
    "Title",
    "Department",
)

_AD_USER_CALCULATED_PROJECTION = (
    ("Office", "physicalDeliveryOfficeName"),
    ("OfficePhone", "telephoneNumber"),
    ("MobilePhone", "mobile"),
)


def build_active_directory_powershell_script(
    command: ActiveDirectoryCommand,
) -> str:
    validate_read_only_active_directory_command(command)

    payload_base64 = encode_active_directory_command_payload(command)

    user_properties_csv = ",".join(f"'{name}'" for name in AD_USER_PROPERTIES)
    group_projection_csv = ",".join(AD_GROUP_PROJECTION_FIELDS)
    membership_projection_csv = ",".join(
        AD_PRINCIPAL_GROUP_MEMBERSHIP_PROJECTION_FIELDS
    )

    user_select_lines: list[str] = ["        $result = $raw | Select-Object `"]

    for field in _AD_USER_PLAIN_PROJECTION_FIELDS:
        user_select_lines.append(f"            {field}, `")

    for friendly, ldap in _AD_USER_CALCULATED_PROJECTION:
        user_select_lines.append(
            f"            @{{Name='{friendly}'; Expression={{ "
            f"if ($null -ne $_.{ldap}) {{ [string]$_.{ldap} }} "
            "else { $null } }}, `"
        )

    user_select_lines.append("            Manager")

    lines = [
        "$ErrorActionPreference = 'Stop'",
        "Import-Module ActiveDirectory -ErrorAction Stop",
        f"$payloadBase64 = '{payload_base64}'",
        "$payloadJson = [System.Text.Encoding]::UTF8.GetString("
        "[System.Convert]::FromBase64String($payloadBase64)"
        ")",
        "$payload = $payloadJson | ConvertFrom-Json",
        "$params = @{}",
        "if ($null -ne $payload.parameters) {",
        "    foreach ($property in $payload.parameters.PSObject.Properties) {",
        "        $params[$property.Name] = $property.Value",
        "    }",
        "}",
        f"$adUserProperties = @({user_properties_csv})",
        "switch ($payload.name) {",
        "    'Get-ADUser' {",
        "        $raw = Get-ADUser @params -Properties $adUserProperties",
        *user_select_lines,
        "        break",
        "    }",
        "    'Get-ADGroup' {",
        "        $raw = Get-ADGroup @params",
        f"        $result = $raw | Select-Object {group_projection_csv}",
        "        break",
        "    }",
        "    'Get-ADPrincipalGroupMembership' {",
        "        $raw = Get-ADPrincipalGroupMembership @params",
        (
            "        $result = $raw | Select-Object "
            f"{membership_projection_csv}"
        ),
        "        break",
        "    }",
        "    default { throw \"Active Directory command is not allowlisted "
        "for inspectors: $($payload.name)\" }",
        "}",
        "$result | ConvertTo-Json -Depth 8 -Compress",
        "",
    ]

    return "\n".join(lines)


def build_active_directory_powershell_invocation(
    command: ActiveDirectoryCommand,
    *,
    executable: str = "powershell.exe",
) -> ActiveDirectoryPowerShellInvocation:
    executable = executable.strip()

    if not executable:
        raise ValueError("PowerShell executable cannot be empty.")

    script = build_active_directory_powershell_script(command)

    return ActiveDirectoryPowerShellInvocation(
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


def encode_active_directory_command_payload(command: ActiveDirectoryCommand) -> str:
    validate_read_only_active_directory_command(command)

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


def decode_active_directory_command_payload(
    payload_base64: str,
) -> dict[str, object]:
    payload_json = base64.b64decode(payload_base64.encode("ascii")).decode("utf-8")
    payload = json.loads(payload_json)

    if not isinstance(payload, dict):
        raise ValueError(
            "Active Directory command payload must decode to a JSON object."
        )

    return payload
