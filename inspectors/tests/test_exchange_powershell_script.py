import pytest

from inspectors.exchange_command_runner import (
    ExchangeCommandValidationError,
    ExchangePowerShellCommand,
)
from inspectors.exchange_powershell_script import (
    build_exchange_powershell_invocation,
    build_exchange_powershell_script,
    decode_exchange_command_payload,
    encode_exchange_command_payload,
)


def test_encode_exchange_command_payload_round_trips_command_data():
    command = ExchangePowerShellCommand(
        name="Get-EXOMailbox",
        parameters={"Identity": "user@example.com"},
    )

    encoded = encode_exchange_command_payload(command)
    decoded = decode_exchange_command_payload(encoded)

    assert decoded == {
        "name": "Get-EXOMailbox",
        "parameters": {"Identity": "user@example.com"},
    }


def test_encode_exchange_command_payload_preserves_unicode():
    command = ExchangePowerShellCommand(
        name="Get-EXOMailbox",
        parameters={"Identity": "Melek.Baş@example.com"},
    )

    encoded = encode_exchange_command_payload(command)
    decoded = decode_exchange_command_payload(encoded)

    assert decoded["parameters"] == {"Identity": "Melek.Baş@example.com"}


def test_build_exchange_powershell_script_uses_base64_payload_not_raw_parameters():
    command = ExchangePowerShellCommand(
        name="Get-EXOMailbox",
        parameters={"Identity": "user@example.com; Remove-Mailbox evil@example.com"},
    )

    script = build_exchange_powershell_script(command)

    assert "FromBase64String" in script
    assert "ConvertFrom-Json -AsHashtable" in script
    assert "Get-EXOMailbox @params" in script
    assert "Remove-Mailbox evil@example.com" not in script
    assert "user@example.com; Remove-Mailbox evil@example.com" not in script


def test_build_exchange_powershell_script_contains_only_allowlisted_switch_commands():
    command = ExchangePowerShellCommand(
        name="Get-EXOMailboxStatistics",
        parameters={"Identity": "user@example.com"},
    )

    script = build_exchange_powershell_script(command)

    assert "'Get-EXOMailbox'" in script
    assert "'Get-EXOMailboxStatistics'" in script
    assert "'Get-Mailbox'" in script
    assert "Set-Mailbox" not in script
    assert "Enable-Mailbox" not in script
    assert "Remove-Mailbox" not in script
    assert "Add-MailboxPermission" not in script


def test_build_exchange_powershell_script_flattens_mailbox_statistics_total_item_size():
    command = ExchangePowerShellCommand(
        name="Get-EXOMailboxStatistics",
        parameters={"Identity": "user@example.com"},
    )

    script = build_exchange_powershell_script(command)

    assert "Get-EXOMailboxStatistics @params" in script
    assert "Select-Object" in script
    assert "TotalItemSize" in script
    assert "$_.TotalItemSize.ToString()" in script
    assert "ItemCount" in script
    # Statistics output must be projected before serialization, not piped raw,
    # because the raw ByteQuantifiedSize type serializes as
    # {IsUnlimited: False, Value: {}} via ConvertTo-Json.
    assert "$result = Get-EXOMailboxStatistics @params" not in script


def test_build_exchange_powershell_script_rejects_forbidden_command():
    command = ExchangePowerShellCommand(
        name="Set-Mailbox",
        parameters={"Identity": "user@example.com"},
    )

    with pytest.raises(
        ExchangeCommandValidationError,
        match="forbidden for inspectors",
    ):
        build_exchange_powershell_script(command)


def test_build_exchange_powershell_script_rejects_unknown_get_command():
    command = ExchangePowerShellCommand(
        name="Get-InboxRule",
        parameters={"Mailbox": "user@example.com"},
    )

    with pytest.raises(
        ExchangeCommandValidationError,
        match="not allowlisted for inspectors",
    ):
        build_exchange_powershell_script(command)


def test_build_exchange_powershell_invocation_returns_noninteractive_pwsh_args():
    command = ExchangePowerShellCommand(
        name="Get-EXOMailbox",
        parameters={"Identity": "user@example.com"},
    )

    invocation = build_exchange_powershell_invocation(
        command,
        executable="pwsh",
    )

    assert invocation.executable == "pwsh"
    assert invocation.argv[0] == "pwsh"
    assert "-NoProfile" in invocation.argv
    assert "-NonInteractive" in invocation.argv
    assert "-Command" in invocation.argv
    assert invocation.argv[-1] == invocation.script
    assert invocation.script == build_exchange_powershell_script(command)


def test_build_exchange_powershell_invocation_rejects_empty_executable():
    command = ExchangePowerShellCommand(
        name="Get-EXOMailbox",
        parameters={"Identity": "user@example.com"},
    )

    with pytest.raises(ValueError, match="executable cannot be empty"):
        build_exchange_powershell_invocation(command, executable="   ")


def test_decode_exchange_command_payload_rejects_non_object_json():
    import base64

    encoded = base64.b64encode(b'["not", "object"]').decode("ascii")

    with pytest.raises(ValueError, match="must decode to a JSON object"):
        decode_exchange_command_payload(encoded)