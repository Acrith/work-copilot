import pytest

from inspectors.active_directory_config import (
    ActiveDirectoryInspectorBackend,
    ActiveDirectoryInspectorConfigError,
)
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

    # AD inspectors default to mock and remain available regardless of
    # Exchange backend.
    for inspector_id in _ACTIVE_DIRECTORY_INSPECTOR_IDS:
        assert configured.registry.get(inspector_id) is not None, (
            f"Expected {inspector_id} to remain registered under disabled "
            "Exchange backend"
        )


# --------------------- Independent AD backend wiring ---------------------


def test_default_env_uses_exchange_mock_and_active_directory_mock():
    configured = create_configured_inspector_registry_from_env({})

    assert configured.exchange_backend == ExchangeInspectorBackend.MOCK
    assert configured.active_directory_backend == (
        ActiveDirectoryInspectorBackend.MOCK
    )
    assert configured.active_directory_is_mock is True
    assert configured.active_directory_is_disabled is False
    assert configured.uses_real_active_directory_backend is False
    assert configured.allow_real_active_directory_calls is False


def test_disabled_active_directory_backend_removes_active_directory_inspectors():
    configured = create_configured_inspector_registry_from_env(
        {
            "WORK_COPILOT_AD_INSPECTOR_BACKEND": "disabled",
        }
    )

    assert configured.active_directory_backend == (
        ActiveDirectoryInspectorBackend.DISABLED
    )
    assert configured.active_directory_is_disabled is True

    for inspector_id in _ACTIVE_DIRECTORY_INSPECTOR_IDS:
        assert configured.registry.get(inspector_id) is None, (
            f"Expected {inspector_id} to be absent under disabled AD backend"
        )

    # Exchange default behavior is preserved.
    assert configured.exchange_backend == ExchangeInspectorBackend.MOCK
    assert configured.registry.get("exchange.mailbox.inspect") is not None


def test_real_active_directory_backend_requires_double_opt_in():
    with pytest.raises(
        ActiveDirectoryInspectorConfigError,
        match="requires WORK_COPILOT_ALLOW_REAL_AD_INSPECTOR=true",
    ):
        create_configured_inspector_registry_from_env(
            {
                "WORK_COPILOT_AD_INSPECTOR_BACKEND": "active_directory_powershell",
                "WORK_COPILOT_ALLOW_REAL_AD_INSPECTOR": "false",
            }
        )


def _real_ad_env() -> dict[str, str]:
    return {
        "WORK_COPILOT_AD_INSPECTOR_BACKEND": "active_directory_powershell",
        "WORK_COPILOT_ALLOW_REAL_AD_INSPECTOR": "true",
    }


def test_real_active_directory_backend_registers_inspectors():
    configured = create_configured_inspector_registry_from_env(_real_ad_env())

    assert configured.active_directory_backend == (
        ActiveDirectoryInspectorBackend.ACTIVE_DIRECTORY_POWERSHELL
    )
    assert configured.uses_real_active_directory_backend is True
    assert configured.allow_real_active_directory_calls is True

    for inspector_id in _ACTIVE_DIRECTORY_INSPECTOR_IDS:
        assert configured.registry.get(inspector_id) is not None, (
            f"Expected {inspector_id} to be registered under real AD backend"
        )

    # Exchange remains on its default mock backend; AD config is independent.
    assert configured.exchange_backend == ExchangeInspectorBackend.MOCK


def test_real_exchange_with_mock_active_directory():
    configured = create_configured_inspector_registry_from_env(
        make_real_exchange_env()
    )

    assert configured.uses_real_external_backend is True
    assert configured.active_directory_backend == (
        ActiveDirectoryInspectorBackend.MOCK
    )
    assert configured.uses_real_active_directory_backend is False
    assert configured.registry.get("exchange.mailbox.inspect") is not None

    for inspector_id in _ACTIVE_DIRECTORY_INSPECTOR_IDS:
        assert configured.registry.get(inspector_id) is not None


def test_mock_exchange_with_real_active_directory():
    configured = create_configured_inspector_registry_from_env(_real_ad_env())

    assert configured.exchange_backend == ExchangeInspectorBackend.MOCK
    assert configured.uses_real_external_backend is False
    assert configured.uses_real_active_directory_backend is True
    assert configured.registry.get("exchange.mailbox.inspect") is not None

    for inspector_id in _ACTIVE_DIRECTORY_INSPECTOR_IDS:
        assert configured.registry.get(inspector_id) is not None


def test_disabled_exchange_with_real_active_directory():
    configured = create_configured_inspector_registry_from_env(
        {
            "WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND": "disabled",
            **_real_ad_env(),
        }
    )

    assert configured.is_disabled is True
    assert configured.uses_real_active_directory_backend is True
    assert configured.registry.get("exchange.mailbox.inspect") is None

    for inspector_id in _ACTIVE_DIRECTORY_INSPECTOR_IDS:
        assert configured.registry.get(inspector_id) is not None


def test_real_active_directory_backend_accepts_custom_executable_and_timeout():
    configured = create_configured_inspector_registry_from_env(
        {
            **_real_ad_env(),
            "WORK_COPILOT_AD_POWERSHELL_EXECUTABLE": "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
            "WORK_COPILOT_AD_POWERSHELL_TIMEOUT_SECONDS": "120",
        }
    )

    assert configured.uses_real_active_directory_backend is True

    # The real AD inspectors must be registered with a runner that accepted
    # the custom executable + timeout. We don't run subprocess here; we only
    # assert successful construction.
    for inspector_id in _ACTIVE_DIRECTORY_INSPECTOR_IDS:
        assert configured.registry.get(inspector_id) is not None


@pytest.mark.parametrize("value", ["0", "-1", "abc"])
def test_real_active_directory_backend_rejects_invalid_timeout(value):
    with pytest.raises(
        ActiveDirectoryInspectorConfigError,
        match=(
            "WORK_COPILOT_AD_POWERSHELL_TIMEOUT_SECONDS must be a "
            "positive integer"
        ),
    ):
        create_configured_inspector_registry_from_env(
            {
                **_real_ad_env(),
                "WORK_COPILOT_AD_POWERSHELL_TIMEOUT_SECONDS": value,
            }
        )
