from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class ApprovalAction(str, Enum):
    ALLOW_ONCE = "y"
    DENY = "n"
    DENY_WITH_FEEDBACK = "f"
    ALLOW_TOOL_SESSION = "s"
    ALLOW_PATH_SESSION = "p"


@dataclass(frozen=True)
class ApprovalResponse:
    action: ApprovalAction
    feedback: str | None = None


def parse_approval_action(value: str) -> ApprovalAction | None:
    normalized = value.strip().lower()

    try:
        return ApprovalAction(normalized)
    except ValueError:
        return None


@dataclass(frozen=True)
class ApprovalRequest:
    function_name: str
    args: dict[str, Any]
    preview_path: str | None = None
    preview: str | None = None


class ApprovalHandler(Protocol):
    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        """Ask the user whether a tool call should be approved."""
