from approval import ApprovalAction, parse_approval_action


def test_parse_approval_action_accepts_valid_choices():
    assert parse_approval_action("y") == ApprovalAction.ALLOW_ONCE
    assert parse_approval_action("n") == ApprovalAction.DENY
    assert parse_approval_action("f") == ApprovalAction.DENY_WITH_FEEDBACK
    assert parse_approval_action("s") == ApprovalAction.ALLOW_TOOL_SESSION
    assert parse_approval_action("p") == ApprovalAction.ALLOW_PATH_SESSION


def test_parse_approval_action_normalizes_input():
    assert parse_approval_action(" Y ") == ApprovalAction.ALLOW_ONCE


def test_parse_approval_action_rejects_invalid_choice():
    assert parse_approval_action("x") is None
