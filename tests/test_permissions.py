import pytest

import permissions as permissions_module
from permissions import (
    Decision,
    PermissionContext,
    PermissionMode,
    PermissionRuleSet,
    evaluate_request,
    extract_target_path,
    is_protected_path,
    is_sensitive_read_path,
    normalize_relative_path,
)
from tool_categories import ToolCategory


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
        (PermissionMode.DEFAULT, "some_new_tool", {}, Decision.DENY),
        # plan
        (PermissionMode.PLAN, "get_file_content", {"file_path": "a.txt"}, Decision.ALLOW),
        (PermissionMode.PLAN, "write_file", {"file_path": "a.txt"}, Decision.DENY),
        (PermissionMode.PLAN, "run_python_file", {"file_path": "a.py"}, Decision.DENY),
        (PermissionMode.PLAN, "some_new_tool", {}, Decision.DENY),
        # accept_edits
        (PermissionMode.ACCEPT_EDITS, "get_file_content", {"file_path": "a.txt"}, Decision.ALLOW),
        (PermissionMode.ACCEPT_EDITS, "write_file", {"file_path": "a.txt"}, Decision.ALLOW),
        (PermissionMode.ACCEPT_EDITS, "run_python_file", {"file_path": "a.py"}, Decision.ASK),
        (PermissionMode.ACCEPT_EDITS, "some_new_tool", {}, Decision.DENY),
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
            PermissionRuleSet(ask=["bash"]),
            "bash",
            {"command": "echo hello"},
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


def test_session_allow_path_overrides_default_ask_for_write_tool():
    ctx = make_context(mode=PermissionMode.DEFAULT)
    ctx.session_allow_paths.add("notes.txt")

    assert evaluate_request(ctx, "write_file", {"file_path": "notes.txt"}) == Decision.ALLOW


def test_session_allow_path_does_not_override_sensitive_read_path():
    ctx = make_context(mode=PermissionMode.DEFAULT)
    ctx.session_allow_paths.add(".env")

    assert evaluate_request(ctx, "get_file_content", {"file_path": ".env"}) == Decision.DENY


def test_tool_allow_path_does_not_override_sensitive_read_path():
    ctx = make_context(mode=PermissionMode.DEFAULT)
    ctx.session_allow_tools.add("get_file_content")

    assert evaluate_request(ctx, "get_file_content", {"file_path": ".env"}) == Decision.DENY


def test_explicit_ask_beats_session_allow_tool():
    ctx = make_context(rules=PermissionRuleSet(ask=["bash"]))
    ctx.session_allow_tools.add("bash")

    assert evaluate_request(ctx, "bash", {"command": "echo hello"}) == Decision.ASK


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
        (PermissionMode.PLAN, "update", {"file_path": ".work_copilot.json"}),
        (PermissionMode.DONT_ASK, "update", {"file_path": ".env"}),
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
    ],
)
def test_run_py_protected_paths_deny(mode, tool_name, args):
    ctx = make_context(mode=mode)
    assert evaluate_request(ctx, tool_name, args) == Decision.DENY


@pytest.mark.parametrize(
    "mode, tool_name, args",
    [
        (PermissionMode.DEFAULT, "get_file_content", {"file_path": ".env"}),
        (PermissionMode.PLAN, "get_file_content", {"file_path": ".env"}),
        (PermissionMode.DONT_ASK, "get_file_content", {"file_path": ".env"}),
    ],
)
def test_sensitive_read_paths_deny(mode, tool_name, args):
    ctx = make_context(mode=mode)
    assert evaluate_request(ctx, tool_name, args) == Decision.DENY


@pytest.mark.parametrize(
    "mode, tool_name, args",
    [
        (PermissionMode.DEFAULT, "get_file_content", {"file_path": ".work_copilot.json"}),
        (PermissionMode.PLAN, "get_file_content", {"file_path": ".git/config"}),
        (PermissionMode.DEFAULT, "get_files_info", {"directory": ".git"}),
    ],
)
def test_protected_but_readable_paths_allow(mode, tool_name, args):
    ctx = make_context(mode=mode)
    assert evaluate_request(ctx, tool_name, args) == Decision.ALLOW


@pytest.mark.parametrize(
    "tool_name, file_path",
    [
        ("write_file", ".env"),
        ("update", ".env"),
    ],
)
def test_explicit_allow_does_not_override_write_protected_paths(tool_name, file_path):
    # Even with an explicit allow rule, writing to protected paths should be denied.
    rules = PermissionRuleSet(allow=[f"{tool_name}:{file_path}"])
    ctx = make_context(
        mode=PermissionMode.DONT_ASK, rules=rules
    )  # DONT_ASK implies ALLOW for writes, but hard safety should override
    assert evaluate_request(ctx, tool_name, {"file_path": file_path}) == Decision.DENY


@pytest.mark.parametrize(
    "tool_name, file_path",
    [
        ("get_file_content", ".env"),
    ],
)
def test_explicit_allow_does_not_override_sensitive_read_paths(tool_name, file_path):
    # Even with an explicit allow rule, reading sensitive paths should be denied.
    rules = PermissionRuleSet(allow=[f"{tool_name}:{file_path}"])
    ctx = make_context(
        mode=PermissionMode.DONT_ASK, rules=rules
    )  # DONT_ASK implies ALLOW for reads, but hard safety should override
    assert evaluate_request(ctx, tool_name, {"file_path": file_path}) == Decision.DENY


@pytest.mark.parametrize(
    "tool_name, file_path",
    [
        ("run_python_file", ".venv/script.py"),
        ("run_python_file", "__pycache__/x.pyc"),
    ],
)
def test_explicit_allow_does_not_override_exec_protected_paths(tool_name, file_path):
    # Even with an explicit allow rule, executing in protected paths should be denied.
    rules = PermissionRuleSet(allow=[f"{tool_name}:{file_path}"])
    ctx = make_context(
        mode=PermissionMode.DONT_ASK, rules=rules
    )  # DONT_ASK implies ALLOW for exec, but hard safety should override
    assert evaluate_request(ctx, tool_name, {"file_path": file_path}) == Decision.DENY


@pytest.mark.parametrize(
    "tool_name, args, expected_path",
    [
        ("get_file_content", {"file_path": "some/file.txt"}, "some/file.txt"),
        ("write_file", {"file_path": "another/path.md"}, "another/path.md"),
        ("update", {"file_path": "./update_target.py"}, "update_target.py"),
        ("run_python_file", {"file_path": "script.py"}, "script.py"),
        ("git_diff_file", {"file_path": "diff_me.txt"}, "diff_me.txt"),
        ("get_files_info", {"directory": "my/dir"}, "my/dir"),
        ("get_files_info", {}, "."),  # Default directory is '.'
        ("run_tests", {"test_path": "tests/unit/test_foo.py"}, "tests/unit/test_foo.py"),
        ("git_status", {}, None),  # Non-path tool
        ("search_in_files", {"query": "somethingf"}, None),  # query is not a path
        ("get_file_content", {"file_path": None}, None),
        ("write_file", {}, None),  # No file_path provided
        (
            "get_files_info",
            {"directory": None},
            None,
        ),  # Normalize returns None if path is None, extract returns None if normalize returns None.
        ("run_tests", {}, None),
    ],
)
def test_extract_target_path(tool_name, args, expected_path):
    assert extract_target_path(tool_name, args) == expected_path


@pytest.mark.parametrize(
    "path, expected",
    [
        (".git/config", True),
        ("foo/.git/config", True),
        (".venv/script.py", True),
        ("bar/.venv/script.py", True),
        ("__pycache__/x.pyc", True),
        ("baz/__pycache__/x.pyc", True),
        (".work_copilot.json", True),
        ("qux/.work_copilot.json", True),
        (".env", True),
        ("quux/.env", True),
        ("src/main.py", False),
        ("README.md", False),
        ("./.git/config", True),
        (r".\.venv\script.py", True),
        (r".\src\main.py", False),
    ],
)
def test_is_protected_path(path, expected):
    assert is_protected_path(path) == expected


@pytest.mark.parametrize(
    "path, expected",
    [
        (".env", True),
        ("foo/.env", True),
        (".work_copilot.json", False),
        ("bar/.work_copilot.json", False),
        ("src/main.py", False),
        ("README.md", False),
        ("./.env", True),
        (r".\.env", True),
        (r".\src\main.py", False),
    ],
)
def test_is_sensitive_read_path(path, expected):
    assert is_sensitive_read_path(path) == expected


@pytest.mark.parametrize(
    "path, expected",
    [
        ("file.txt", "file.txt"),
        ("./file.txt", "file.txt"),
        ("dir/subdir/file.txt", "dir/subdir/file.txt"),
        ("dir/../file.txt", "file.txt"),
        (r".\.venv\script.py", ".venv/script.py"),
        (r".\.env", ".env"),
        (r".\src\main.py", "src/main.py"),
        (None, None),
        ("", None),
    ],
)
def test_normalize_relative_path(path, expected):
    assert normalize_relative_path(path) == expected


@pytest.mark.parametrize(
    "mode, args, expected",
    [
        (PermissionMode.DEFAULT, {"command": "git status"}, Decision.ASK),
        (PermissionMode.PLAN, {"command": "git status"}, Decision.DENY),
        (PermissionMode.DONT_ASK, {"command": "git status"}, Decision.DENY),
        (PermissionMode.DEFAULT, {"command": "git status", "cwd": ".git"}, Decision.DENY),
    ],
)
def test_bash_permission_behavior(mode, args, expected):
    ctx = make_context(mode=mode)
    assert evaluate_request(ctx, "bash", args) == expected


def test_connector_read_allowed_in_default_mode(monkeypatch):
    monkeypatch.setattr(
        permissions_module,
        "get_tool_category",
        lambda name: ToolCategory.CONNECTOR_READ if name == "servicedesk_status" else None,
    )

    ctx = make_context(mode=PermissionMode.DEFAULT)

    decision = evaluate_request(
        ctx,
        "servicedesk_status",
        {},
    )

    assert decision == Decision.ALLOW


def test_connector_write_denied_even_if_session_allowed(monkeypatch):
    monkeypatch.setattr(
        permissions_module,
        "get_tool_category",
        lambda name: (
            ToolCategory.CONNECTOR_WRITE
            if name == "servicedesk_update_request"
            else None
        ),
    )

    ctx = make_context(mode=PermissionMode.DEFAULT)
    ctx.session_allow_tools.add("servicedesk_update_request")

    decision = evaluate_request(
        ctx,
        "servicedesk_update_request",
        {"request_id": "123"},
    )

    assert decision == Decision.DENY


def test_unknown_tool_is_denied():
    ctx = make_context(mode=PermissionMode.DEFAULT)

    decision = evaluate_request(
        ctx,
        "totally_fake_tool",
        {},
    )

    assert decision == Decision.DENY


def test_explicit_allow_does_not_allow_unknown_tool():
    ctx = make_context(
        mode=PermissionMode.DEFAULT,
        rules=PermissionRuleSet(allow=["totally_fake_tool"]),
    )

    assert evaluate_request(ctx, "totally_fake_tool", {}) == Decision.DENY