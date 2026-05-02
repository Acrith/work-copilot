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
    # Email-shaped identifier flows through LDAPFilter; non-email path is
    # covered by `test_user_client_non_email_identifier_uses_identity`.
    assert runner.commands[0].parameters == {
        "LDAPFilter": (
            "(|(userPrincipalName=user@example.com)(mail=user@example.com))"
        )
    }


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
                error="Access is denied for the given user.",
            )
        }
    )
    client = ActiveDirectoryPowerShellUserClient(runner)

    with pytest.raises(
        ActiveDirectoryUserInspectionError,
        match="Active Directory inspection failed: access denied.",
    ):
        client.get_user_snapshot("user@example.com")


def test_user_client_maps_generic_runner_failure_to_sanitized_inspection_error():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=False,
                error=(
                    "At line:42 char:9\n"
                    "+         $raw = Get-ADUser @params -Properties $adUserProperties\n"
                    "    + CategoryInfo          : SomeError\n"
                    "    + FullyQualifiedErrorId : SomeId,Get-ADUser\n"
                ),
            )
        }
    )
    client = ActiveDirectoryPowerShellUserClient(runner)

    with pytest.raises(ActiveDirectoryUserInspectionError) as exc_info:
        client.get_user_snapshot("name.surname")

    message = str(exc_info.value)

    assert "failed during Active Directory inspection." in message

    for forbidden in (
        "At line:",
        "CategoryInfo",
        "FullyQualifiedErrorId",
        "Get-ADUser @params",
        "$adUserProperties",
    ):
        assert forbidden not in message, (
            f"Sanitized error must not echo raw PowerShell diagnostic: {forbidden}"
        )


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
                error="Access is denied.",
            )
        }
    )
    client = ActiveDirectoryPowerShellGroupClient(runner)

    with pytest.raises(
        ActiveDirectoryGroupInspectionError,
        match="Active Directory inspection failed: access denied.",
    ):
        client.get_group_snapshot("Engineers")


def test_group_client_maps_generic_runner_failure_to_sanitized_inspection_error():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADGroup": ActiveDirectoryCommandResult(
                command="Get-ADGroup",
                ok=False,
                error=(
                    "At line:1 char:1\n"
                    "+ Get-ADGroup @params\n"
                    "    + CategoryInfo          : SomeError\n"
                    "    + FullyQualifiedErrorId : SomeId,Get-ADGroup\n"
                ),
            )
        }
    )
    client = ActiveDirectoryPowerShellGroupClient(runner)

    with pytest.raises(ActiveDirectoryGroupInspectionError) as exc_info:
        client.get_group_snapshot("Engineers")

    message = str(exc_info.value)

    assert "failed during Active Directory inspection." in message

    for forbidden in (
        "At line:",
        "CategoryInfo",
        "FullyQualifiedErrorId",
        "Get-ADGroup @params",
    ):
        assert forbidden not in message


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
    resolved_user_dn: str | None = "CN=Resolved User,OU=Users,DC=ex,DC=com",
) -> MockActiveDirectoryCommandRunner:
    """Build a mock runner for membership-client tests.

    The membership client resolves email-shaped identifiers via Get-ADUser
    before issuing Get-ADPrincipalGroupMembership, so the helper also
    configures a stable Get-ADUser mock by default. Pass
    `resolved_user_dn=None` to omit it (e.g. when the test wants the
    user-resolution path itself to fail or when the identifier is not
    email-shaped).
    """
    results: dict[str, ActiveDirectoryCommandResult] = {
        "Get-ADPrincipalGroupMembership": ActiveDirectoryCommandResult(
            command="Get-ADPrincipalGroupMembership",
            ok=ok,
            data=rows if ok else None,
            error=error,
        )
    }

    if resolved_user_dn is not None:
        results["Get-ADUser"] = ActiveDirectoryCommandResult(
            command="Get-ADUser",
            ok=True,
            data={
                "DistinguishedName": resolved_user_dn,
                "SamAccountName": "resolved.user",
                "UserPrincipalName": "resolved.user@example.com",
            },
        )

    return MockActiveDirectoryCommandRunner(results=results)


def test_membership_client_returns_true_when_match_by_name():
    runner = _membership_runner(
        [
            {
                "Name": "Engineers",
                "SamAccountName": "engineers",
                "DistinguishedName": "CN=Engineers,OU=Groups,DC=ex,DC=com",
            }
        ],
        resolved_user_dn=None,
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    snapshot = client.get_group_membership_snapshot(
        user_identifier="name.surname",
        group_identifier="Engineers",
    )

    assert snapshot.is_member is True
    assert snapshot.user_identifier == "name.surname"
    assert snapshot.group_identifier == "Engineers"
    assert snapshot.membership_source == "direct_or_nested_unknown"

    # Non-email identifier: no resolver call, single membership call.
    assert [command.name for command in runner.commands] == [
        "Get-ADPrincipalGroupMembership"
    ]
    assert runner.commands[0].parameters == {"Identity": "name.surname"}


def test_membership_client_returns_true_when_match_by_sam_account_name():
    runner = _membership_runner(
        [
            {
                "Name": "Engineers",
                "SamAccountName": "engineers",
                "DistinguishedName": "CN=Engineers,OU=Groups,DC=ex,DC=com",
            }
        ],
        resolved_user_dn=None,
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    snapshot = client.get_group_membership_snapshot(
        user_identifier="name.surname",
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
        ],
        resolved_user_dn=None,
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    snapshot = client.get_group_membership_snapshot(
        user_identifier="name.surname",
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
        ],
        resolved_user_dn=None,
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    snapshot = client.get_group_membership_snapshot(
        user_identifier="name.surname",
        group_identifier="Engineers",
    )

    assert snapshot.is_member is False
    assert snapshot.membership_source == "direct_or_nested_unknown"


def test_membership_client_treats_empty_list_as_not_member():
    runner = _membership_runner([], resolved_user_dn=None)
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    snapshot = client.get_group_membership_snapshot(
        user_identifier="name.surname",
        group_identifier="Engineers",
    )

    assert snapshot.is_member is False


def test_membership_client_treats_none_data_as_not_member():
    runner = _membership_runner(None, resolved_user_dn=None)
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    snapshot = client.get_group_membership_snapshot(
        user_identifier="name.surname",
        group_identifier="Engineers",
    )

    assert snapshot.is_member is False


def test_membership_client_raises_sanitized_access_denied_error():
    runner = _membership_runner(
        None,
        ok=False,
        error="Access is denied.",
        resolved_user_dn=None,
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    with pytest.raises(
        ActiveDirectoryGroupMembershipInspectionError,
        match="Active Directory inspection failed: access denied.",
    ):
        client.get_group_membership_snapshot(
            user_identifier="name.surname",
            group_identifier="Engineers",
        )


def test_membership_client_sanitizes_generic_runner_failure():
    runner = _membership_runner(
        None,
        ok=False,
        error=(
            "At line:1 char:1\n"
            "+ Get-ADPrincipalGroupMembership @params\n"
            "    + CategoryInfo          : SomeError\n"
            "    + FullyQualifiedErrorId : SomeId,Get-ADPrincipalGroupMembership\n"
        ),
        resolved_user_dn=None,
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    with pytest.raises(
        ActiveDirectoryGroupMembershipInspectionError
    ) as exc_info:
        client.get_group_membership_snapshot(
            user_identifier="name.surname",
            group_identifier="Engineers",
        )

    message = str(exc_info.value)

    assert "failed during Active Directory inspection." in message

    for forbidden in (
        "At line:",
        "CategoryInfo",
        "FullyQualifiedErrorId",
        "Get-ADPrincipalGroupMembership @params",
    ):
        assert forbidden not in message


def test_membership_client_rejects_unsupported_data_shape():
    runner = _membership_runner("not a list", resolved_user_dn=None)
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    with pytest.raises(
        ActiveDirectoryGroupMembershipInspectionError,
        match="unsupported data shape",
    ):
        client.get_group_membership_snapshot(
            user_identifier="name.surname",
            group_identifier="Engineers",
        )


def test_membership_client_rejects_unsupported_list_items():
    runner = _membership_runner(
        [{"Name": "Engineers"}, "string-instead-of-dict"],
        resolved_user_dn=None,
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    with pytest.raises(
        ActiveDirectoryGroupMembershipInspectionError,
        match="unsupported list data",
    ):
        client.get_group_membership_snapshot(
            user_identifier="name.surname",
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
        user_identifier="name.surname",
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


# ------------------- Identity resolution & LDAP filtering ----------------


def test_escape_ldap_filter_value_escapes_special_characters():
    from inspectors.active_directory_powershell import _escape_ldap_filter_value

    assert _escape_ldap_filter_value("a*b") == r"a\2ab"
    assert _escape_ldap_filter_value("a(b") == r"a\28b"
    assert _escape_ldap_filter_value("a)b") == r"a\29b"
    assert _escape_ldap_filter_value("a\\b") == r"a\5cb"
    assert _escape_ldap_filter_value("a\x00b") == r"a\00b"
    assert _escape_ldap_filter_value("plain.value") == "plain.value"


def test_user_client_email_identifier_uses_ldap_filter_for_upn_and_mail():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=True,
                data={
                    "DisplayName": "Example User",
                    "UserPrincipalName": "user@example.com",
                    "Mail": "user@example.com",
                    "DistinguishedName": "CN=Example User,OU=Users,DC=ex,DC=com",
                },
            )
        }
    )
    client = ActiveDirectoryPowerShellUserClient(runner)

    snapshot = client.get_user_snapshot("user@example.com")

    assert snapshot.display_name == "Example User"

    assert len(runner.commands) == 1
    issued = runner.commands[0]
    assert issued.name == "Get-ADUser"
    assert "Identity" not in issued.parameters
    ldap_filter = issued.parameters["LDAPFilter"]
    assert ldap_filter == (
        "(|(userPrincipalName=user@example.com)(mail=user@example.com))"
    )


def test_user_client_email_identifier_with_special_chars_is_ldap_escaped():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=True,
                data={"DisplayName": "Example"},
            )
        }
    )
    ActiveDirectoryPowerShellUserClient(runner).get_user_snapshot(
        "evil*user@example.com"
    )

    ldap_filter = runner.commands[0].parameters["LDAPFilter"]
    assert r"\2a" in ldap_filter  # escaped *
    assert "*" not in ldap_filter.replace(r"\2a", "")


def test_user_client_non_email_identifier_uses_identity():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=True,
                data={"DisplayName": "Example User"},
            )
        }
    )
    client = ActiveDirectoryPowerShellUserClient(runner)

    client.get_user_snapshot("name.surname")

    issued = runner.commands[0]
    assert issued.name == "Get-ADUser"
    assert issued.parameters == {"Identity": "name.surname"}
    assert "LDAPFilter" not in issued.parameters


def test_membership_client_resolves_email_user_then_calls_membership_with_dn():
    resolved_dn = "CN=Resolved User,OU=Users,DC=ex,DC=com"
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=True,
                data={
                    "DistinguishedName": resolved_dn,
                    "SamAccountName": "resolved.user",
                    "UserPrincipalName": "user@example.com",
                },
            ),
            "Get-ADPrincipalGroupMembership": ActiveDirectoryCommandResult(
                command="Get-ADPrincipalGroupMembership",
                ok=True,
                data=[
                    {
                        "Name": "Engineers",
                        "SamAccountName": "engineers",
                        "DistinguishedName": "CN=Engineers,OU=Groups,DC=ex,DC=com",
                    }
                ],
            ),
        }
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    snapshot = client.get_group_membership_snapshot(
        user_identifier="user@example.com",
        group_identifier="Engineers",
    )

    assert snapshot.is_member is True
    assert snapshot.user_identifier == "user@example.com"

    # First call resolves the email via Get-ADUser LDAPFilter; second call
    # issues membership against the resolved DN.
    assert [c.name for c in runner.commands] == [
        "Get-ADUser",
        "Get-ADPrincipalGroupMembership",
    ]
    user_call = runner.commands[0]
    assert "Identity" not in user_call.parameters
    assert user_call.parameters["LDAPFilter"] == (
        "(|(userPrincipalName=user@example.com)(mail=user@example.com))"
    )
    assert runner.commands[1].parameters == {"Identity": resolved_dn}


def test_membership_client_uses_sam_account_name_when_dn_missing():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=True,
                data={
                    "SamAccountName": "resolved.user",
                    "UserPrincipalName": "user@example.com",
                },
            ),
            "Get-ADPrincipalGroupMembership": ActiveDirectoryCommandResult(
                command="Get-ADPrincipalGroupMembership",
                ok=True,
                data=[],
            ),
        }
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    client.get_group_membership_snapshot(
        user_identifier="user@example.com",
        group_identifier="Engineers",
    )

    assert runner.commands[1].parameters == {"Identity": "resolved.user"}


def test_membership_client_user_resolution_failure_is_sanitized():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=False,
                error=(
                    "At line:1 char:1\n"
                    "+ Get-ADUser @params -LDAPFilter ...\n"
                    "    + CategoryInfo          : ObjectNotFound\n"
                    "    + FullyQualifiedErrorId : SomeId,Get-ADUser\n"
                ),
            )
        }
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    with pytest.raises(
        ActiveDirectoryGroupMembershipInspectionError,
        match="AD user not found for membership inspection: user@example.com",
    ) as exc_info:
        client.get_group_membership_snapshot(
            user_identifier="user@example.com",
            group_identifier="Engineers",
        )

    message = str(exc_info.value)

    for forbidden in (
        "At line:",
        "CategoryInfo",
        "FullyQualifiedErrorId",
        "Get-ADUser @params",
    ):
        assert forbidden not in message

    # Membership command must not have been issued after resolution failure.
    issued = [c.name for c in runner.commands]
    assert issued == ["Get-ADUser"]


def test_membership_client_user_resolution_generic_failure_is_not_treated_as_not_found():
    """Generic resolver failures (no not-found / access-denied markers in
    the runner error) must surface as a `Get-ADUser failed during Active
    Directory inspection.` message — NOT as "AD user not found", which
    would falsely imply the user does not exist. The membership command
    must not be issued after a resolver failure either way.
    """
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=False,
                error=(
                    "At line:1 char:1\n"
                    "+ Get-ADUser @params -LDAPFilter ...\n"
                    "    + CategoryInfo          : NotSpecified: (:) []\n"
                    "    + FullyQualifiedErrorId : SomeOpaqueId,Get-ADUser\n"
                ),
            )
        }
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    with pytest.raises(
        ActiveDirectoryGroupMembershipInspectionError
    ) as exc_info:
        client.get_group_membership_snapshot(
            user_identifier="user@example.com",
            group_identifier="Engineers",
        )

    message = str(exc_info.value)

    assert message == "Get-ADUser failed during Active Directory inspection."

    assert "AD user not found" not in message

    for forbidden in (
        "At line:",
        "CategoryInfo",
        "FullyQualifiedErrorId",
        "Get-ADUser @params",
    ):
        assert forbidden not in message

    issued = [c.name for c in runner.commands]
    assert issued == ["Get-ADUser"]


def test_membership_client_user_resolution_empty_result_is_sanitized():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=True,
                data=[],
            )
        }
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    with pytest.raises(
        ActiveDirectoryGroupMembershipInspectionError,
        match="AD user not found for membership inspection: user@example.com",
    ):
        client.get_group_membership_snapshot(
            user_identifier="user@example.com",
            group_identifier="Engineers",
        )


def test_membership_client_user_resolution_access_denied_is_sanitized():
    runner = MockActiveDirectoryCommandRunner(
        results={
            "Get-ADUser": ActiveDirectoryCommandResult(
                command="Get-ADUser",
                ok=False,
                error="Access is denied.",
            )
        }
    )
    client = ActiveDirectoryPowerShellGroupMembershipClient(runner)

    with pytest.raises(
        ActiveDirectoryGroupMembershipInspectionError,
        match="Active Directory inspection failed: access denied.",
    ):
        client.get_group_membership_snapshot(
            user_identifier="user@example.com",
            group_identifier="Engineers",
        )
