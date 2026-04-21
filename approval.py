from dataclasses import dataclass
from enum import Enum


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
