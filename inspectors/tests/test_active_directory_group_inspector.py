from inspectors.active_directory_group import (
    ActiveDirectoryGroupNotFoundError,
    ActiveDirectoryGroupSnapshot,
    MockActiveDirectoryGroupInspectorClient,
    inspect_active_directory_group,
)
from inspectors.models import InspectorRequest, InspectorStatus, InspectorTarget


def make_request(
    *,
    group_name: str | None = "Engineers",
    target_id: str = "Engineers",
) -> InspectorRequest:
    inputs: dict[str, object] = {}

    if group_name is not None:
        inputs["group_name"] = group_name

    return InspectorRequest(
        inspector="active_directory.group.inspect",
        request_id="55948",
        target=InspectorTarget(
            type="active_directory_group",
            id=target_id,
            metadata={"source": "test"},
        ),
        inputs=inputs,
    )


def test_inspect_active_directory_group_returns_read_only_facts():
    client = MockActiveDirectoryGroupInspectorClient(
        {
            "Engineers": ActiveDirectoryGroupSnapshot(
                group_identifier="Engineers",
                name="Engineers",
                sam_account_name="engineers",
                mail="engineers@example.com",
                group_scope="Global",
                group_category="Security",
                distinguished_name="CN=Engineers,OU=Groups,DC=example,DC=com",
                member_count=42,
            )
        }
    )

    result = inspect_active_directory_group(make_request(), client)

    assert result.status == InspectorStatus.OK
    assert result.summary == "AD group metadata inspected for Engineers."

    facts = {fact.key: fact.value for fact in result.facts}

    assert facts["group_exists"] is True
    assert facts["name"] == "Engineers"
    assert facts["sam_account_name"] == "engineers"
    assert facts["mail"] == "engineers@example.com"
    assert facts["group_scope"] == "Global"
    assert facts["group_category"] == "Security"
    assert facts["distinguished_name"].startswith("CN=Engineers")
    assert facts["member_count"] == 42

    assert "No AD writes performed" in result.limitations


def test_inspect_active_directory_group_returns_error_when_missing():
    client = MockActiveDirectoryGroupInspectorClient({})

    result = inspect_active_directory_group(make_request(), client)

    assert result.status == InspectorStatus.ERROR
    assert result.errors[0].code == "active_directory_group_not_found"
    facts = {fact.key: fact.value for fact in result.facts}
    assert facts["group_exists"] is False


def test_inspect_active_directory_group_returns_error_when_target_is_empty():
    client = MockActiveDirectoryGroupInspectorClient({})

    request = make_request(group_name=None, target_id="")
    result = inspect_active_directory_group(request, client)

    assert result.status == InspectorStatus.ERROR
    assert result.errors[0].code == "missing_group_identifier"


def test_mock_client_raises_not_found_for_unknown_group():
    client = MockActiveDirectoryGroupInspectorClient({})

    try:
        client.get_group_snapshot("missing")
    except ActiveDirectoryGroupNotFoundError as exc:
        assert str(exc) == "AD group not found: missing"
    else:
        raise AssertionError("Expected ActiveDirectoryGroupNotFoundError")
