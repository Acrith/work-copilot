import pytest

from inspectors.exchange_auth_config import (
    ExchangePowerShellAuthConfig,
    ExchangePowerShellAuthConfigError,
    ExchangePowerShellAuthMode,
    load_exchange_powershell_auth_config,
    redacted_exchange_powershell_auth_config,
    validate_exchange_powershell_auth_config,
)


def test_default_exchange_auth_config_is_disabled():
    config = load_exchange_powershell_auth_config({})

    assert config.mode == ExchangePowerShellAuthMode.DISABLED
    assert config.is_enabled is False
    assert config.uses_certificate_thumbprint is False
    assert config.uses_certificate_file is False


def test_thumbprint_auth_config_loads_when_required_values_present():
    config = load_exchange_powershell_auth_config(
        {
            "WORK_COPILOT_EXCHANGE_AUTH_MODE": "app_certificate_thumbprint",
            "WORK_COPILOT_EXCHANGE_APP_ID": "app-id",
            "WORK_COPILOT_EXCHANGE_ORGANIZATION": "example.onmicrosoft.com",
            "WORK_COPILOT_EXCHANGE_CERTIFICATE_THUMBPRINT": "thumbprint",
        }
    )

    assert config.mode == ExchangePowerShellAuthMode.APP_CERTIFICATE_THUMBPRINT
    assert config.is_enabled is True
    assert config.uses_certificate_thumbprint is True
    assert config.app_id == "app-id"
    assert config.organization == "example.onmicrosoft.com"
    assert config.certificate_thumbprint == "thumbprint"
    assert config.certificate_path is None


def test_file_auth_config_loads_when_required_values_present():
    config = load_exchange_powershell_auth_config(
        {
            "WORK_COPILOT_EXCHANGE_AUTH_MODE": "app_certificate_file",
            "WORK_COPILOT_EXCHANGE_APP_ID": "app-id",
            "WORK_COPILOT_EXCHANGE_ORGANIZATION": "example.onmicrosoft.com",
            "WORK_COPILOT_EXCHANGE_CERTIFICATE_PATH": "/secure/cert.pfx",
        }
    )

    assert config.mode == ExchangePowerShellAuthMode.APP_CERTIFICATE_FILE
    assert config.is_enabled is True
    assert config.uses_certificate_file is True
    assert config.app_id == "app-id"
    assert config.organization == "example.onmicrosoft.com"
    assert config.certificate_path == "/secure/cert.pfx"
    assert config.certificate_thumbprint is None


@pytest.mark.parametrize(
    "missing_key",
    [
        "WORK_COPILOT_EXCHANGE_APP_ID",
        "WORK_COPILOT_EXCHANGE_ORGANIZATION",
        "WORK_COPILOT_EXCHANGE_CERTIFICATE_THUMBPRINT",
    ],
)
def test_thumbprint_auth_config_requires_values(missing_key):
    env = {
        "WORK_COPILOT_EXCHANGE_AUTH_MODE": "app_certificate_thumbprint",
        "WORK_COPILOT_EXCHANGE_APP_ID": "app-id",
        "WORK_COPILOT_EXCHANGE_ORGANIZATION": "example.onmicrosoft.com",
        "WORK_COPILOT_EXCHANGE_CERTIFICATE_THUMBPRINT": "thumbprint",
    }
    env.pop(missing_key)

    with pytest.raises(
        ExchangePowerShellAuthConfigError,
        match=f"{missing_key} is required",
    ):
        load_exchange_powershell_auth_config(env)


@pytest.mark.parametrize(
    "missing_key",
    [
        "WORK_COPILOT_EXCHANGE_APP_ID",
        "WORK_COPILOT_EXCHANGE_ORGANIZATION",
        "WORK_COPILOT_EXCHANGE_CERTIFICATE_PATH",
    ],
)
def test_file_auth_config_requires_values(missing_key):
    env = {
        "WORK_COPILOT_EXCHANGE_AUTH_MODE": "app_certificate_file",
        "WORK_COPILOT_EXCHANGE_APP_ID": "app-id",
        "WORK_COPILOT_EXCHANGE_ORGANIZATION": "example.onmicrosoft.com",
        "WORK_COPILOT_EXCHANGE_CERTIFICATE_PATH": "/secure/cert.pfx",
    }
    env.pop(missing_key)

    with pytest.raises(
        ExchangePowerShellAuthConfigError,
        match=f"{missing_key} is required",
    ):
        load_exchange_powershell_auth_config(env)


def test_thumbprint_auth_rejects_certificate_path():
    with pytest.raises(
        ExchangePowerShellAuthConfigError,
        match="Do not set WORK_COPILOT_EXCHANGE_CERTIFICATE_PATH",
    ):
        load_exchange_powershell_auth_config(
            {
                "WORK_COPILOT_EXCHANGE_AUTH_MODE": "app_certificate_thumbprint",
                "WORK_COPILOT_EXCHANGE_APP_ID": "app-id",
                "WORK_COPILOT_EXCHANGE_ORGANIZATION": "example.onmicrosoft.com",
                "WORK_COPILOT_EXCHANGE_CERTIFICATE_THUMBPRINT": "thumbprint",
                "WORK_COPILOT_EXCHANGE_CERTIFICATE_PATH": "/secure/cert.pfx",
            }
        )


def test_file_auth_rejects_certificate_thumbprint():
    with pytest.raises(
        ExchangePowerShellAuthConfigError,
        match="Do not set WORK_COPILOT_EXCHANGE_CERTIFICATE_THUMBPRINT",
    ):
        load_exchange_powershell_auth_config(
            {
                "WORK_COPILOT_EXCHANGE_AUTH_MODE": "app_certificate_file",
                "WORK_COPILOT_EXCHANGE_APP_ID": "app-id",
                "WORK_COPILOT_EXCHANGE_ORGANIZATION": "example.onmicrosoft.com",
                "WORK_COPILOT_EXCHANGE_CERTIFICATE_PATH": "/secure/cert.pfx",
                "WORK_COPILOT_EXCHANGE_CERTIFICATE_THUMBPRINT": "thumbprint",
            }
        )


def test_exchange_auth_config_rejects_unknown_mode():
    with pytest.raises(
        ExchangePowerShellAuthConfigError,
        match="Unsupported Exchange PowerShell auth mode",
    ):
        load_exchange_powershell_auth_config(
            {
                "WORK_COPILOT_EXCHANGE_AUTH_MODE": "delegated",
            }
        )


def test_validate_exchange_auth_config_allows_disabled_without_values():
    validate_exchange_powershell_auth_config(
        ExchangePowerShellAuthConfig(mode=ExchangePowerShellAuthMode.DISABLED)
    )


def test_redacted_exchange_auth_config_does_not_include_secret_values():
    config = ExchangePowerShellAuthConfig(
        mode=ExchangePowerShellAuthMode.APP_CERTIFICATE_THUMBPRINT,
        app_id="real-app-id",
        organization="example.onmicrosoft.com",
        certificate_thumbprint="secret-thumbprint",
    )

    redacted = redacted_exchange_powershell_auth_config(config)

    assert redacted == {
        "mode": "app_certificate_thumbprint",
        "app_id_configured": True,
        "organization_configured": True,
        "certificate_thumbprint_configured": True,
        "certificate_path_configured": False,
    }
    assert "real-app-id" not in str(redacted)
    assert "example.onmicrosoft.com" not in str(redacted)
    assert "secret-thumbprint" not in str(redacted)


def test_empty_strings_are_treated_as_missing_values():
    with pytest.raises(
        ExchangePowerShellAuthConfigError,
        match="WORK_COPILOT_EXCHANGE_APP_ID is required",
    ):
        load_exchange_powershell_auth_config(
            {
                "WORK_COPILOT_EXCHANGE_AUTH_MODE": "app_certificate_thumbprint",
                "WORK_COPILOT_EXCHANGE_APP_ID": "   ",
                "WORK_COPILOT_EXCHANGE_ORGANIZATION": "example.onmicrosoft.com",
                "WORK_COPILOT_EXCHANGE_CERTIFICATE_THUMBPRINT": "thumbprint",
            }
        )