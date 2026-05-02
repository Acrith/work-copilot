import pytest

from inspectors.active_directory_command_runner import (
    ActiveDirectoryCommand,
    ActiveDirectoryCommandValidationError,
)
from inspectors.active_directory_powershell_script import (
    build_active_directory_powershell_invocation,
    build_active_directory_powershell_script,
    decode_active_directory_command_payload,
    encode_active_directory_command_payload,
)


def test_encode_active_directory_command_payload_round_trips():
    command = ActiveDirectoryCommand(
        name="Get-ADUser",
        parameters={"Identity": "user@example.com"},
    )

    encoded = encode_active_directory_command_payload(command)
    decoded = decode_active_directory_command_payload(encoded)

    assert decoded == {
        "name": "Get-ADUser",
        "parameters": {"Identity": "user@example.com"},
    }


def test_encode_active_directory_command_payload_preserves_unicode():
    command = ActiveDirectoryCommand(
        name="Get-ADUser",
        parameters={"Identity": "Melek.Baş@example.com"},
    )

    encoded = encode_active_directory_command_payload(command)
    decoded = decode_active_directory_command_payload(encoded)

    assert decoded["parameters"] == {"Identity": "Melek.Baş@example.com"}


def test_decode_active_directory_command_payload_rejects_non_object_json():
    import base64

    encoded = base64.b64encode(b'["not", "object"]').decode("ascii")

    with pytest.raises(ValueError, match="must decode to a JSON object"):
        decode_active_directory_command_payload(encoded)


def test_build_active_directory_powershell_script_imports_active_directory_module():
    script = build_active_directory_powershell_script(
        ActiveDirectoryCommand(
            name="Get-ADUser",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert "Import-Module ActiveDirectory -ErrorAction Stop" in script


def test_build_active_directory_powershell_script_forces_utf8_stdout_before_module_import():
    script = build_active_directory_powershell_script(
        ActiveDirectoryCommand(
            name="Get-ADUser",
            parameters={"Identity": "user@example.com"},
        )
    )

    utf8_setup = "New-Object System.Text.UTF8Encoding $false"
    console_encoding = "[Console]::OutputEncoding = $utf8NoBom"
    output_encoding = "$OutputEncoding = $utf8NoBom"

    assert utf8_setup in script
    assert console_encoding in script
    assert output_encoding in script

    import_index = script.index("Import-Module ActiveDirectory -ErrorAction Stop")
    utf8_setup_index = script.index(utf8_setup)
    console_encoding_index = script.index(console_encoding)
    output_encoding_index = script.index(output_encoding)

    # The UTF-8 stdout setup must run before Import-Module so the module's
    # own load-time output (if any) is also captured under UTF-8.
    assert utf8_setup_index < import_index
    assert console_encoding_index < import_index
    assert output_encoding_index < import_index


def test_build_active_directory_powershell_script_uses_base64_payload():
    command = ActiveDirectoryCommand(
        name="Get-ADUser",
        parameters={"Identity": "user@example.com; Remove-ADUser evil"},
    )

    script = build_active_directory_powershell_script(command)

    # Parameter values must NOT be interpolated raw into the script body.
    assert "Remove-ADUser evil" not in script
    assert "user@example.com; Remove-ADUser evil" not in script
    assert "FromBase64String" in script
    # Windows PowerShell 5.1 (the default under powershell.exe) does not
    # support ConvertFrom-Json -AsHashtable, so the script must use the
    # PSObject.Properties iteration pattern instead.
    assert "ConvertFrom-Json" in script
    assert "-AsHashtable" not in script
    assert "$payload.parameters.PSObject.Properties" in script


def test_build_active_directory_powershell_script_uses_static_switch_with_three_commands():
    script = build_active_directory_powershell_script(
        ActiveDirectoryCommand(
            name="Get-ADUser",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert "switch ($payload.name) {" in script
    assert "'Get-ADUser'" in script
    assert "'Get-ADGroup'" in script
    assert "'Get-ADPrincipalGroupMembership'" in script
    assert "Get-ADUser @params -Properties $adUserProperties" in script
    assert "Get-ADGroup @params" in script
    assert "Get-ADPrincipalGroupMembership @params" in script


def test_build_active_directory_powershell_script_emits_compressed_json_at_depth_8():
    script = build_active_directory_powershell_script(
        ActiveDirectoryCommand(
            name="Get-ADUser",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert "ConvertTo-Json -Depth 8 -Compress" in script


def test_build_active_directory_powershell_script_uses_explicit_user_properties():
    script = build_active_directory_powershell_script(
        ActiveDirectoryCommand(
            name="Get-ADUser",
            parameters={"Identity": "user@example.com"},
        )
    )

    # Properties are passed via an explicit list, not -Properties *.
    assert "Get-ADUser @params -Properties $adUserProperties" in script
    assert "-Properties *" not in script
    assert "$adUserProperties = @(" in script

    for property_name in (
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
    ):
        assert f"'{property_name}'" in script, (
            f"Expected requested AD user property {property_name} in script"
        )


def test_build_active_directory_powershell_script_user_projection_includes_friendly_fields():
    script = build_active_directory_powershell_script(
        ActiveDirectoryCommand(
            name="Get-ADUser",
            parameters={"Identity": "user@example.com"},
        )
    )

    for projected in (
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
        "Manager",
    ):
        assert projected in script

    # Calculated property names must appear as Select-Object output keys.
    assert "Name='Office'" in script
    assert "Name='OfficePhone'" in script
    assert "Name='MobilePhone'" in script
    # Calculated properties read from the raw LDAP names.
    assert "$_.physicalDeliveryOfficeName" in script
    assert "$_.telephoneNumber" in script
    assert "$_.mobile" in script


def test_build_active_directory_powershell_script_does_not_expose_sensitive_attributes():
    script = build_active_directory_powershell_script(
        ActiveDirectoryCommand(
            name="Get-ADUser",
            parameters={"Identity": "user@example.com"},
        )
    )

    forbidden_substrings = [
        "pwdLastSet",
        "badPwdCount",
        "lockoutTime",
        "userPassword",
        "unicodePwd",
        "ms-Mcs-AdmPwd",
        "msLAPS-Password",
        "msLAPS-EncryptedPassword",
        "msFVE-RecoveryInformation",
        "msFVE-RecoveryPassword",
        "thumbnailPhoto",
        "homeDirectory",
        "scriptPath",
        "directReports",
        "memberOf",
    ]

    for substring in forbidden_substrings:
        assert substring not in script, (
            f"Sensitive/broad attribute leaked into AD script: {substring}"
        )


def test_build_active_directory_powershell_script_does_not_use_get_adgroupmember():
    script_user = build_active_directory_powershell_script(
        ActiveDirectoryCommand(
            name="Get-ADUser",
            parameters={"Identity": "user@example.com"},
        )
    )
    script_group = build_active_directory_powershell_script(
        ActiveDirectoryCommand(
            name="Get-ADGroup",
            parameters={"Identity": "Engineers"},
        )
    )
    script_membership = build_active_directory_powershell_script(
        ActiveDirectoryCommand(
            name="Get-ADPrincipalGroupMembership",
            parameters={"Identity": "user@example.com"},
        )
    )

    for script in (script_user, script_group, script_membership):
        assert "Get-ADGroupMember" not in script


def test_build_active_directory_powershell_script_group_projection_fields():
    script = build_active_directory_powershell_script(
        ActiveDirectoryCommand(
            name="Get-ADGroup",
            parameters={"Identity": "Engineers"},
        )
    )

    assert "Get-ADGroup @params" in script
    assert (
        "Select-Object Name,SamAccountName,Mail,GroupScope,GroupCategory,"
        "DistinguishedName" in script
    )


def test_build_active_directory_powershell_script_principal_group_membership_projection():
    script = build_active_directory_powershell_script(
        ActiveDirectoryCommand(
            name="Get-ADPrincipalGroupMembership",
            parameters={"Identity": "user@example.com"},
        )
    )

    assert "Get-ADPrincipalGroupMembership @params" in script
    assert (
        "Select-Object Name,SamAccountName,DistinguishedName,GroupScope,"
        "GroupCategory" in script
    )


def test_build_active_directory_powershell_script_rejects_forbidden_command():
    command = ActiveDirectoryCommand(
        name="Set-ADUser",
        parameters={"Identity": "user@example.com"},
    )

    with pytest.raises(
        ActiveDirectoryCommandValidationError,
        match="forbidden for inspectors",
    ):
        build_active_directory_powershell_script(command)


def test_build_active_directory_powershell_script_rejects_unknown_get_command():
    command = ActiveDirectoryCommand(
        name="Get-ADGroupMember",
        parameters={"Identity": "Engineers"},
    )

    with pytest.raises(
        ActiveDirectoryCommandValidationError,
        match="not allowlisted for inspectors",
    ):
        build_active_directory_powershell_script(command)


def test_build_active_directory_powershell_invocation_returns_noninteractive_args():
    command = ActiveDirectoryCommand(
        name="Get-ADUser",
        parameters={"Identity": "user@example.com"},
    )

    invocation = build_active_directory_powershell_invocation(
        command,
        executable="powershell.exe",
    )

    assert invocation.executable == "powershell.exe"
    assert invocation.argv[0] == "powershell.exe"
    assert "-NoProfile" in invocation.argv
    assert "-NonInteractive" in invocation.argv
    assert "-Command" in invocation.argv
    assert invocation.argv[-1] == invocation.script
    assert invocation.script == build_active_directory_powershell_script(command)


def test_build_active_directory_powershell_invocation_accepts_pwsh_executable():
    command = ActiveDirectoryCommand(
        name="Get-ADUser",
        parameters={"Identity": "user@example.com"},
    )

    invocation = build_active_directory_powershell_invocation(
        command,
        executable="pwsh",
    )

    assert invocation.executable == "pwsh"
    assert invocation.argv[0] == "pwsh"


def test_build_active_directory_powershell_invocation_rejects_empty_executable():
    command = ActiveDirectoryCommand(
        name="Get-ADUser",
        parameters={"Identity": "user@example.com"},
    )

    with pytest.raises(ValueError, match="executable cannot be empty"):
        build_active_directory_powershell_invocation(command, executable="   ")
