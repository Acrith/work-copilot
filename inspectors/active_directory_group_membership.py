from dataclasses import dataclass
from typing import Protocol

from inspectors.models import (
    InspectorError,
    InspectorEvidence,
    InspectorFact,
    InspectorRequest,
    InspectorResult,
    InspectorStatus,
)


class ActiveDirectoryGroupMembershipInspectionError(Exception):
    """Raised when AD group membership inspection cannot proceed safely."""


@dataclass(frozen=True)
class ActiveDirectoryGroupMembershipSnapshot:
    user_identifier: str
    group_identifier: str
    is_member: bool
    membership_source: str | None = None


class ActiveDirectoryGroupMembershipInspectorClient(Protocol):
    """Read-only client interface for AD group membership inspection."""

    def get_group_membership_snapshot(
        self,
        *,
        user_identifier: str,
        group_identifier: str,
    ) -> ActiveDirectoryGroupMembershipSnapshot:
        """Return read-only AD group membership metadata for one user/group pair."""


class MockActiveDirectoryGroupMembershipInspectorClient:
    """Deterministic mock client for tests and local wiring."""

    def __init__(
        self,
        snapshots: dict[
            tuple[str, str], ActiveDirectoryGroupMembershipSnapshot
        ]
        | None = None,
    ) -> None:
        self.snapshots = snapshots or {}

    def get_group_membership_snapshot(
        self,
        *,
        user_identifier: str,
        group_identifier: str,
    ) -> ActiveDirectoryGroupMembershipSnapshot:
        snapshot = self.snapshots.get((user_identifier, group_identifier))

        if snapshot is None:
            return ActiveDirectoryGroupMembershipSnapshot(
                user_identifier=user_identifier,
                group_identifier=group_identifier,
                is_member=False,
                membership_source="mock_unknown",
            )

        return snapshot


def inspect_active_directory_group_membership(
    request: InspectorRequest,
    client: ActiveDirectoryGroupMembershipInspectorClient,
) -> InspectorResult:
    user_identifier = _get_input(request, ["user_principal_name", "user_identifier", "target_user"])
    group_identifier = _get_input(request, ["group_name", "group_identifier", "target_group"])

    if user_identifier is None or group_identifier is None:
        return _error_result(
            request=request,
            code="missing_membership_inputs",
            message=(
                "Missing user and/or group identifier inputs for "
                "Active Directory group membership inspection."
            ),
            recoverable=True,
        )

    try:
        snapshot = client.get_group_membership_snapshot(
            user_identifier=user_identifier,
            group_identifier=group_identifier,
        )
    except ActiveDirectoryGroupMembershipInspectionError as exc:
        return _error_result(
            request=request,
            code="active_directory_group_membership_inspection_failed",
            message=str(exc),
            recoverable=True,
        )

    facts = [
        InspectorFact(
            key="user_identifier",
            value=snapshot.user_identifier,
            source="read_only_active_directory_metadata",
        ),
        InspectorFact(
            key="group_identifier",
            value=snapshot.group_identifier,
            source="read_only_active_directory_metadata",
        ),
        InspectorFact(
            key="is_member",
            value=snapshot.is_member,
            source="read_only_active_directory_metadata",
        ),
    ]

    if snapshot.membership_source is not None:
        facts.append(
            InspectorFact(
                key="membership_source",
                value=snapshot.membership_source,
                source="read_only_active_directory_metadata",
            )
        )

    evidence = [
        InspectorEvidence(label="user_identifier", value=snapshot.user_identifier),
        InspectorEvidence(label="group_identifier", value=snapshot.group_identifier),
    ]

    return InspectorResult(
        inspector=request.inspector,
        target=request.target,
        status=InspectorStatus.OK,
        summary=(
            f"AD group membership inspected for user "
            f"{snapshot.user_identifier} and group {snapshot.group_identifier}."
        ),
        facts=facts,
        evidence=evidence,
        limitations=_default_limitations(),
    )


def _get_input(request: InspectorRequest, keys: list[str]) -> str | None:
    for key in keys:
        value = request.inputs.get(key)

        if value is None:
            continue

        text = str(value).strip()

        if text:
            return text

    return None


def _default_limitations() -> list[str]:
    return [
        "Membership inspection limited to the requested user/group pair",
        "Sensitive attributes beyond basic membership metadata not inspected",
        "No AD writes performed",
        "No ServiceDesk writes performed",
    ]


def _error_result(
    *,
    request: InspectorRequest,
    code: str,
    message: str,
    recoverable: bool,
) -> InspectorResult:
    return InspectorResult(
        inspector=request.inspector,
        target=request.target,
        status=InspectorStatus.ERROR,
        summary=message,
        limitations=_default_limitations(),
        errors=[
            InspectorError(
                code=code,
                message=message,
                recoverable=recoverable,
            )
        ],
    )
