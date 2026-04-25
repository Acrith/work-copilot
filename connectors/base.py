from dataclasses import dataclass
from enum import Enum


class ConnectorMode(str, Enum):
    DISABLED = "disabled"
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"


@dataclass(frozen=True)
class ConnectorConfig:
    name: str
    mode: ConnectorMode