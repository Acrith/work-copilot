import os
from collections.abc import Mapping
from dataclasses import dataclass

from inspectors.exchange_auth_config import (
    ExchangePowerShellAuthConfig,
    ExchangePowerShellAuthConfigError,
    ExchangePowerShellAuthMode,
    load_exchange_powershell_auth_config,
    validate_exchange_powershell_auth_config,
)
from inspectors.exchange_config import (
    ExchangeInspectorBackend,
    ExchangeInspectorConfigError,
    ExchangeInspectorRuntimeConfig,
    load_exchange_inspector_runtime_config,
)
from inspectors.exchange_mailbox import inspect_exchange_mailbox
from inspectors.exchange_online_powershell import (
    ExchangeOnlinePowerShellConfig,
    ExchangeOnlinePowerShellMailboxClient,
)
from inspectors.exchange_powershell_runner import (
    ExchangePowerShellRunnerConfig,
    ExchangePowerShellSubprocessRunner,
)
from inspectors.mock import create_mock_inspector_registry
from inspectors.registry import InspectorRegistry


@dataclass(frozen=True)
class ConfiguredInspectorRegistry:
    registry: InspectorRegistry
    exchange_backend: ExchangeInspectorBackend
    allow_real_external_calls: bool

    @property
    def is_mock(self) -> bool:
        return self.exchange_backend == ExchangeInspectorBackend.MOCK

    @property
    def is_disabled(self) -> bool:
        return self.exchange_backend == ExchangeInspectorBackend.DISABLED

    @property
    def uses_real_external_backend(self) -> bool:
        return self.exchange_backend == ExchangeInspectorBackend.EXCHANGE_ONLINE_POWERSHELL


def create_configured_inspector_registry(
    *,
    runtime_config: ExchangeInspectorRuntimeConfig,
    powershell_executable: str = "pwsh",
    powershell_timeout_seconds: int = 60,
    auth_config: ExchangePowerShellAuthConfig | None = None,
) -> ConfiguredInspectorRegistry:
    if runtime_config.backend == ExchangeInspectorBackend.DISABLED:
        return ConfiguredInspectorRegistry(
            registry=InspectorRegistry(),
            exchange_backend=runtime_config.backend,
            allow_real_external_calls=runtime_config.allow_real_external_calls,
        )

    if runtime_config.backend == ExchangeInspectorBackend.MOCK:
        return ConfiguredInspectorRegistry(
            registry=create_mock_inspector_registry(),
            exchange_backend=runtime_config.backend,
            allow_real_external_calls=runtime_config.allow_real_external_calls,
        )

    if runtime_config.backend == ExchangeInspectorBackend.EXCHANGE_ONLINE_POWERSHELL:
        registry = InspectorRegistry()
        resolved_auth_config = auth_config or _load_required_exchange_auth_config()

        runner = ExchangePowerShellSubprocessRunner(
            ExchangePowerShellRunnerConfig(
                runtime_config=runtime_config,
                executable=powershell_executable,
                timeout_seconds=powershell_timeout_seconds,
                auth_config=resolved_auth_config,
            )
        )
        client = ExchangeOnlinePowerShellMailboxClient(
            config=ExchangeOnlinePowerShellConfig(enabled=True),
            runner=runner,
        )

        registry.register(
            "exchange.mailbox.inspect",
            lambda request: inspect_exchange_mailbox(request, client),
        )

        return ConfiguredInspectorRegistry(
            registry=registry,
            exchange_backend=runtime_config.backend,
            allow_real_external_calls=runtime_config.allow_real_external_calls,
        )

    raise ExchangeInspectorConfigError(
        f"Unsupported Exchange inspector backend: {runtime_config.backend}"
    )


def create_configured_inspector_registry_from_env(
    environ: Mapping[str, str] | None = None,
) -> ConfiguredInspectorRegistry:
    if environ is None:
        environ = os.environ

    runtime_config = load_exchange_inspector_runtime_config(environ)

    auth_config = None
    if runtime_config.backend == ExchangeInspectorBackend.EXCHANGE_ONLINE_POWERSHELL:
        auth_config = _load_required_exchange_auth_config(environ)

    return create_configured_inspector_registry(
        runtime_config=runtime_config,
        powershell_executable=environ.get(
            "WORK_COPILOT_EXCHANGE_POWERSHELL_EXECUTABLE",
            "pwsh",
        ),
        powershell_timeout_seconds=_parse_positive_int(
            environ.get("WORK_COPILOT_EXCHANGE_POWERSHELL_TIMEOUT_SECONDS", "60"),
            setting_name="WORK_COPILOT_EXCHANGE_POWERSHELL_TIMEOUT_SECONDS",
        ),
        auth_config=auth_config,
    )


def _load_required_exchange_auth_config(
    environ: Mapping[str, str] | None = None,
) -> ExchangePowerShellAuthConfig:
    try:
        auth_config = load_exchange_powershell_auth_config(environ)
    except ExchangePowerShellAuthConfigError as exc:
        raise ExchangeInspectorConfigError(
            f"Invalid Exchange PowerShell auth config: {exc}"
        ) from exc

    if auth_config.mode == ExchangePowerShellAuthMode.DISABLED:
        raise ExchangeInspectorConfigError(
            "Real Exchange inspector backend requires Exchange PowerShell auth config."
        )

    try:
        validate_exchange_powershell_auth_config(auth_config)
    except ExchangePowerShellAuthConfigError as exc:
        raise ExchangeInspectorConfigError(
            f"Invalid Exchange PowerShell auth config: {exc}"
        ) from exc

    return auth_config


def _parse_positive_int(value: str, *, setting_name: str) -> int:
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise ExchangeInspectorConfigError(
            f"{setting_name} must be a positive integer."
        ) from exc

    if parsed <= 0:
        raise ExchangeInspectorConfigError(
            f"{setting_name} must be a positive integer."
        )

    return parsed