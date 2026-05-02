import pytest

from inspectors.active_directory_config import (
    ActiveDirectoryInspectorBackend,
    ActiveDirectoryInspectorConfigError,
    ActiveDirectoryInspectorRuntimeConfig,
    load_active_directory_inspector_runtime_config,
    validate_active_directory_inspector_runtime_config,
)


def test_default_config_is_mock_with_no_real_external_calls():
    config = ActiveDirectoryInspectorRuntimeConfig()

    assert config.backend == ActiveDirectoryInspectorBackend.MOCK
    assert config.allow_real_external_calls is False
    assert config.uses_real_external_backend is False
    assert config.is_enabled is True


def test_load_defaults_to_mock_backend_when_env_empty():
    config = load_active_directory_inspector_runtime_config({})

    assert config.backend == ActiveDirectoryInspectorBackend.MOCK
    assert config.allow_real_external_calls is False


def test_load_disabled_backend_makes_inspector_not_enabled():
    config = load_active_directory_inspector_runtime_config(
        {
            "WORK_COPILOT_AD_INSPECTOR_BACKEND": "disabled",
        }
    )

    assert config.backend == ActiveDirectoryInspectorBackend.DISABLED
    assert config.is_enabled is False
    assert config.uses_real_external_backend is False


@pytest.mark.parametrize("value", ["true", "yes", "1", "on", "Y"])
def test_load_parses_truthy_allow_real_external_calls(value):
    config = load_active_directory_inspector_runtime_config(
        {
            "WORK_COPILOT_AD_INSPECTOR_BACKEND": "active_directory_powershell",
            "WORK_COPILOT_ALLOW_REAL_AD_INSPECTOR": value,
        }
    )

    assert config.allow_real_external_calls is True
    assert config.uses_real_external_backend is True


def test_real_backend_requires_double_opt_in():
    with pytest.raises(
        ActiveDirectoryInspectorConfigError,
        match="requires WORK_COPILOT_ALLOW_REAL_AD_INSPECTOR=true",
    ):
        load_active_directory_inspector_runtime_config(
            {
                "WORK_COPILOT_AD_INSPECTOR_BACKEND": "active_directory_powershell",
                "WORK_COPILOT_ALLOW_REAL_AD_INSPECTOR": "false",
            }
        )


def test_real_backend_with_double_opt_in_validates():
    config = load_active_directory_inspector_runtime_config(
        {
            "WORK_COPILOT_AD_INSPECTOR_BACKEND": "active_directory_powershell",
            "WORK_COPILOT_ALLOW_REAL_AD_INSPECTOR": "true",
        }
    )

    assert config.uses_real_external_backend is True
    assert config.allow_real_external_calls is True


def test_unknown_backend_value_is_rejected():
    with pytest.raises(
        ActiveDirectoryInspectorConfigError,
        match="Unsupported Active Directory inspector backend",
    ):
        load_active_directory_inspector_runtime_config(
            {
                "WORK_COPILOT_AD_INSPECTOR_BACKEND": "graph",
            }
        )


def test_invalid_boolean_value_is_rejected():
    with pytest.raises(
        ActiveDirectoryInspectorConfigError,
        match="Invalid boolean value",
    ):
        load_active_directory_inspector_runtime_config(
            {
                "WORK_COPILOT_ALLOW_REAL_AD_INSPECTOR": "maybe",
            }
        )


def test_validate_runtime_config_rejects_real_backend_without_opt_in():
    config = ActiveDirectoryInspectorRuntimeConfig(
        backend=ActiveDirectoryInspectorBackend.ACTIVE_DIRECTORY_POWERSHELL,
        allow_real_external_calls=False,
    )

    with pytest.raises(
        ActiveDirectoryInspectorConfigError,
        match="requires WORK_COPILOT_ALLOW_REAL_AD_INSPECTOR=true",
    ):
        validate_active_directory_inspector_runtime_config(config)
