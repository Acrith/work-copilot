from typing import Any

from inspectors.active_directory_command_runner import (
    ActiveDirectoryCommand,
    ActiveDirectoryCommandResult,
    ActiveDirectoryCommandRunner,
)
from inspectors.active_directory_group import (
    ActiveDirectoryGroupInspectionError,
    ActiveDirectoryGroupInspectorClient,
    ActiveDirectoryGroupNotFoundError,
    ActiveDirectoryGroupSnapshot,
)
from inspectors.active_directory_group_membership import (
    ActiveDirectoryGroupMembershipInspectionError,
    ActiveDirectoryGroupMembershipInspectorClient,
    ActiveDirectoryGroupMembershipSnapshot,
)
from inspectors.active_directory_user import (
    ActiveDirectoryUserInspectionError,
    ActiveDirectoryUserInspectorClient,
    ActiveDirectoryUserNotFoundError,
    ActiveDirectoryUserSnapshot,
)


class ActiveDirectoryPowerShellUserClient(ActiveDirectoryUserInspectorClient):
    """Adapts a read-only AD command runner into the user inspector client."""

    def __init__(self, runner: ActiveDirectoryCommandRunner) -> None:
        self.runner = runner

    def get_user_snapshot(
        self, user_identifier: str
    ) -> ActiveDirectoryUserSnapshot:
        result = self.runner.run(
            ActiveDirectoryCommand(
                name="Get-ADUser",
                parameters={"Identity": user_identifier},
            )
        )

        row = _required_row_for_user(result, user_identifier=user_identifier)

        return ActiveDirectoryUserSnapshot(
            user_identifier=user_identifier,
            display_name=_optional_str(row.get("DisplayName")),
            first_name=_optional_str(row.get("GivenName")),
            last_name=_optional_str(row.get("Surname")),
            user_principal_name=_optional_str(row.get("UserPrincipalName")),
            sam_account_name=_optional_str(row.get("SamAccountName")),
            mail=_optional_str(row.get("Mail")),
            enabled=_optional_bool(row.get("Enabled")),
            distinguished_name=_optional_str(row.get("DistinguishedName")),
            department=_optional_str(row.get("Department")),
            title=_optional_str(row.get("Title")),
            office=_optional_str(row.get("Office")),
            office_phone=_optional_str(row.get("OfficePhone")),
            mobile_phone=_optional_str(row.get("MobilePhone")),
            manager=_optional_str(row.get("Manager")),
        )


class ActiveDirectoryPowerShellGroupClient(ActiveDirectoryGroupInspectorClient):
    """Adapts a read-only AD command runner into the group inspector client."""

    def __init__(self, runner: ActiveDirectoryCommandRunner) -> None:
        self.runner = runner

    def get_group_snapshot(
        self, group_identifier: str
    ) -> ActiveDirectoryGroupSnapshot:
        result = self.runner.run(
            ActiveDirectoryCommand(
                name="Get-ADGroup",
                parameters={"Identity": group_identifier},
            )
        )

        row = _required_row_for_group(result, group_identifier=group_identifier)

        return ActiveDirectoryGroupSnapshot(
            group_identifier=group_identifier,
            name=_optional_str(row.get("Name")),
            sam_account_name=_optional_str(row.get("SamAccountName")),
            mail=_optional_str(row.get("Mail")),
            group_scope=_optional_str(row.get("GroupScope")),
            group_category=_optional_str(row.get("GroupCategory")),
            distinguished_name=_optional_str(row.get("DistinguishedName")),
            member_count=_optional_int(row.get("MemberCount")),
        )


class ActiveDirectoryPowerShellGroupMembershipClient(
    ActiveDirectoryGroupMembershipInspectorClient
):
    """Adapts a read-only AD command runner into the membership inspector client.

    Uses Get-ADPrincipalGroupMembership against the user, then checks whether
    the requested group identifier matches any returned group by Name,
    SamAccountName, or DistinguishedName. The effective list returned by
    Get-ADPrincipalGroupMembership can include nested membership; this
    adapter therefore reports `direct_or_nested_unknown` rather than
    overclaiming direct membership.
    """

    MEMBERSHIP_SOURCE = "direct_or_nested_unknown"

    def __init__(self, runner: ActiveDirectoryCommandRunner) -> None:
        self.runner = runner

    def get_group_membership_snapshot(
        self,
        *,
        user_identifier: str,
        group_identifier: str,
    ) -> ActiveDirectoryGroupMembershipSnapshot:
        result = self.runner.run(
            ActiveDirectoryCommand(
                name="Get-ADPrincipalGroupMembership",
                parameters={"Identity": user_identifier},
            )
        )

        if not result.ok:
            error = result.error or "Group membership lookup failed."
            raise ActiveDirectoryGroupMembershipInspectionError(
                f"{result.command} failed: {error}"
            )

        rows = _normalize_rows(
            result.data,
            command_name="Get-ADPrincipalGroupMembership",
        )

        is_member = any(
            _row_matches_group(row, group_identifier=group_identifier)
            for row in rows
        )

        return ActiveDirectoryGroupMembershipSnapshot(
            user_identifier=user_identifier,
            group_identifier=group_identifier,
            is_member=is_member,
            membership_source=self.MEMBERSHIP_SOURCE,
        )


def _required_row_for_user(
    result: ActiveDirectoryCommandResult,
    *,
    user_identifier: str,
) -> dict[str, object]:
    if not result.ok:
        error = result.error or "AD user lookup failed."

        if _looks_like_not_found(error):
            raise ActiveDirectoryUserNotFoundError(
                f"AD user not found: {user_identifier}"
            )

        raise ActiveDirectoryUserInspectionError(
            f"{result.command} failed: {error}"
        )

    row = _first_row(
        result.data,
        on_unsupported=lambda: ActiveDirectoryUserInspectionError(
            "Active Directory command returned unsupported data shape."
        ),
    )

    if row is None:
        raise ActiveDirectoryUserNotFoundError(
            f"AD user not found: {user_identifier}"
        )

    return row


def _required_row_for_group(
    result: ActiveDirectoryCommandResult,
    *,
    group_identifier: str,
) -> dict[str, object]:
    if not result.ok:
        error = result.error or "AD group lookup failed."

        if _looks_like_not_found(error):
            raise ActiveDirectoryGroupNotFoundError(
                f"AD group not found: {group_identifier}"
            )

        raise ActiveDirectoryGroupInspectionError(
            f"{result.command} failed: {error}"
        )

    row = _first_row(
        result.data,
        on_unsupported=lambda: ActiveDirectoryGroupInspectionError(
            "Active Directory command returned unsupported data shape."
        ),
    )

    if row is None:
        raise ActiveDirectoryGroupNotFoundError(
            f"AD group not found: {group_identifier}"
        )

    return row


def _first_row(
    data: Any,
    *,
    on_unsupported,
) -> dict[str, object] | None:
    if data is None:
        return None

    if isinstance(data, dict):
        return data

    if isinstance(data, list):
        if not data:
            return None

        first_item = data[0]

        if not isinstance(first_item, dict):
            raise on_unsupported()

        return first_item

    raise on_unsupported()


def _normalize_rows(
    data: Any,
    *,
    command_name: str,
) -> list[dict[str, object]]:
    if data is None:
        return []

    if isinstance(data, dict):
        return [data]

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                raise ActiveDirectoryGroupMembershipInspectionError(
                    f"{command_name} returned unsupported list data."
                )

        return list(data)

    raise ActiveDirectoryGroupMembershipInspectionError(
        f"{command_name} returned unsupported data shape."
    )


def _row_matches_group(
    row: dict[str, object],
    *,
    group_identifier: str,
) -> bool:
    target = group_identifier.strip().lower()

    if not target:
        return False

    for key in ("Name", "SamAccountName", "DistinguishedName"):
        value = row.get(key)

        if value is None:
            continue

        if str(value).strip().lower() == target:
            return True

    return False


def _looks_like_not_found(error: str) -> bool:
    normalized = error.lower()

    return (
        "not found" in normalized
        or "couldn't be found" in normalized
        or "cannot find an object with identity" in normalized
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return str(value)

    text = str(value).strip()

    return text or None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    text = str(value).strip()

    if not text.lstrip("-").isdigit():
        return None

    return int(text)


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    text = str(value).strip().lower()

    if text in {"true", "yes", "1", "enabled"}:
        return True

    if text in {"false", "no", "0", "disabled"}:
        return False

    return None
