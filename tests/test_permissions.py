import pytest

from permissions import (
    Decision,
    PermissionContext,
    PermissionMode,
    PermissionRuleSet,
    evaluate_request,
)


def make_context(mode=PermissionMode.DEFAULT, rules=None):
    return PermissionContext(
        mode=mode,
        workspace="/tmp/test_workspace",
        rules=rules or PermissionRuleSet(),
    )


@pytest.mark.parametrize(
    "mode, tool_name, args, expected",
    [
        # default
        (PermissionMode.DEFAULT, "get_file_content", {"file_path": "a.txt"}, Decision.ALLOW),
        (PermissionMode.DEFAULT, "write_file", {"file_path": "a.txt"}, Decision.ASK),
        (PermissionMode.DEFAULT, "run_python_file", {"file_path": "a.py"}, Decision.ASK),
        (PermissionMode.DEFAULT, "some_new_tool", {}, Decision.ASK),
        # plan
        (PermissionMode.PLAN, "get_file_content", {"file_path": "a.txt"}, Decision.ALLOW),
        (PermissionMode.PLAN, "write_file", {"file_path": "a.txt"}, Decision.DENY),
        (PermissionMode.PLAN, "run_python_file", {"file_path": "a.py"}, Decision.DENY),
        (PermissionMode.PLAN, "some_new_tool", {}, Decision.DENY),
        # accept_edits
        (PermissionMode.ACCEPT_EDITS, "get_file_content", {"file_path": "a.txt"}, Decision.ALLOW),
        (PermissionMode.ACCEPT_EDITS, "write_file", {"file_path": "a.txt"}, Decision.ALLOW),
        (PermissionMode.ACCEPT_EDITS, "run_python_file", {"file_path": "a.py"}, Decision.ASK),
        (PermissionMode.ACCEPT_EDITS, "some_new_tool", {}, Decision.ASK),
        # dont_ask
        (PermissionMode.DONT_ASK, "get_file_content", {"file_path": "a.txt"}, Decision.ALLOW),
        (PermissionMode.DONT_ASK, "write_file", {"file_path": "a.txt"}, Decision.DENY),
        (PermissionMode.DONT_ASK, "run_python_file", {"file_path": "a.py"}, Decision.DENY),
        (PermissionMode.DONT_ASK, "some_new_tool", {}, Decision.DENY),
    ],
)
def test_mode_baselines(mode, tool_name, args, expected):
    ctx = make_context(mode=mode)
    assert evaluate_request(ctx, tool_name, args) == expected


@pytest.mark.parametrize(
    "rules, tool_name, args, expected",
    [
        (
            PermissionRuleSet(deny=["run_python_file:denied.py"]),
            "run_python_file",
            {"file_path": "denied.py"},
            Decision.DENY,
        ),
        (
            PermissionRuleSet(ask=["write_file:ask_me.txt"]),
            "write_file",
            {"file_path": "ask_me.txt"},
            Decision.ASK,
        ),
        (
            PermissionRuleSet(ask=["dangerous_tool"]),
            "dangerous_tool",
            {},
            Decision.ASK,
        ),
        (
            PermissionRuleSet(allow=["get_file_content:allowed.txt"]),
            "get_file_content",
            {"file_path": "allowed.txt"},
            Decision.ALLOW,
        ),
    ],
)
def test_explicit_rules_override_mode_baseline(rules, tool_name, args, expected):
    ctx = make_context(mode=PermissionMode.DEFAULT, rules=rules)
    assert evaluate_request(ctx, tool_name, args) == expected


def test_session_allow_tool_overrides_mode_baseline():
    ctx = make_context(mode=PermissionMode.PLAN)
    ctx.session_allow_tools.add("write_file")

    assert evaluate_request(ctx, "write_file", {"file_path": "x.txt"}) == Decision.ALLOW


def test_session_allow_path_overrides_protected_path():
    ctx = make_context(mode=PermissionMode.DEFAULT)
    ctx.session_allow_paths.add(".env")

    assert evaluate_request(ctx, "get_file_content", {"file_path": ".env"}) == Decision.ALLOW


def test_explicit_ask_beats_session_allow_tool():
    ctx = make_context(rules=PermissionRuleSet(ask=["dangerous_tool"]))
    ctx.session_allow_tools.add("dangerous_tool")

    assert evaluate_request(ctx, "dangerous_tool", {}) == Decision.ASK


def test_explicit_ask_beats_session_allow_path():
    ctx = make_context(rules=PermissionRuleSet(ask=["write_file:ask_me.txt"]))
    ctx.session_allow_paths.add("ask_me.txt")

    assert evaluate_request(ctx, "write_file", {"file_path": "ask_me.txt"}) == Decision.ASK


def test_explicit_deny_beats_session_allow():
    ctx = make_context(rules=PermissionRuleSet(deny=["run_python_file:denied.py"]))
    ctx.session_allow_tools.add("run_python_file")
    ctx.session_allow_paths.add("denied.py")

    assert evaluate_request(ctx, "run_python_file", {"file_path": "denied.py"}) == Decision.DENY


@pytest.mark.parametrize(
    "mode, tool_name, args",
    [
        (PermissionMode.DEFAULT, "write_file", {"file_path": ".env"}),
        (PermissionMode.PLAN, "write_file", {"file_path": ".venv/script.py"}),
        (PermissionMode.PLAN, "write_file", {"file_path": ".git/config"}),
        (PermissionMode.DONT_ASK, "write_file", {"file_path": ".env"}),
    ],
)
def test_write_protected_paths_deny(mode, tool_name, args):
    ctx = make_context(mode=mode)
    assert evaluate_request(ctx, tool_name, args) == Decision.DENY


@pytest.mark.parametrize(
    "mode, tool_name, args",
    [
        (PermissionMode.DEFAULT, "update", {"file_path": ".env"}),
        (PermissionMode.PLAN, "update", {"file_path": ".venv/script.py"}),
        
        (PermissionMode.DONT_ASK, "update", {"file_path": ".env"}),(PermissionMode.PLAN, "update", {"file_path": ".work_copilot.json"}),
    ],
)
def test_update_protected_paths_deny(mode, tool_name, args):
    ctx = make_context(mode=mode)
    assert evaluate_request(ctx, tool_name, args) == Decision.DENY

@pytest.mark.parametrize(
    "mode, tool_name, args",
    [
        (PermissionMode.DEFAULT, "run_python_file", {"file_path": "__pycache__/x.pyc"}),
        (PermissionMode.DONT_ASK, "run_python_file", {"file_path": ".venv/script.py"}),
    ]
)
def test_run_py_protected_paths_deny(mode, tool_name, args):
    ctx = make_context(mode=mode)
    assert evaluate_request(ctx, tool_name, args) == Decision.DENY