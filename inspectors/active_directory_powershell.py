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


def _escape_ldap_filter_value(value: str) -> str:
    """RFC 4515 escape an LDAP filter assertion value.

    Escapes the special characters that would otherwise change the meaning
    of a filter: NUL, `*`, `(`, `)`, and the backslash itself.
    """
    out: list[str] = []

    for ch in value:
        if ch == "\\":
            out.append(r"\5c")
        elif ch == "*":
            out.append(r"\2a")
        elif ch == "(":
            out.append(r"\28")
        elif ch == ")":
            out.append(r"\29")
        elif ch == "\x00":
            out.append(r"\00")
        else:
            out.append(ch)

    return "".join(out)


def _looks_like_email(value: str) -> bool:
    return "@" in value


def _build_user_email_filter(value: str) -> str:
    escaped = _escape_ldap_filter_value(value)
    return f"(|(userPrincipalName={escaped})(mail={escaped}))"


def _build_user_lookup_command(user_identifier: str) -> ActiveDirectoryCommand:
    if _looks_like_email(user_identifier):
        return ActiveDirectoryCommand(
            name="Get-ADUser",
            parameters={"LDAPFilter": _build_user_email_filter(user_identifier)},
        )

    return ActiveDirectoryCommand(
        name="Get-ADUser",
        parameters={"Identity": user_identifier},
    )


# ---- Error sanitization ------------------------------------------------


_RAW_POWERSHELL_DIAGNOSTIC_MARKERS = (
    "At line:",
    "CategoryInfo",
    "FullyQualifiedErrorId",
    "Get-ADUser @params",
    "Get-ADGroup @params",
    "Get-ADPrincipalGroupMembership @params",
    "$ErrorActionPreference",
    "Import-Module",
    "ConvertTo-Json",
    "ConvertFrom-Json",
    "$payload",
    "$params",
    "$result",
)


def _classify_runner_error(error: str) -> str:
    normalized = error.lower()

    if (
        "not found" in normalized
        or "couldn't be found" in normalized
        or "cannot find an object with identity" in normalized
        or "objectnotfound" in normalized
    ):
        return "not_found"

    if (
        "access is denied" in normalized
        or "access denied" in normalized
        or "insufficient access rights" in normalized
        or "unauthorized" in normalized
    ):
        return "access_denied"

    return "other"


def _sanitize_ad_command_error(
    *,
    command: str,
    error: str,
    fallback: str,
) -> str:
    """Return a sanitized error string suitable for inspector summaries.

    Never echoes raw PowerShell diagnostics. Maps to a small set of stable
    messages plus a generic fallback.
    """
    classification = _classify_runner_error(error)

    if classification == "access_denied":
        return "Active Directory inspection failed: access denied."

    return f"{command} {fallback}"


# ---- User client -------------------------------------------------------


class ActiveDirectoryPowerShellUserClient(ActiveDirectoryUserInspectorClient):
    """Adapts a read-only AD command runner into the user inspector client."""

    def __init__(self, runner: ActiveDirectoryCommandRunner) -> None:
        self.runner = runner

    def get_user_snapshot(
        self, user_identifier: str
    ) -> ActiveDirectoryUserSnapshot:
        result = self.runner.run(_build_user_lookup_command(user_identifier))

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

    On-prem AD's `Get-ADPrincipalGroupMembership` does not accept an email
    address as `-Identity`. When the caller passes an email/UPN, the
    adapter first resolves the user via `Get-ADUser -LDAPFilter ...` and
    then issues the membership lookup against the resolved
    DistinguishedName / SamAccountName / UserPrincipalName.

    The effective list returned by `Get-ADPrincipalGroupMembership` can
    include nested membership; this adapter therefore reports
    `direct_or_nested_unknown` rather than overclaiming direct membership.
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
        resolved_identity = self._resolve_user_identity_for_membership(
            user_identifier
        )

        result = self.runner.run(
            ActiveDirectoryCommand(
                name="Get-ADPrincipalGroupMembership",
                parameters={"Identity": resolved_identity},
            )
        )

        if not result.ok:
            error = result.error or "command failed."
            sanitized = _sanitize_ad_command_error(
                command=result.command,
                error=error,
                fallback="failed during Active Directory inspection.",
            )
            raise ActiveDirectoryGroupMembershipInspectionError(sanitized)

        rows = _normalize_membership_rows(
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

    def _resolve_user_identity_for_membership(self, user_identifier: str) -> str:
        if not _looks_like_email(user_identifier):
            return user_identifier

        result = self.runner.run(_build_user_lookup_command(user_identifier))

        if not result.ok:
            classification = _classify_runner_error(result.error or "")

            if classification == "not_found":
                raise ActiveDirectoryGroupMembershipInspectionError(
                    "AD user not found for membership inspection: "
                    f"{user_identifier}"
                )

            if classification == "access_denied":
                raise ActiveDirectoryGroupMembershipInspectionError(
                    "Active Directory inspection failed: access denied."
                )

            raise ActiveDirectoryGroupMembershipInspectionError(
                "Get-ADUser failed during Active Directory inspection."
            )

        row = _first_row(
            result.data,
            on_unsupported=lambda: ActiveDirectoryGroupMembershipInspectionError(
                "Active Directory command returned unsupported data shape."
            ),
        )

        if row is None:
            raise ActiveDirectoryGroupMembershipInspectionError(
                "AD user not found for membership inspection: "
                f"{user_identifier}"
            )

        for key in ("DistinguishedName", "SamAccountName", "UserPrincipalName"):
            value = _optional_str(row.get(key))

            if value:
                return value

        raise ActiveDirectoryGroupMembershipInspectionError(
            "AD user not found for membership inspection: "
            f"{user_identifier}"
        )


# ---- Row helpers -------------------------------------------------------


def _required_row_for_user(
    result: ActiveDirectoryCommandResult,
    *,
    user_identifier: str,
) -> dict[str, object]:
    if not result.ok:
        error = result.error or "AD user lookup failed."
        classification = _classify_runner_error(error)

        if classification == "not_found":
            raise ActiveDirectoryUserNotFoundError(
                f"AD user not found: {user_identifier}"
            )

        if classification == "access_denied":
            raise ActiveDirectoryUserInspectionError(
                "Active Directory inspection failed: access denied."
            )

        raise ActiveDirectoryUserInspectionError(
            f"{result.command} failed during Active Directory inspection."
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
        classification = _classify_runner_error(error)

        if classification == "not_found":
            raise ActiveDirectoryGroupNotFoundError(
                f"AD group not found: {group_identifier}"
            )

        if classification == "access_denied":
            raise ActiveDirectoryGroupInspectionError(
                "Active Directory inspection failed: access denied."
            )

        raise ActiveDirectoryGroupInspectionError(
            f"{result.command} failed during Active Directory inspection."
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


def _normalize_membership_rows(
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
