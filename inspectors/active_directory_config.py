import os
from dataclasses import dataclass
from enum import StrEnum


class ActiveDirectoryInspectorBackend(StrEnum):
    MOCK = "mock"
    DISABLED = "disabled"
    ACTIVE_DIRECTORY_POWERSHELL = "active_directory_powershell"


class ActiveDirectoryInspectorConfigError(ValueError):
    """Raised when AD inspector configuration is unsafe or invalid."""


@dataclass(frozen=True)
class ActiveDirectoryInspectorRuntimeConfig:
    backend: ActiveDirectoryInspectorBackend = ActiveDirectoryInspectorBackend.MOCK
    allow_real_external_calls: bool = False

    @property
    def uses_real_external_backend(self) -> bool:
        return (
            self.backend
            == ActiveDirectoryInspectorBackend.ACTIVE_DIRECTORY_POWERSHELL
        )

    @property
    def is_enabled(self) -> bool:
        return self.backend != ActiveDirectoryInspectorBackend.DISABLED


def load_active_directory_inspector_runtime_config(
    environ: dict[str, str] | None = None,
) -> ActiveDirectoryInspectorRuntimeConfig:
    if environ is None:
        environ = dict(os.environ)

    backend = _parse_backend(
        environ.get("WORK_COPILOT_AD_INSPECTOR_BACKEND", "mock")
    )
    allow_real_external_calls = _parse_bool(
        environ.get("WORK_COPILOT_ALLOW_REAL_AD_INSPECTOR", "false")
    )

    config = ActiveDirectoryInspectorRuntimeConfig(
        backend=backend,
        allow_real_external_calls=allow_real_external_calls,
    )
    validate_active_directory_inspector_runtime_config(config)

    return config


def validate_active_directory_inspector_runtime_config(
    config: ActiveDirectoryInspectorRuntimeConfig,
) -> None:
    if config.uses_real_external_backend and not config.allow_real_external_calls:
        raise ActiveDirectoryInspectorConfigError(
            "Active Directory PowerShell inspector backend requires "
            "WORK_COPILOT_ALLOW_REAL_AD_INSPECTOR=true."
        )


def _parse_backend(value: str) -> ActiveDirectoryInspectorBackend:
    normalized = value.strip().lower()

    try:
        return ActiveDirectoryInspectorBackend(normalized)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in ActiveDirectoryInspectorBackend)
        raise ActiveDirectoryInspectorConfigError(
            f"Unsupported Active Directory inspector backend: {value}. "
            f"Allowed values: {allowed}."
        ) from exc


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()

    if normalized in {"1", "true", "yes", "y", "on"}:
        return True

    if normalized in {"0", "false", "no", "n", "off", ""}:
        return False

    raise ActiveDirectoryInspectorConfigError(
        f"Invalid boolean value for Active Directory inspector config: {value}."
    )
