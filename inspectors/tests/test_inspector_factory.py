import pytest

from inspectors.exchange_config import (
    ExchangeInspectorBackend,
    ExchangeInspectorConfigError,
    ExchangeInspectorRuntimeConfig,
)
from inspectors.factory import (
    create_configured_inspector_registry,
    create_configured_inspector_registry_from_env,
)


def make_auth_env() -> dict[str, str]:
    return {
        "WORK_COPILOT_EXCHANGE_AUTH_MODE": "app_certificate_file",
        "WORK_COPILOT_EXCHANGE_APP_ID": "app-id",
        "WORK_COPILOT_EXCHANGE_ORGANIZATION": "example.onmicrosoft.com",
        "WORK_COPILOT_EXCHANGE_CERTIFICATE_PATH": "/secure/cert.pfx",
        "WORK_COPILOT_EXCHANGE_CERTIFICATE_PASSWORD_ENV_VAR": (
            "WORK_COPILOT_EXCHANGE_CERTIFICATE_PASSWORD"
        ),
    }


def make_real_exchange_env() -> dict[str, str]:
    return {
        "WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND": "exchange_online_powershell",
        "WORK_COPILOT_ALLOW_REAL_EXCHANGE_INSPECTOR": "true",
        **make_auth_env(),
    }


def test_create_configured_inspector_registry_uses_mock_backend_by_default():
    configured = create_configured_inspector_registry_from_env({})

    assert configured.exchange_backend == ExchangeInspectorBackend.MOCK
    assert configured.allow_real_external_calls is False
    assert configured.is_mock is True
    assert configured.is_disabled is False
    assert configured.uses_real_external_backend is False
    assert configured.registry.get("exchange.mailbox.inspect") is not None


def test_create_configured_inspector_registry_can_disable_exchange_inspector():
    configured = create_configured_inspector_registry_from_env(
        {
            "WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND": "disabled",
        }
    )

    assert configured.exchange_backend == ExchangeInspectorBackend.DISABLED
    assert configured.is_disabled is True
    assert configured.registry.get("exchange.mailbox.inspect") is None


def test_create_configured_inspector_registry_rejects_real_backend_without_double_opt_in():
    with pytest.raises(
        ExchangeInspectorConfigError,
        match="requires WORK_COPILOT_ALLOW_REAL_EXCHANGE_INSPECTOR=true",
    ):
        create_configured_inspector_registry_from_env(
            {
                "WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND": "exchange_online_powershell",
                "WORK_COPILOT_ALLOW_REAL_EXCHANGE_INSPECTOR": "false",
                **make_auth_env(),
            }
        )


def test_create_configured_inspector_registry_rejects_real_backend_without_auth_config():
    with pytest.raises(
        ExchangeInspectorConfigError,
        match="auth",
    ):
        create_configured_inspector_registry_from_env(
            {
                "WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND": "exchange_online_powershell",
                "WORK_COPILOT_ALLOW_REAL_EXCHANGE_INSPECTOR": "true",
            }
        )


def test_create_configured_inspector_registry_registers_real_backend_with_double_opt_in():
    configured = create_configured_inspector_registry_from_env(make_real_exchange_env())

    assert configured.exchange_backend == ExchangeInspectorBackend.EXCHANGE_ONLINE_POWERSHELL
    assert configured.allow_real_external_calls is True
    assert configured.uses_real_external_backend is True
    assert configured.registry.get("exchange.mailbox.inspect") is not None


def test_create_configured_inspector_registry_passes_custom_runner_settings():
    configured = create_configured_inspector_registry_from_env(
        {
            **make_real_exchange_env(),
            "WORK_COPILOT_EXCHANGE_POWERSHELL_EXECUTABLE": "/usr/bin/pwsh",
            "WORK_COPILOT_EXCHANGE_POWERSHELL_TIMEOUT_SECONDS": "120",
        }
    )

    assert configured.uses_real_external_backend is True
    assert configured.registry.get("exchange.mailbox.inspect") is not None


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
        "abc",
    ],
)
def test_create_configured_inspector_registry_rejects_invalid_timeout(value):
    with pytest.raises(
        ExchangeInspectorConfigError,
        match="WORK_COPILOT_EXCHANGE_POWERSHELL_TIMEOUT_SECONDS must be a positive integer",
    ):
        create_configured_inspector_registry_from_env(
            {
                "WORK_COPILOT_EXCHANGE_POWERSHELL_TIMEOUT_SECONDS": value,
            }
        )


def test_create_configured_inspector_registry_from_runtime_config_mock():
    configured = create_configured_inspector_registry(
        runtime_config=ExchangeInspectorRuntimeConfig(
            backend=ExchangeInspectorBackend.MOCK,
            allow_real_external_calls=False,
        )
    )

    assert configured.is_mock is True
    assert configured.registry.get("exchange.mailbox.inspect") is not None


def test_create_configured_inspector_registry_from_runtime_config_disabled():
    configured = create_configured_inspector_registry(
        runtime_config=ExchangeInspectorRuntimeConfig(
            backend=ExchangeInspectorBackend.DISABLED,
            allow_real_external_calls=False,
        )
    )

    assert configured.is_disabled is True
    assert configured.registry.get("exchange.mailbox.inspect") is None


_ACTIVE_DIRECTORY_INSPECTOR_IDS = (
    "active_directory.user.inspect",
    "active_directory.group.inspect",
    "active_directory.group_membership.inspect",
)


def test_mock_backend_includes_active_directory_inspectors():
    configured = create_configured_inspector_registry_from_env({})

    assert configured.is_mock is True
    assert configured.registry.get("exchange.mailbox.inspect") is not None

    for inspector_id in _ACTIVE_DIRECTORY_INSPECTOR_IDS:
        assert configured.registry.get(inspector_id) is not None, (
            f"Expected {inspector_id} to be registered under mock backend"
        )


def test_real_exchange_backend_includes_active_directory_inspectors():
    configured = create_configured_inspector_registry_from_env(
        make_real_exchange_env()
    )

    assert configured.uses_real_external_backend is True
    assert configured.registry.get("exchange.mailbox.inspect") is not None

    for inspector_id in _ACTIVE_DIRECTORY_INSPECTOR_IDS:
        assert configured.registry.get(inspector_id) is not None, (
            f"Expected {inspector_id} to be registered under real Exchange backend"
        )


def test_disabled_exchange_backend_still_registers_active_directory_inspectors():
    configured = create_configured_inspector_registry_from_env(
        {
            "WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND": "disabled",
        }
    )

    assert configured.is_disabled is True
    # Exchange inspector remains absent under the disabled backend.
    assert configured.registry.get("exchange.mailbox.inspect") is None

    # AD inspectors are mock-only and remain available regardless of
    # Exchange backend.
    for inspector_id in _ACTIVE_DIRECTORY_INSPECTOR_IDS:
        assert configured.registry.get(inspector_id) is not None, (
            f"Expected {inspector_id} to remain registered under disabled "
            "Exchange backend"
        )