import pytest

from inspectors.active_directory_command_runner import (
    ActiveDirectoryCommandResult,
    MockActiveDirectoryCommandRunner,
)
from inspectors.active_directory_group import (
    ActiveDirectoryGroupInspectionError,
    ActiveDirectoryGroupNotFoundError,
)
from inspectors.active_directory_group_membership import (
    ActiveDirectoryGroupMembershipInspectionError,
)
from inspectors.active_directory_powershell import (
    ActiveDirectoryPowerShellGroupClient,
    ActiveDirectoryPowerShellGroupMembershipClient,
    ActiveDirectoryPowerShellUserClient,
)
from inspectors.active_directory_user import (
    ActiveDirectoryUserInspectionError,
    ActiveDirectoryUserNotFoundError,
)

# ----------------------------- User client -----------------------------


def test_user_client_maps_full_dict_result_to_snapshot():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=True,
                data={
                    "DisplayName": "Example User",
                    "GivenName": "Example",
                    "Surname": "User",
                    "UserPrincipalName": "user@example.com",
                    "SamAccountName": "example.user",
                    "Mail": "user@example.com",
                    "Enabled": True,
                    "DistinguishedName": "CN=Example User,OU=Users,DC=ex,DC=com",
                    "Department": "Engineering",
                    "Title": "Engineer",
                    "Office": "HQ",
                    "OfficePhone": "+1-555-0100",
                    "MobilePhone": "+1-555-0200",
                    "Manager": "CN=Manager,OU=Users,DC=ex,DC=com",
                },
            )
        }
    )
    client = ActiveDirectoryPowerShellUserClient(runner)

    snapshot = client.get_user_snapshot("user@example.com")

    assert snapshot.user_identifier == "user@example.com"
    assert snapshot.display_name == "Example User"
    assert snapshot.first_name == "Example"
    assert snapshot.last_name == "User"
    assert snapshot.user_principal_name == "user@example.com"
    assert snapshot.sam_account_name == "example.user"
    assert snapshot.mail == "user@example.com"
    assert snapshot.enabled is True
    assert snapshot.distinguished_name.startswith("CN=Example User")
    assert snapshot.department == "Engineering"
    assert snapshot.title == "Engineer"
    assert snapshot.office == "HQ"
    assert snapshot.office_phone == "+1-555-0100"
    assert snapshot.mobile_phone == "+1-555-0200"
    assert snapshot.manager.startswith("CN=Manager")

    assert [command.name for command in runner.commands] == ["Get-ADUser"]
    assert runner.commands[0].parameters == {"Identity": "user@example.com"}


def test_user_client_accepts_list_shaped_data_first_row():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=True,
                data=[
                    {
                        "DisplayName": "First Match",
                        "UserPrincipalName": "user@example.com",
                    }
                ],
            )
        }
    )
    client = ActiveDirectoryPowerShellUserClient(runner)

    snapshot = client.get_user_snapshot("user@example.com")

    assert snapshot.display_name == "First Match"


def test_user_client_raises_not_found_on_empty_list():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=True,
                data=[],
            )
        }
    )
    client = ActiveDirectoryPowerShellUserClient(runner)

    with pytest.raises(
        ActiveDirectoryUserNotFoundError,
        match="AD user not found: user@example.com",
    ):
        client.get_user_snapshot("user@example.com")


def test_user_client_raises_not_found_on_none_result():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=True,
                data=None,
            )
        }
    )
    client = ActiveDirectoryPowerShellUserClient(runner)

    with pytest.raises(
        ActiveDirectoryUserNotFoundError,
        match="AD user not found: user@example.com",
    ):
        client.get_user_snapshot("user@example.com")


def test_user_client_maps_runner_failure_to_inspection_error():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=False,
                error="Access denied for the given user.",
            )
        }
    )
    client = ActiveDirectoryPowerShellUserClient(runner)

    with pytest.raises(
        ActiveDirectoryUserInspectionError,
        match="Get-ADUser failed: Access denied",
    ):
        client.get_user_snapshot("user@example.com")


def test_user_client_maps_explicit_not_found_runner_error():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=False,
                error="Cannot find an object with identity: 'missing@example.com'",
            )
        }
    )
    client = ActiveDirectoryPowerShellUserClient(runner)

    with pytest.raises(
        ActiveDirectoryUserNotFoundError,
        match="AD user not found: missing@example.com",
    ):
        client.get_user_snapshot("missing@example.com")


def test_user_client_rejects_unsupported_data_shape():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=True,
                data="not a dict or list",  # type: ignore[arg-type]
            )
        }
    )
    client = ActiveDirectoryPowerShellUserClient(runner)

    with pytest.raises(
        ActiveDirectoryUserInspectionError,
        match="unsupported data shape",
    ):
        client.get_user_snapshot("user@example.com")


# ----------------------------- Group client ----------------------------


def test_group_client_maps_full_dict_result_to_snapshot():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADGroup": ActiveDirectoryCommandResult(
                command="Get-ADGroup",
                ok=True,
                data={
                    "Name": "Engineers",
                    "SamAccountName": "engineers",
                    "Mail": "engineers@example.com",
                    "GroupScope": "Global",
                    "GroupCategory": "Security",
                    "DistinguishedName": "CN=Engineers,OU=Groups,DC=ex,DC=com",
                    "MemberCount": 42,
                },
            )
        }
    )
    client = ActiveDirectoryPowerShellGroupClient(runner)

    snapshot = client.get_group_snapshot("Engineers")

    assert snapshot.group_identifier == "Engineers"
    assert snapshot.name == "Engineers"
    assert snapshot.sam_account_name == "engineers"
    assert snapshot.mail == "engineers@example.com"
    assert snapshot.group_scope == "Global"
    assert snapshot.group_category == "Security"
    assert snapshot.distinguished_name.startswith("CN=Engineers")
    assert snapshot.member_count == 42

    assert [command.name for command in runner.commands] == ["Get-ADGroup"]
    assert runner.commands[0].parameters == {"Identity": "Engineers"}


def test_group_client_raises_not_found_on_empty_list():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADGroup": ActiveDirectoryCommandResult(
                command="Get-ADGroup",
                ok=True,
                data=[],
            )
        }
    )
    client = ActiveDirectoryPowerShellGroupClient(runner)

    with pytest.raises(
        ActiveDirectoryGroupNotFoundError,
        match="AD group not found: Engineers",
    ):
        client.get_group_snapshot("Engineers")


def test_group_client_maps_runner_failure_to_inspection_error():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADGroup": ActiveDirectoryCommandResult(
                command="Get-ADGroup",
                ok=False,
                error="Access denied.",
            )
        }
    )
    client = ActiveDirectoryPowerShellGroupClient(runner)

    with pytest.raises(
        ActiveDirectoryGroupInspectionError,
        match="Get-ADGroup failed: Access denied.",
    ):
        client.get_group_snapshot("Engineers")


def test_group_client_maps_explicit_not_found_runner_error():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADGroup": ActiveDirectoryCommandResult(
                command="Get-ADGroup",
                ok=False,
                error="Cannot find an object with identity: 'NoSuchGroup'",
            )
        }
    )
    client = ActiveDirectoryPowerShellGroupClient(runner)

    with pytest.raises(
        ActiveDirectoryGroupNotFoundError,
        match="AD group not found: NoSuchGroup",
    ):
        client.get_group_snapshot("NoSuchGroup")


def test_group_client_rejects_unsupported_data_shape():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADGroup": ActiveDirectoryCommandResult(
                command="Get-ADGroup",
                ok=True,
                data="not a dict or list",  # type: ignore[arg-type]
            )
        }
    )
    client = ActiveDirectoryPowerShellGroupClient(runner)

    with pytest.raises(
        ActiveDirectoryGroupInspectionError,
        match="unsupported data shape",
    ):
        client.get_group_snapshot("Engineers")


# ----------------------- Group membership client -----------------------


def _membership_runner(
    rows: object,
    *,
    ok: bool = True,
    error: str | None = None,
) -> MockActiveDirectoryCommandRunner:
    return MockActiveDirectoryCommandRunner(
        results={
            "Get-ADPrincipalGroupMembership": ActiveDirectoryCommandResult(
                command="Get-ADPrincipalGroupMembership",
                ok=ok,
                data=rows if ok else None,
                error=error,
            )
        }
    )


def test_membership_client_returns_true_when_match_by_name():
    runner = _membership_runner(
        [
            {
                "Name": "Engineers",
                "SamAccountName": "engineers",
                "DistinguishedName": "CN=Engineers,OU=Groups,DC=ex,DC=com",
            }
        ]
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    snapshot = client.get_group_membership_snapshot(
        user_identifier="user@example.com",
        group_identifier="Engineers",
    )

    assert snapshot.is_member is True
    assert snapshot.user_identifier == "user@example.com"
    assert snapshot.group_identifier == "Engineers"
    assert snapshot.membership_source == "direct_or_nested_unknown"

    assert [command.name for command in runner.commands] == [
        "Get-ADPrincipalGroupMembership"
    ]
    assert runner.commands[0].parameters == {"Identity": "user@example.com"}


def test_membership_client_returns_true_when_match_by_sam_account_name():
    runner = _membership_runner(
        [
            {
                "Name": "Engineers",
                "SamAccountName": "engineers",
                "DistinguishedName": "CN=Engineers,OU=Groups,DC=ex,DC=com",
            }
        ]
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    snapshot = client.get_group_membership_snapshot(
        user_identifier="user@example.com",
        group_identifier="engineers",
    )

    assert snapshot.is_member is True


def test_membership_client_returns_true_when_match_by_distinguished_name():
    target_dn = "CN=Engineers,OU=Groups,DC=ex,DC=com"
    runner = _membership_runner(
        [
            {
                "Name": "Engineers",
                "SamAccountName": "engineers",
                "DistinguishedName": target_dn,
            }
        ]
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    snapshot = client.get_group_membership_snapshot(
        user_identifier="user@example.com",
        group_identifier=target_dn,
    )

    assert snapshot.is_member is True


def test_membership_client_returns_false_when_no_match():
    runner = _membership_runner(
        [
            {
                "Name": "Operations",
                "SamAccountName": "operations",
                "DistinguishedName": "CN=Operations,OU=Groups,DC=ex,DC=com",
            }
        ]
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    snapshot = client.get_group_membership_snapshot(
        user_identifier="user@example.com",
        group_identifier="Engineers",
    )

    assert snapshot.is_member is False
    assert snapshot.membership_source == "direct_or_nested_unknown"


def test_membership_client_treats_empty_list_as_not_member():
    runner = _membership_runner([])
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    snapshot = client.get_group_membership_snapshot(
        user_identifier="user@example.com",
        group_identifier="Engineers",
    )

    assert snapshot.is_member is False


def test_membership_client_treats_none_data_as_not_member():
    runner = _membership_runner(None)
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    snapshot = client.get_group_membership_snapshot(
        user_identifier="user@example.com",
        group_identifier="Engineers",
    )

    assert snapshot.is_member is False


def test_membership_client_raises_inspection_error_on_runner_failure():
    runner = _membership_runner(None, ok=False, error="Access denied.")
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    with pytest.raises(
        ActiveDirectoryGroupMembershipInspectionError,
        match="Get-ADPrincipalGroupMembership failed: Access denied.",
    ):
        client.get_group_membership_snapshot(
            user_identifier="user@example.com",
            group_identifier="Engineers",
        )


def test_membership_client_rejects_unsupported_data_shape():
    runner = _membership_runner("not a list")
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    with pytest.raises(
        ActiveDirectoryGroupMembershipInspectionError,
        match="unsupported data shape",
    ):
        client.get_group_membership_snapshot(
            user_identifier="user@example.com",
            group_identifier="Engineers",
        )


def test_membership_client_rejects_unsupported_list_items():
    runner = _membership_runner([{"Name": "Engineers"}, "string-instead-of-dict"])
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    with pytest.raises(
        ActiveDirectoryGroupMembershipInspectionError,
        match="unsupported list data",
    ):
        client.get_group_membership_snapshot(
            user_identifier="user@example.com",
            group_identifier="Engineers",
        )


# --------------------- Allowlisted command guarantee --------------------


def test_only_allowlisted_command_names_are_used_by_adapters():
    user_runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=True,
                data={"DisplayName": "Example"},
            )
        }
    )
    group_runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADGroup": ActiveDirectoryCommandResult(
                command="Get-ADGroup",
                ok=True,
                data={"Name": "Engineers"},
            )
        }
    )
    membership_runner = _membership_runner([])

    ActiveDirectoryPowerShellUserClient(user_runner).get_user_snapshot(
        "user@example.com"
    )
    ActiveDirectoryPowerShellGroupClient(group_runner).get_group_snapshot(
        "Engineers"
    )
    ActiveDirectoryPowerShellGroupMembershipClient(
        membership_runner
    ).get_group_membership_snapshot(
        user_identifier="user@example.com",
        group_identifier="Engineers",
    )

    issued = (
        [c.name for c in user_runner.commands]
        + [c.name for c in group_runner.commands]
        + [c.name for c in membership_runner.commands]
    )

    # Only the three allowlisted command names must ever appear here. In
    # particular, Get-ADGroupMember must not be used.
    assert set(issued) <= {
        "Get-ADUser",
        "Get-ADGroup",
        "Get-ADPrincipalGroupMembership",
    }
    assert "Get-ADGroupMember" not in issued
