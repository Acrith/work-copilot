import os
from collections.abc import Mapping
from dataclasses import dataclass

from inspectors.active_directory_command_runner import (
    ActiveDirectoryCommandRunner,
)
from inspectors.active_directory_config import (
    ActiveDirectoryInspectorBackend,
    ActiveDirectoryInspectorConfigError,
    ActiveDirectoryInspectorRuntimeConfig,
    load_active_directory_inspector_runtime_config,
)
from inspectors.active_directory_group import inspect_active_directory_group
from inspectors.active_directory_group_membership import (
    inspect_active_directory_group_membership,
)
from inspectors.active_directory_powershell import (
    ActiveDirectoryPowerShellGroupClient,
    ActiveDirectoryPowerShellGroupMembershipClient,
    ActiveDirectoryPowerShellUserClient,
)
from inspectors.active_directory_powershell_runner import (
    ActiveDirectoryPowerShellRunnerConfig,
    ActiveDirectoryPowerShellSubprocessRunner,
)
from inspectors.active_directory_user import inspect_active_directory_user
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
from inspectors.mock import (
    inspect_mock_active_directory_group,
    inspect_mock_active_directory_group_membership,
    inspect_mock_active_directory_user,
    inspect_mock_exchange_mailbox,
)
from inspectors.registry import InspectorRegistry


@dataclass(frozen=True)
class ConfiguredInspectorRegistry:
    registry: InspectorRegistry
    exchange_backend: ExchangeInspectorBackend
    allow_real_external_calls: bool
    active_directory_backend: ActiveDirectoryInspectorBackend = (
        ActiveDirectoryInspectorBackend.MOCK
    )
    allow_real_active_directory_calls: bool = False

    @property
    def is_mock(self) -> bool:
        return self.exchange_backend == ExchangeInspectorBackend.MOCK

    @property
    def is_disabled(self) -> bool:
        return self.exchange_backend == ExchangeInspectorBackend.DISABLED

    @property
    def uses_real_external_backend(self) -> bool:
        return self.exchange_backend == ExchangeInspectorBackend.EXCHANGE_ONLINE_POWERSHELL

    @property
    def uses_real_active_directory_backend(self) -> bool:
        return (
            self.active_directory_backend
            == ActiveDirectoryInspectorBackend.ACTIVE_DIRECTORY_POWERSHELL
        )

    @property
    def active_directory_is_mock(self) -> bool:
        return (
            self.active_directory_backend == ActiveDirectoryInspectorBackend.MOCK
        )

    @property
    def active_directory_is_disabled(self) -> bool:
        return (
            self.active_directory_backend == ActiveDirectoryInspectorBackend.DISABLED
        )


def create_configured_inspector_registry(
    *,
    runtime_config: ExchangeInspectorRuntimeConfig,
    powershell_executable: str = "pwsh",
    powershell_timeout_seconds: int = 60,
    auth_config: ExchangePowerShellAuthConfig | None = None,
    ad_runtime_config: ActiveDirectoryInspectorRuntimeConfig | None = None,
    ad_powershell_executable: str = "powershell.exe",
    ad_powershell_timeout_seconds: int = 60,
) -> ConfiguredInspectorRegistry:
    if ad_runtime_config is None:
        ad_runtime_config = ActiveDirectoryInspectorRuntimeConfig()

    registry = InspectorRegistry()

    _register_exchange_inspector(
        registry,
        runtime_config=runtime_config,
        powershell_executable=powershell_executable,
        powershell_timeout_seconds=powershell_timeout_seconds,
        auth_config=auth_config,
    )
    _register_active_directory_inspectors(
        registry,
        ad_runtime_config=ad_runtime_config,
        ad_powershell_executable=ad_powershell_executable,
        ad_powershell_timeout_seconds=ad_powershell_timeout_seconds,
    )

    return ConfiguredInspectorRegistry(
        registry=registry,
        exchange_backend=runtime_config.backend,
        allow_real_external_calls=runtime_config.allow_real_external_calls,
        active_directory_backend=ad_runtime_config.backend,
        allow_real_active_directory_calls=(
            ad_runtime_config.allow_real_external_calls
        ),
    )


def _register_exchange_inspector(
    registry: InspectorRegistry,
    *,
    runtime_config: ExchangeInspectorRuntimeConfig,
    powershell_executable: str,
    powershell_timeout_seconds: int,
    auth_config: ExchangePowerShellAuthConfig | None,
) -> None:
    if runtime_config.backend == ExchangeInspectorBackend.DISABLED:
        return

    if runtime_config.backend == ExchangeInspectorBackend.MOCK:
        registry.register(
            "exchange.mailbox.inspect", inspect_mock_exchange_mailbox
        )
        return

    if runtime_config.backend == ExchangeInspectorBackend.EXCHANGE_ONLINE_POWERSHELL:
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
        return

    raise ExchangeInspectorConfigError(
        f"Unsupported Exchange inspector backend: {runtime_config.backend}"
    )


def _register_active_directory_inspectors(
    registry: InspectorRegistry,
    *,
    ad_runtime_config: ActiveDirectoryInspectorRuntimeConfig,
    ad_powershell_executable: str,
    ad_powershell_timeout_seconds: int,
) -> None:
    if ad_runtime_config.backend == ActiveDirectoryInspectorBackend.DISABLED:
        return

    if ad_runtime_config.backend == ActiveDirectoryInspectorBackend.MOCK:
        registry.register(
            "active_directory.user.inspect", inspect_mock_active_directory_user
        )
        registry.register(
            "active_directory.group.inspect", inspect_mock_active_directory_group
        )
        registry.register(
            "active_directory.group_membership.inspect",
            inspect_mock_active_directory_group_membership,
        )
        return

    if (
        ad_runtime_config.backend
        == ActiveDirectoryInspectorBackend.ACTIVE_DIRECTORY_POWERSHELL
    ):
        runner = ActiveDirectoryPowerShellSubprocessRunner(
            ActiveDirectoryPowerShellRunnerConfig(
                runtime_config=ad_runtime_config,
                executable=ad_powershell_executable,
                timeout_seconds=ad_powershell_timeout_seconds,
            )
        )

        _register_real_active_directory_inspectors(registry, runner)
        return

    raise ActiveDirectoryInspectorConfigError(
        "Unsupported Active Directory inspector backend: "
        f"{ad_runtime_config.backend}"
    )


def _register_real_active_directory_inspectors(
    registry: InspectorRegistry,
    runner: ActiveDirectoryCommandRunner,
) -> None:
    user_client = ActiveDirectoryPowerShellUserClient(runner)
    group_client = ActiveDirectoryPowerShellGroupClient(runner)
    membership_client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    registry.register(
        "active_directory.user.inspect",
        lambda request: inspect_active_directory_user(request, user_client),
    )
    registry.register(
        "active_directory.group.inspect",
        lambda request: inspect_active_directory_group(request, group_client),
    )
    registry.register(
        "active_directory.group_membership.inspect",
        lambda request: inspect_active_directory_group_membership(
            request, membership_client
        ),
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

    ad_runtime_config = load_active_directory_inspector_runtime_config(environ)

    return create_configured_inspector_registry(
        runtime_config=runtime_config,
        powershell_executable=environ.get(
            "WORK_COPILOT_EXCHANGE_POWERSHELL_EXECUTABLE",
            "pwsh",
        ),
        powershell_timeout_seconds=_parse_positive_int(
            environ.get("WORK_COPILOT_EXCHANGE_POWERSHELL_TIMEOUT_SECONDS", "60"),
            setting_name="WORK_COPILOT_EXCHANGE_POWERSHELL_TIMEOUT_SECONDS",
            error_cls=ExchangeInspectorConfigError,
        ),
        auth_config=auth_config,
        ad_runtime_config=ad_runtime_config,
        ad_powershell_executable=environ.get(
            "WORK_COPILOT_AD_POWERSHELL_EXECUTABLE",
            "powershell.exe",
        ),
        ad_powershell_timeout_seconds=_parse_positive_int(
            environ.get("WORK_COPILOT_AD_POWERSHELL_TIMEOUT_SECONDS", "60"),
            setting_name="WORK_COPILOT_AD_POWERSHELL_TIMEOUT_SECONDS",
            error_cls=ActiveDirectoryInspectorConfigError,
        ),
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


def _parse_positive_int(
    value: str,
    *,
    setting_name: str,
    error_cls: type[Exception] = ExchangeInspectorConfigError,
) -> int:
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise error_cls(
            f"{setting_name} must be a positive integer."
        ) from exc

    if parsed <= 0:
        raise error_cls(
            f"{setting_name} must be a positive integer."
        )

    return parsed
