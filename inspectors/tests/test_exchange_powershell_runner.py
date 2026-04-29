import pytest

from inspectors.exchange_command_runner import ExchangePowerShellCommand
from inspectors.exchange_config import (
    ExchangeInspectorBackend,
    ExchangeInspectorConfigError,
    ExchangeInspectorRuntimeConfig,
)
from inspectors.exchange_powershell_runner import (
    ExchangePowerShellExecutionError,
    ExchangePowerShellRunnerConfig,
    ExchangePowerShellSubprocessRunner,
    validate_exchange_powershell_runner_config,
)


def make_runtime_config(
    *,
    backend: ExchangeInspectorBackend = ExchangeInspectorBackend.EXCHANGE_ONLINE_POWERSHELL,
    allow_real_external_calls: bool = True,
) -> ExchangeInspectorRuntimeConfig:
    return ExchangeInspectorRuntimeConfig(
        backend=backend,
        allow_real_external_calls=allow_real_external_calls,
    )


def test_validate_exchange_powershell_runner_config_allows_explicit_real_backend():
    config = ExchangePowerShellRunnerConfig(
        runtime_config=make_runtime_config(),
    )

    validate_exchange_powershell_runner_config(config)


def test_exchange_powershell_runner_requires_exchange_backend():
    config = ExchangePowerShellRunnerConfig(
        runtime_config=make_runtime_config(
            backend=ExchangeInspectorBackend.MOCK,
            allow_real_external_calls=True,
        ),
    )

    with pytest.raises(
        ExchangeInspectorConfigError,
        match="requires exchange_online_powershell backend",
    ):
        ExchangePowerShellSubprocessRunner(config)


def test_exchange_powershell_runner_requires_real_external_calls_allowed():
    config = ExchangePowerShellRunnerConfig(
        runtime_config=make_runtime_config(
            allow_real_external_calls=False,
        ),
    )

    with pytest.raises(
        ExchangeInspectorConfigError,
        match="requires real external calls",
    ):
        ExchangePowerShellSubprocessRunner(config)


def test_exchange_powershell_runner_rejects_empty_executable():
    config = ExchangePowerShellRunnerConfig(
        runtime_config=make_runtime_config(),
        executable="   ",
    )

    with pytest.raises(
        ExchangeInspectorConfigError,
        match="executable cannot be empty",
    ):
        ExchangePowerShellSubprocessRunner(config)


def test_exchange_powershell_runner_rejects_non_positive_timeout():
    config = ExchangePowerShellRunnerConfig(
        runtime_config=make_runtime_config(),
        timeout_seconds=0,
    )

    with pytest.raises(
        ExchangeInspectorConfigError,
        match="timeout must be greater than zero",
    ):
        ExchangePowerShellSubprocessRunner(config)


def test_exchange_powershell_runner_validates_command_before_not_implemented_error():
    config = ExchangePowerShellRunnerConfig(
        runtime_config=make_runtime_config(),
    )
    runner = ExchangePowerShellSubprocessRunner(config)

    with pytest.raises(
        ExchangePowerShellExecutionError,
        match="not implemented yet",
    ):
        runner.run(
            ExchangePowerShellCommand(
                name="Get-EXOMailbox",
                parameters={"Identity": "user@example.com"},
            )
        )


def test_exchange_powershell_runner_rejects_forbidden_command_before_execution():
    config = ExchangePowerShellRunnerConfig(
        runtime_config=make_runtime_config(),
    )
    runner = ExchangePowerShellSubprocessRunner(config)

    with pytest.raises(
        ValueError,
        match="forbidden for inspectors",
    ):
        runner.run(
            ExchangePowerShellCommand(
                name="Set-Mailbox",
                parameters={"Identity": "user@example.com"},
            )
        )