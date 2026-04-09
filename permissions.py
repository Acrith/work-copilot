from __future__ import annotations

import fnmatch
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PermissionMode(str, Enum):
    DEFAULT = "default"
    ACCEPT_EDITS = "accept_edits"
    PLAN = "plan"
    DONT_ASK = "dont_ask"


class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


READ_TOOLS = {
    "get_files_info",
    "get_file_content",
    "search_in_files",
}

WRITE_TOOLS = {
    "write_file",
}

EXEC_TOOLS = {
    "run_python_file",
}

PROTECTED_PATHS = {
    ".git",
    ".env",
    ".venv",
    "__pycache__",
    ".work_copilot.json",
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


def tool_category(tool_name: str) -> str:
    if tool_name in READ_TOOLS:
        return "read"
    if tool_name in WRITE_TOOLS:
        return "write"
    if tool_name in EXEC_TOOLS:
        return "exec"
    return "unknown"


def extract_target_path(tool_name: str, args: dict[str, Any]) -> str | None:
    if tool_name in {"get_file_content", "write_file", "run_python_file"}:
        return args.get("file_path")
    if tool_name == "get_files_info":
        return args.get("directory", ".")
    return None


def is_protected_path(path: str | None) -> bool:
    if not path:
        return False
    normalized = path.replace("\\", "/").lstrip("./")
    parts = normalized.split("/")
    return any(part in PROTECTED_PATHS for part in parts if part)


def matches_any(value: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(value, pattern) for pattern in patterns)


def evaluate_request(ctx: PermissionContext, tool_name: str, args: dict[str, Any]) -> Decision:
    target_path = extract_target_path(tool_name, args)
    tool_key = tool_name if target_path is None else f"{tool_name}:{target_path}"

    # Explicit deny > ask > allow
    if matches_any(tool_name, ctx.rules.deny) or matches_any(tool_key, ctx.rules.deny):
        return Decision.DENY

    if matches_any(tool_name, ctx.rules.ask) or matches_any(tool_key, ctx.rules.ask):
        return Decision.ASK

    if matches_any(tool_name, ctx.rules.allow) or matches_any(tool_key, ctx.rules.allow):
        return Decision.ALLOW

    # Session-level approvals
    if tool_name in ctx.session_allow_tools:
        return Decision.ALLOW
    if target_path and target_path in ctx.session_allow_paths:
        return Decision.ALLOW

    # Protected paths should always ask or deny
    if is_protected_path(target_path):
        return Decision.ASK

    # Mode baseline
    category = tool_category(tool_name)

    if ctx.mode == PermissionMode.PLAN:
        return Decision.ALLOW if category == "read" else Decision.DENY

    if ctx.mode == PermissionMode.DEFAULT:
        return Decision.ALLOW if category == "read" else Decision.ASK

    if ctx.mode == PermissionMode.ACCEPT_EDITS:
        if category in {"read", "write"}:
            return Decision.ALLOW
        return Decision.ASK

    if ctx.mode == PermissionMode.DONT_ASK:
        return Decision.ALLOW if category == "read" else Decision.DENY

    return Decision.ASK