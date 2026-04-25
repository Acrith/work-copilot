from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceDeskPlusConfig:
    enabled: bool
    deployment: str
    base_url: str | None
    portal: str | None
    authtoken: str | None
    oauth_access_token: str | None


def load_servicedeskplus_config() -> ServiceDeskPlusConfig:
    return ServiceDeskPlusConfig(
        enabled=os.getenv("WORK_COPILOT_ENABLE_SERVICEDESKPLUS") == "true",
        deployment=os.getenv("SDP_DEPLOYMENT", "onprem"),
        base_url=os.getenv("SDP_BASE_URL"),
        portal=os.getenv("SDP_PORTAL"),
        authtoken=os.getenv("SDP_AUTHTOKEN"),
        oauth_access_token=os.getenv("SDP_OAUTH_ACCESS_TOKEN"),
    )