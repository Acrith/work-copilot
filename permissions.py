from __future__ import annotations

import fnmatch
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from constants import PROTECTED_PATHS, SENSITIVE_READ_PATHS
from tool_categories import ToolCategory


class PermissionMode(str, Enum):
    DEFAULT = "default"
    ACCEPT_EDITS = "accept_edits"
    PLAN = "plan"
    DONT_ASK = "dont_ask"


class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"

READ_CATEGORIES = {
    ToolCategory.READ,
    ToolCategory.CONNECTOR_READ,
}

LOCAL_WRITE_OR_EXEC_CATEGORIES = {
    ToolCategory.WRITE,
    ToolCategory.EXEC,
}

ACCEPT_EDITS_ALLOWED_CATEGORIES = {
    ToolCategory.READ,
    ToolCategory.WRITE,
    ToolCategory.CONNECTOR_READ,
}


@dataclass
class PermissionRuleSet:
    allow: list[str] = field(default_factory=list)
    ask: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)


@dataclass
class PermissionContext:
    mode: PermissionMode
    workspace: str
    rules: PermissionRuleSet
    session_allow_tools: set[str] = field(default_factory=set)
    session_allow_paths: set[str] = field(default_factory=set)


def load_rules(workspace: str) -> PermissionRuleSet:
    config_path = os.path.join(workspace, ".work_copilot.json")
    if not os.path.exists(config_path):
        return PermissionRuleSet()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return PermissionRuleSet()

    perms = data.get("permissions", {})
    return PermissionRuleSet(
        allow=perms.get("allow", []),
        ask=perms.get("ask", []),
        deny=perms.get("deny", []),
    )


def get_tool_category(tool_name: str) -> ToolCategory | None:
    from tool_registry import get_tool_definition

    try:
        return get_tool_definition(tool_name).category
    except KeyError:
        return None


def tool_category(tool_name: str) -> str:
    category = get_tool_category(tool_name)
    return category.value if category else "unknown"


def normalize_relative_path(path: str | None) -> str | None:
    if not path:
        return None

    normalized = os.path.normpath(path).replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]

    return normalized


def extract_target_path(tool_name: str, args: dict[str, Any]) -> str | None:
    if tool_name in {"get_file_content", "write_file", "update", "run_python_file"}:
        return normalize_relative_path(args.get("file_path"))
    if tool_name == "get_files_info":
        return normalize_relative_path(args.get("directory", "."))
    if tool_name == "git_diff_file":
        return normalize_relative_path(args.get("file_path"))
    if tool_name == "run_tests":
        return normalize_relative_path(args.get("test_path"))
    if tool_name == "bash":
        return normalize_relative_path(args.get("cwd", "."))
    return None


def is_protected_path(path: str | None) -> bool:
    normalized = normalize_relative_path(path)
    if not normalized:
        return False

    parts = normalized.split("/")
    return any(part in PROTECTED_PATHS for part in parts if part)


def is_sensitive_read_path(path: str | None) -> bool:
    normalized = normalize_relative_path(path)
    if not normalized:
        return False

    parts = normalized.split("/")
    return any(part in SENSITIVE_READ_PATHS for part in parts if part)


def matches_any(value: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(value, pattern) for pattern in patterns)


def evaluate_request(ctx: PermissionContext, tool_name: str, args: dict[str, Any]) -> Decision:
    target_path = extract_target_path(tool_name, args)
    tool_key = tool_name if target_path is None else f"{tool_name}:{target_path}"
    category = get_tool_category(tool_name)

    # Unknown tools should never be silently allowed.
    if category is None:
        return Decision.DENY

    # Hard safety rules should override everything, including explicit rules and session approvals.
    if category == ToolCategory.READ and is_sensitive_read_path(target_path):
        return Decision.DENY

    if category in LOCAL_WRITE_OR_EXEC_CATEGORIES and is_protected_path(target_path):
        return Decision.DENY

    # Explicit workspace deny/ask rules.
    if matches_any(tool_name, ctx.rules.deny) or matches_any(tool_key, ctx.rules.deny):
        return Decision.DENY

    if matches_any(tool_name, ctx.rules.ask) or matches_any(tool_key, ctx.rules.ask):
        return Decision.ASK

    # Connector writes must require fresh approval.
    # Explicit/session allow rules should not bypass this.
    if category == ToolCategory.CONNECTOR_WRITE:
        if ctx.mode in {PermissionMode.PLAN, PermissionMode.DONT_ASK}:
            return Decision.DENY

        return Decision.ASK

    # Explicit workspace allow rules.
    if matches_any(tool_name, ctx.rules.allow) or matches_any(tool_key, ctx.rules.allow):
        return Decision.ALLOW

    # Session-level approvals.
    if tool_name in ctx.session_allow_tools:
        return Decision.ALLOW

    if target_path and target_path in ctx.session_allow_paths:
        return Decision.ALLOW

    # Mode baseline.
    if ctx.mode == PermissionMode.PLAN:
        return Decision.ALLOW if category in READ_CATEGORIES else Decision.DENY

    if ctx.mode == PermissionMode.DEFAULT:
        return Decision.ALLOW if category in READ_CATEGORIES else Decision.ASK

    if ctx.mode == PermissionMode.ACCEPT_EDITS:
        return Decision.ALLOW if category in ACCEPT_EDITS_ALLOWED_CATEGORIES else Decision.ASK

    if ctx.mode == PermissionMode.DONT_ASK:
        return Decision.ALLOW if category in READ_CATEGORIES else Decision.DENY

    return Decision.ASK
