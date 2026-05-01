import os
from dataclasses import dataclass
from enum import StrEnum


class ExchangePowerShellAuthMode(StrEnum):
    DISABLED = "disabled"
    APP_CERTIFICATE_THUMBPRINT = "app_certificate_thumbprint"
    APP_CERTIFICATE_FILE = "app_certificate_file"


class ExchangePowerShellAuthConfigError(ValueError):
    """Raised when Exchange PowerShell auth configuration is unsafe or invalid."""


@dataclass(frozen=True)
class ExchangePowerShellAuthConfig:
    mode: ExchangePowerShellAuthMode = ExchangePowerShellAuthMode.DISABLED
    app_id: str | None = None
    organization: str | None = None
    certificate_thumbprint: str | None = None
    certificate_path: str | None = None
    certificate_password_env_var: str | None = None

    @property
    def is_enabled(self) -> bool:
        return self.mode != ExchangePowerShellAuthMode.DISABLED

    @property
    def uses_certificate_thumbprint(self) -> bool:
        return self.mode == ExchangePowerShellAuthMode.APP_CERTIFICATE_THUMBPRINT

    @property
    def uses_certificate_file(self) -> bool:
        return self.mode == ExchangePowerShellAuthMode.APP_CERTIFICATE_FILE


def load_exchange_powershell_auth_config(
    environ: dict[str, str] | None = None,
) -> ExchangePowerShellAuthConfig:
    if environ is None:
        environ = dict(os.environ)

    config = ExchangePowerShellAuthConfig(
        mode=_parse_auth_mode(
            environ.get("WORK_COPILOT_EXCHANGE_AUTH_MODE", "disabled")
        ),
        app_id=_empty_to_none(environ.get("WORK_COPILOT_EXCHANGE_APP_ID")),
        organization=_empty_to_none(environ.get("WORK_COPILOT_EXCHANGE_ORGANIZATION")),
        certificate_thumbprint=_empty_to_none(
            environ.get("WORK_COPILOT_EXCHANGE_CERTIFICATE_THUMBPRINT")
        ),
        certificate_path=_empty_to_none(
            environ.get("WORK_COPILOT_EXCHANGE_CERTIFICATE_PATH")
        ),
        certificate_password_env_var=_empty_to_none(
            environ.get("WORK_COPILOT_EXCHANGE_CERTIFICATE_PASSWORD_ENV_VAR")
        ),
    )
    validate_exchange_powershell_auth_config(config)

    return config


def validate_exchange_powershell_auth_config(
    config: ExchangePowerShellAuthConfig,
) -> None:
    if config.mode == ExchangePowerShellAuthMode.DISABLED:
        return

    _require_value(config.app_id, "WORK_COPILOT_EXCHANGE_APP_ID")
    _require_value(config.organization, "WORK_COPILOT_EXCHANGE_ORGANIZATION")

    if config.mode == ExchangePowerShellAuthMode.APP_CERTIFICATE_THUMBPRINT:
        _require_value(
            config.certificate_thumbprint,
            "WORK_COPILOT_EXCHANGE_CERTIFICATE_THUMBPRINT",
        )

        if config.certificate_path:
            raise ExchangePowerShellAuthConfigError(
                "Do not set WORK_COPILOT_EXCHANGE_CERTIFICATE_PATH when using "
                "app_certificate_thumbprint auth."
            )

        if config.certificate_password_env_var:
            raise ExchangePowerShellAuthConfigError(
                "Do not set WORK_COPILOT_EXCHANGE_CERTIFICATE_PASSWORD_ENV_VAR when using "
                "app_certificate_thumbprint auth."
            )

        return

    if config.mode == ExchangePowerShellAuthMode.APP_CERTIFICATE_FILE:
        _require_value(
            config.certificate_path,
            "WORK_COPILOT_EXCHANGE_CERTIFICATE_PATH",
        )
        _require_value(
            config.certificate_password_env_var,
            "WORK_COPILOT_EXCHANGE_CERTIFICATE_PASSWORD_ENV_VAR",
        )

        if config.certificate_thumbprint:
            raise ExchangePowerShellAuthConfigError(
                "Do not set WORK_COPILOT_EXCHANGE_CERTIFICATE_THUMBPRINT when using "
                "app_certificate_file auth."
            )

        return

    raise ExchangePowerShellAuthConfigError(
        f"Unsupported Exchange PowerShell auth mode: {config.mode}"
    )


def redacted_exchange_powershell_auth_config(
    config: ExchangePowerShellAuthConfig,
) -> dict[str, object]:
    return {
        "mode": config.mode.value,
        "app_id_configured": bool(config.app_id),
        "organization_configured": bool(config.organization),
        "certificate_thumbprint_configured": bool(config.certificate_thumbprint),
        "certificate_path_configured": bool(config.certificate_path),
        "certificate_password_env_var_configured": bool(
            config.certificate_password_env_var
        ),
    }


def _parse_auth_mode(value: str) -> ExchangePowerShellAuthMode:
    normalized = value.strip().lower()

    try:
        return ExchangePowerShellAuthMode(normalized)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in ExchangePowerShellAuthMode)
        raise ExchangePowerShellAuthConfigError(
            f"Unsupported Exchange PowerShell auth mode: {value}. "
            f"Allowed values: {allowed}."
        ) from exc


def _empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()

    return stripped or None


def _require_value(value: str | None, setting_name: str) -> None:
    if not value:
        raise ExchangePowerShellAuthConfigError(f"{setting_name} is required.")