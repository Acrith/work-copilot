import os
from dataclasses import dataclass
from enum import StrEnum


class ExchangeInspectorBackend(StrEnum):
    MOCK = "mock"
    DISABLED = "disabled"
    EXCHANGE_ONLINE_POWERSHELL = "exchange_online_powershell"


class ExchangeInspectorConfigError(ValueError):
    """Raised when Exchange inspector configuration is unsafe or invalid."""


@dataclass(frozen=True)
class ExchangeInspectorRuntimeConfig:
    backend: ExchangeInspectorBackend = ExchangeInspectorBackend.MOCK
    allow_real_external_calls: bool = False

    @property
    def uses_real_external_backend(self) -> bool:
        return self.backend == ExchangeInspectorBackend.EXCHANGE_ONLINE_POWERSHELL

    @property
    def is_enabled(self) -> bool:
        return self.backend != ExchangeInspectorBackend.DISABLED


def load_exchange_inspector_runtime_config(
    environ: dict[str, str] | None = None,
) -> ExchangeInspectorRuntimeConfig:
    if environ is None:
        environ = dict(os.environ)

    backend = _parse_backend(
        environ.get("WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND", "mock")
    )
    allow_real_external_calls = _parse_bool(
        environ.get("WORK_COPILOT_ALLOW_REAL_EXCHANGE_INSPECTOR", "false")
    )

    config = ExchangeInspectorRuntimeConfig(
        backend=backend,
        allow_real_external_calls=allow_real_external_calls,
    )
    validate_exchange_inspector_runtime_config(config)

    return config


def validate_exchange_inspector_runtime_config(
    config: ExchangeInspectorRuntimeConfig,
) -> None:
    if config.uses_real_external_backend and not config.allow_real_external_calls:
        raise ExchangeInspectorConfigError(
            "Exchange Online PowerShell inspector backend requires "
            "WORK_COPILOT_ALLOW_REAL_EXCHANGE_INSPECTOR=true."
        )


def _parse_backend(value: str) -> ExchangeInspectorBackend:
    normalized = value.strip().lower()

    try:
        return ExchangeInspectorBackend(normalized)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in ExchangeInspectorBackend)
        raise ExchangeInspectorConfigError(
            f"Unsupported Exchange inspector backend: {value}. "
            f"Allowed values: {allowed}."
        ) from exc


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()

    if normalized in {"1", "true", "yes", "y", "on"}:
        return True

    if normalized in {"0", "false", "no", "n", "off", ""}:
        return False

    raise ExchangeInspectorConfigError(
        f"Invalid boolean value for Exchange inspector config: {value}."
    )