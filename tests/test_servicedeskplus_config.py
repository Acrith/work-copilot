from connectors.servicedeskplus.config import load_servicedeskplus_config


def test_servicedeskplus_config_defaults_to_disabled(monkeypatch):
    monkeypatch.delenv("WORK_COPILOT_ENABLE_SERVICEDESKPLUS", raising=False)
    monkeypatch.delenv("SDP_DEPLOYMENT", raising=False)
    monkeypatch.delenv("SDP_BASE_URL", raising=False)
    monkeypatch.delenv("SDP_PORTAL", raising=False)
    monkeypatch.delenv("SDP_AUTHTOKEN", raising=False)
    monkeypatch.delenv("SDP_OAUTH_ACCESS_TOKEN", raising=False)

    config = load_servicedeskplus_config()

    assert config.enabled is False
    assert config.deployment == "onprem"
    assert config.base_url is None
    assert config.portal is None
    assert config.authtoken is None
    assert config.oauth_access_token is None


def test_servicedeskplus_config_loads_environment(monkeypatch):
    monkeypatch.setenv("WORK_COPILOT_ENABLE_SERVICEDESKPLUS", "true")
    monkeypatch.setenv("SDP_DEPLOYMENT", "cloud")
    monkeypatch.setenv("SDP_BASE_URL", "https://example.manageengine.com")
    monkeypatch.setenv("SDP_PORTAL", "example-portal")
    monkeypatch.setenv("SDP_AUTHTOKEN", "secret-token")
    monkeypatch.setenv("SDP_OAUTH_ACCESS_TOKEN", "oauth-token")

    config = load_servicedeskplus_config()

    assert config.enabled is True
    assert config.deployment == "cloud"
    assert config.base_url == "https://example.manageengine.com"
    assert config.portal == "example-portal"
    assert config.authtoken == "secret-token"
    assert config.oauth_access_token == "oauth-token"