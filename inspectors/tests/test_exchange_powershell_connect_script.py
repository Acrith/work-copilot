import pytest

from inspectors.exchange_auth_config import (
    ExchangePowerShellAuthConfig,
    ExchangePowerShellAuthMode,
)
from inspectors.exchange_command_runner import ExchangePowerShellCommand
from inspectors.exchange_powershell_script import (
    build_exchange_connect_preamble,
    build_exchange_powershell_invocation,
    build_exchange_powershell_script,
    decode_exchange_auth_payload,
    encode_exchange_auth_payload,
)


def test_encode_exchange_auth_payload_thumbprint_round_trips_without_password():
    auth_config = ExchangePowerShellAuthConfig(
        mode=ExchangePowerShellAuthMode.APP_CERTIFICATE_THUMBPRINT,
        app_id="app-id",
        organization="example.onmicrosoft.com",
        certificate_thumbprint="thumbprint",
    )

    encoded = encode_exchange_auth_payload(auth_config)
    decoded = decode_exchange_auth_payload(encoded)

    assert decoded == {
        "mode": "app_certificate_thumbprint",
        "app_id": "app-id",
        "organization": "example.onmicrosoft.com",
        "certificate_thumbprint": "thumbprint",
    }


def test_encode_exchange_auth_payload_file_round_trips_env_var_name_not_password():
    auth_config = ExchangePowerShellAuthConfig(
        mode=ExchangePowerShellAuthMode.APP_CERTIFICATE_FILE,
        app_id="app-id",
        organization="example.onmicrosoft.com",
        certificate_path="/secure/cert.pfx",
        certificate_password_env_var="WORK_COPILOT_EXCHANGE_CERTIFICATE_PASSWORD",
    )

    encoded = encode_exchange_auth_payload(auth_config)
    decoded = decode_exchange_auth_payload(encoded)

    assert decoded == {
        "mode": "app_certificate_file",
        "app_id": "app-id",
        "organization": "example.onmicrosoft.com",
        "certificate_path": "/secure/cert.pfx",
        "certificate_password_env_var": "WORK_COPILOT_EXCHANGE_CERTIFICATE_PASSWORD",
    }
    assert "certificate-password-value" not in str(decoded)


def test_build_exchange_connect_preamble_thumbprint_contains_connect_command():
    auth_config = ExchangePowerShellAuthConfig(
        mode=ExchangePowerShellAuthMode.APP_CERTIFICATE_THUMBPRINT,
        app_id="app-id",
        organization="example.onmicrosoft.com",
        certificate_thumbprint="secret-thumbprint",
    )

    preamble = build_exchange_connect_preamble(auth_config)

    assert "Import-Module ExchangeOnlineManagement -ErrorAction Stop" in preamble
    assert "Connect-ExchangeOnline" in preamble
    assert "-AppId $auth.app_id" in preamble
    assert "-CertificateThumbprint $auth.certificate_thumbprint" in preamble
    assert "-Organization $auth.organization" in preamble
    assert "-ShowBanner:$false" in preamble
    assert "app-id" not in preamble
    assert "secret-thumbprint" not in preamble


def test_build_exchange_connect_preamble_file_uses_password_env_var():
    auth_config = ExchangePowerShellAuthConfig(
        mode=ExchangePowerShellAuthMode.APP_CERTIFICATE_FILE,
        app_id="app-id",
        organization="example.onmicrosoft.com",
        certificate_path="/secure/cert.pfx",
        certificate_password_env_var="WORK_COPILOT_EXCHANGE_CERTIFICATE_PASSWORD",
    )

    preamble = build_exchange_connect_preamble(auth_config)

    assert "Connect-ExchangeOnline" in preamble
    assert "-CertificateFilePath $auth.certificate_path" in preamble
    assert "-CertificatePassword $certificatePassword" in preamble
    assert "[Environment]::GetEnvironmentVariable($auth.certificate_password_env_var)" in preamble
    assert "ConvertTo-SecureString" in preamble
    assert "WORK_COPILOT_EXCHANGE_CERTIFICATE_PASSWORD" not in preamble
    assert "/secure/cert.pfx" not in preamble


def test_build_exchange_connect_preamble_rejects_disabled_auth():
    auth_config = ExchangePowerShellAuthConfig(
        mode=ExchangePowerShellAuthMode.DISABLED,
    )

    with pytest.raises(ValueError, match="auth config is disabled"):
        build_exchange_connect_preamble(auth_config)


def test_build_exchange_powershell_script_can_include_auth_preamble():
    command = ExchangePowerShellCommand(
        name="Get-EXOMailbox",
        parameters={"Identity": "user@example.com"},
    )
    auth_config = ExchangePowerShellAuthConfig(
        mode=ExchangePowerShellAuthMode.APP_CERTIFICATE_THUMBPRINT,
        app_id="app-id",
        organization="example.onmicrosoft.com",
        certificate_thumbprint="thumbprint",
    )

    script = build_exchange_powershell_script(command, auth_config=auth_config)

    assert "Import-Module ExchangeOnlineManagement" in script
    assert "Connect-ExchangeOnline" in script
    assert "Get-EXOMailbox @params" in script
    assert script.index("Connect-ExchangeOnline") < script.index("Get-EXOMailbox @params")


def test_build_exchange_powershell_invocation_accepts_auth_config():
    command = ExchangePowerShellCommand(
        name="Get-EXOMailbox",
        parameters={"Identity": "user@example.com"},
    )
    auth_config = ExchangePowerShellAuthConfig(
        mode=ExchangePowerShellAuthMode.APP_CERTIFICATE_THUMBPRINT,
        app_id="app-id",
        organization="example.onmicrosoft.com",
        certificate_thumbprint="thumbprint",
    )

    invocation = build_exchange_powershell_invocation(
        command,
        executable="pwsh",
        auth_config=auth_config,
    )

    assert invocation.argv[0] == "pwsh"
    assert invocation.argv[-1] == invocation.script
    assert "Connect-ExchangeOnline" in invocation.script


def test_decode_exchange_auth_payload_rejects_non_object_json():
    import base64

    encoded = base64.b64encode(b'["not", "object"]').decode("ascii")

    with pytest.raises(ValueError, match="must decode to a JSON object"):
        decode_exchange_auth_payload(encoded)