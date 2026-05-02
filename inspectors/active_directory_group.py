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


class ActiveDirectoryGroupNotFoundError(Exception):
    """Raised when the AD group cannot be found by a read-only lookup."""


class ActiveDirectoryGroupInspectionError(Exception):
    """Raised when AD group inspection fails before useful facts can be returned."""


@dataclass(frozen=True)
class ActiveDirectoryGroupSnapshot:
    group_identifier: str
    name: str | None = None
    sam_account_name: str | None = None
    mail: str | None = None
    group_scope: str | None = None
    group_category: str | None = None
    distinguished_name: str | None = None
    member_count: int | None = None


class ActiveDirectoryGroupInspectorClient(Protocol):
    """Read-only client interface for AD group metadata inspection."""

    def get_group_snapshot(
        self, group_identifier: str
    ) -> ActiveDirectoryGroupSnapshot:
        """Return read-only AD group metadata for one group."""


class MockActiveDirectoryGroupInspectorClient:
    """Deterministic mock client for tests and local wiring."""

    def __init__(
        self,
        snapshots: dict[str, ActiveDirectoryGroupSnapshot] | None = None,
    ) -> None:
        self.snapshots = snapshots or {}

    def get_group_snapshot(
        self, group_identifier: str
    ) -> ActiveDirectoryGroupSnapshot:
        snapshot = self.snapshots.get(group_identifier)

        if snapshot is None:
            raise ActiveDirectoryGroupNotFoundError(
                f"AD group not found: {group_identifier}"
            )

        return snapshot


def inspect_active_directory_group(
    request: InspectorRequest,
    client: ActiveDirectoryGroupInspectorClient,
) -> InspectorResult:
    group_identifier = _get_group_identifier(request)

    if group_identifier is None:
        return _error_result(
            request=request,
            code="missing_group_identifier",
            message=(
                "Missing group_name, sam_account_name, or group identifier "
                "input for Active Directory group inspection."
            ),
            recoverable=True,
        )

    try:
        snapshot = client.get_group_snapshot(group_identifier)
    except ActiveDirectoryGroupNotFoundError as exc:
        return InspectorResult(
            inspector=request.inspector,
            target=request.target,
            status=InspectorStatus.ERROR,
            summary=f"AD group not found: {group_identifier}",
            facts=[
                InspectorFact(
                    key="group_exists",
                    value=False,
                    source="read_only_active_directory_metadata",
                )
            ],
            limitations=_default_limitations(),
            errors=[
                InspectorError(
                    code="active_directory_group_not_found",
                    message=str(exc),
                    recoverable=True,
                )
            ],
        )
    except ActiveDirectoryGroupInspectionError as exc:
        return _error_result(
            request=request,
            code="active_directory_group_inspection_failed",
            message=str(exc),
            recoverable=True,
        )

    facts = _snapshot_to_facts(snapshot)
    evidence = _snapshot_to_evidence(snapshot)

    return InspectorResult(
        inspector=request.inspector,
        target=request.target,
        status=InspectorStatus.OK,
        summary=f"AD group metadata inspected for {snapshot.group_identifier}.",
        facts=facts,
        evidence=evidence,
        limitations=_default_limitations(),
    )


def _get_group_identifier(request: InspectorRequest) -> str | None:
    candidates = [
        request.inputs.get("group_name"),
        request.inputs.get("group_identifier"),
        request.inputs.get("sam_account_name"),
        request.inputs.get("target_group"),
        request.target.id,
    ]

    for candidate in candidates:
        if candidate is None:
            continue

        text = str(candidate).strip()

        if text:
            return text

    return None


def _snapshot_to_facts(
    snapshot: ActiveDirectoryGroupSnapshot,
) -> list[InspectorFact]:
    facts = [
        InspectorFact(
            key="group_exists",
            value=True,
            source="read_only_active_directory_metadata",
        )
    ]

    optional_fact_values: dict[str, object | None] = {
        "name": snapshot.name,
        "sam_account_name": snapshot.sam_account_name,
        "mail": snapshot.mail,
        "group_scope": snapshot.group_scope,
        "group_category": snapshot.group_category,
        "distinguished_name": snapshot.distinguished_name,
        "member_count": snapshot.member_count,
    }

    for key, value in optional_fact_values.items():
        if value is None:
            continue

        facts.append(
            InspectorFact(
                key=key,
                value=value,
                source="read_only_active_directory_metadata",
            )
        )

    return facts


def _snapshot_to_evidence(
    snapshot: ActiveDirectoryGroupSnapshot,
) -> list[InspectorEvidence]:
    evidence = [
        InspectorEvidence(
            label="group_identifier",
            value=snapshot.group_identifier,
        )
    ]

    if snapshot.name:
        evidence.append(
            InspectorEvidence(label="name", value=snapshot.name)
        )

    if snapshot.sam_account_name:
        evidence.append(
            InspectorEvidence(
                label="sam_account_name",
                value=snapshot.sam_account_name,
            )
        )

    return evidence


def _default_limitations() -> list[str]:
    return [
        "Member object content beyond identifiers not inspected",
        "Sensitive attributes beyond basic group metadata not inspected",
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
