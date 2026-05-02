from inspectors.active_directory_user import (
    ActiveDirectoryUserInspectionError,
    ActiveDirectoryUserNotFoundError,
    ActiveDirectoryUserSnapshot,
    MockActiveDirectoryUserInspectorClient,
    inspect_active_directory_user,
)
from inspectors.models import InspectorRequest, InspectorStatus, InspectorTarget


def make_request(
    *,
    user_principal_name: str | None = "user@example.com",
    target_id: str = "user@example.com",
) -> InspectorRequest:
    inputs: dict[str, object] = {}

    if user_principal_name is not None:
        inputs["user_principal_name"] = user_principal_name

    return InspectorRequest(
        inspector="active_directory.user.inspect",
        request_id="55948",
        target=InspectorTarget(
            type="active_directory_user",
            id=target_id,
            metadata={"source": "test"},
        ),
        inputs=inputs,
    )


def test_inspect_active_directory_user_returns_read_only_facts():
    client = MockActiveDirectoryUserInspectorClient(
        {
            "user@example.com": ActiveDirectoryUserSnapshot(
                user_identifier="user@example.com",
                display_name="Example User",
                user_principal_name="user@example.com",
                sam_account_name="example.user",
                mail="user@example.com",
                enabled=True,
                distinguished_name="CN=Example User,OU=Users,DC=example,DC=com",
                department="Engineering",
                title="Engineer",
                manager="CN=Manager,OU=Users,DC=example,DC=com",
            )
        }
    )

    result = inspect_active_directory_user(make_request(), client)

    assert result.status == InspectorStatus.OK
    assert result.summary == "AD user metadata inspected for user@example.com."

    facts = {fact.key: fact.value for fact in result.facts}

    assert facts["user_exists"] is True
    assert facts["display_name"] == "Example User"
    assert facts["user_principal_name"] == "user@example.com"
    assert facts["sam_account_name"] == "example.user"
    assert facts["mail"] == "user@example.com"
    assert facts["enabled"] is True
    assert facts["distinguished_name"].startswith("CN=Example User")
    assert facts["department"] == "Engineering"
    assert facts["title"] == "Engineer"
    assert facts["manager"].startswith("CN=Manager")

    assert "Account passwords not inspected" in result.limitations
    assert "No AD writes performed" in result.limitations


def test_inspect_active_directory_user_returns_error_when_user_missing():
    client = MockActiveDirectoryUserInspectorClient({})

    result = inspect_active_directory_user(make_request(), client)

    assert result.status == InspectorStatus.ERROR
    assert result.errors[0].code == "active_directory_user_not_found"
    facts = {fact.key: fact.value for fact in result.facts}
    assert facts["user_exists"] is False


def test_inspect_active_directory_user_uses_target_id_when_input_missing():
    client = MockActiveDirectoryUserInspectorClient(
        {
            "target@example.com": ActiveDirectoryUserSnapshot(
                user_identifier="target@example.com",
            )
        }
    )

    request = make_request(
        user_principal_name=None,
        target_id="target@example.com",
    )

    result = inspect_active_directory_user(request, client)

    assert result.status == InspectorStatus.OK
    assert result.target.id == "target@example.com"


def test_inspect_active_directory_user_returns_error_when_target_is_empty():
    client = MockActiveDirectoryUserInspectorClient({})

    request = make_request(user_principal_name=None, target_id="")
    result = inspect_active_directory_user(request, client)

    assert result.status == InspectorStatus.ERROR
    assert result.errors[0].code == "missing_user_identifier"


def test_inspect_active_directory_user_returns_structured_client_error():
    class FailingClient:
        def get_user_snapshot(
            self, user_identifier: str
        ) -> ActiveDirectoryUserSnapshot:
            raise ActiveDirectoryUserInspectionError(
                "Active Directory metadata lookup failed."
            )

    result = inspect_active_directory_user(make_request(), FailingClient())

    assert result.status == InspectorStatus.ERROR
    assert result.errors[0].code == "active_directory_user_inspection_failed"


def test_mock_client_raises_not_found_for_unknown_user():
    client = MockActiveDirectoryUserInspectorClient({})

    try:
        client.get_user_snapshot("missing@example.com")
    except ActiveDirectoryUserNotFoundError as exc:
        assert str(exc) == "AD user not found: missing@example.com"
    else:
        raise AssertionError("Expected ActiveDirectoryUserNotFoundError")
