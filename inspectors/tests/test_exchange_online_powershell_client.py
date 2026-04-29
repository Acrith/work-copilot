from inspectors.exchange_mailbox import ExchangeMailboxInspectionError
from inspectors.exchange_online_powershell import (
    ExchangeOnlinePowerShellConfig,
    ExchangeOnlinePowerShellMailboxClient,
)


def test_exchange_online_powershell_config_defaults_to_disabled():
    config = ExchangeOnlinePowerShellConfig()

    assert config.enabled is False


def test_exchange_online_powershell_client_is_disabled_placeholder():
    client = ExchangeOnlinePowerShellMailboxClient()

    try:
        client.get_mailbox_snapshot("user@example.com")
    except ExchangeMailboxInspectionError as exc:
        assert str(exc) == (
            "Exchange Online PowerShell mailbox inspector is not implemented yet."
        )
    else:
        raise AssertionError("Expected ExchangeMailboxInspectionError")


def test_exchange_online_powershell_client_accepts_config():
    config = ExchangeOnlinePowerShellConfig(enabled=True)
    client = ExchangeOnlinePowerShellMailboxClient(config)

    assert client.config is config