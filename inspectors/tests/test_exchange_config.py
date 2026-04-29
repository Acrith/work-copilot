import pytest

from inspectors.exchange_config import (
    ExchangeInspectorBackend,
    ExchangeInspectorConfigError,
    ExchangeInspectorRuntimeConfig,
    load_exchange_inspector_runtime_config,
    validate_exchange_inspector_runtime_config,
)


def test_default_exchange_inspector_config_is_mock_and_safe():
    config = load_exchange_inspector_runtime_config({})

    assert config.backend == ExchangeInspectorBackend.MOCK
    assert config.allow_real_external_calls is False
    assert config.is_enabled is True
    assert config.uses_real_external_backend is False


def test_exchange_inspector_config_can_be_disabled():
    config = load_exchange_inspector_runtime_config(
        {
            "WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND": "disabled",
        }
    )

    assert config.backend == ExchangeInspectorBackend.DISABLED
    assert config.is_enabled is False
    assert config.uses_real_external_backend is False


def test_exchange_inspector_config_accepts_mock_backend():
    config = load_exchange_inspector_runtime_config(
        {
            "WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND": "mock",
            "WORK_COPILOT_ALLOW_REAL_EXCHANGE_INSPECTOR": "false",
        }
    )

    assert config.backend == ExchangeInspectorBackend.MOCK
    assert config.allow_real_external_calls is False


@pytest.mark.parametrize(
    "value",
    [
        "true",
        "True",
        "1",
        "yes",
        "y",
        "on",
    ],
)
def test_exchange_inspector_config_parses_true_values(value):
    config = load_exchange_inspector_runtime_config(
        {
            "WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND": "mock",
            "WORK_COPILOT_ALLOW_REAL_EXCHANGE_INSPECTOR": value,
        }
    )

    assert config.allow_real_external_calls is True


@pytest.mark.parametrize(
    "value",
    [
        "false",
        "False",
        "0",
        "no",
        "n",
        "off",
        "",
    ],
)
def test_exchange_inspector_config_parses_false_values(value):
    config = load_exchange_inspector_runtime_config(
        {
            "WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND": "mock",
            "WORK_COPILOT_ALLOW_REAL_EXCHANGE_INSPECTOR": value,
        }
    )

    assert config.allow_real_external_calls is False


def test_exchange_online_powershell_backend_requires_explicit_real_call_allow():
    with pytest.raises(
        ExchangeInspectorConfigError,
        match="requires WORK_COPILOT_ALLOW_REAL_EXCHANGE_INSPECTOR=true",
    ):
        load_exchange_inspector_runtime_config(
            {
                "WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND": "exchange_online_powershell",
                "WORK_COPILOT_ALLOW_REAL_EXCHANGE_INSPECTOR": "false",
            }
        )


def test_exchange_online_powershell_backend_allowed_when_explicitly_enabled():
    config = load_exchange_inspector_runtime_config(
        {
            "WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND": "exchange_online_powershell",
            "WORK_COPILOT_ALLOW_REAL_EXCHANGE_INSPECTOR": "true",
        }
    )

    assert config.backend == ExchangeInspectorBackend.EXCHANGE_ONLINE_POWERSHELL
    assert config.allow_real_external_calls is True
    assert config.uses_real_external_backend is True


def test_exchange_inspector_config_rejects_unknown_backend():
    with pytest.raises(
        ExchangeInspectorConfigError,
        match="Unsupported Exchange inspector backend",
    ):
        load_exchange_inspector_runtime_config(
            {
                "WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND": "graph",
            }
        )


def test_exchange_inspector_config_rejects_invalid_boolean():
    with pytest.raises(
        ExchangeInspectorConfigError,
        match="Invalid boolean value",
    ):
        load_exchange_inspector_runtime_config(
            {
                "WORK_COPILOT_ALLOW_REAL_EXCHANGE_INSPECTOR": "maybe",
            }
        )


def test_validate_exchange_inspector_runtime_config_rejects_unsafe_real_backend():
    config = ExchangeInspectorRuntimeConfig(
        backend=ExchangeInspectorBackend.EXCHANGE_ONLINE_POWERSHELL,
        allow_real_external_calls=False,
    )

    with pytest.raises(ExchangeInspectorConfigError):
        validate_exchange_inspector_runtime_config(config)


def test_validate_exchange_inspector_runtime_config_allows_mock_without_real_calls():
    config = ExchangeInspectorRuntimeConfig(
        backend=ExchangeInspectorBackend.MOCK,
        allow_real_external_calls=False,
    )

    validate_exchange_inspector_runtime_config(config)