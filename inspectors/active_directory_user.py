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


class ActiveDirectoryUserNotFoundError(Exception):
    """Raised when the AD user cannot be found by a read-only lookup."""


class ActiveDirectoryUserInspectionError(Exception):
    """Raised when AD user inspection fails before useful facts can be returned."""


@dataclass(frozen=True)
class ActiveDirectoryUserSnapshot:
    user_identifier: str
    display_name: str | None = None
    user_principal_name: str | None = None
    sam_account_name: str | None = None
    mail: str | None = None
    enabled: bool | None = None
    distinguished_name: str | None = None
    department: str | None = None
    title: str | None = None
    manager: str | None = None


class ActiveDirectoryUserInspectorClient(Protocol):
    """Read-only client interface for AD user metadata inspection."""

    def get_user_snapshot(self, user_identifier: str) -> ActiveDirectoryUserSnapshot:
        """Return read-only AD user metadata for one user."""


class MockActiveDirectoryUserInspectorClient:
    """Deterministic mock client for tests and local wiring."""

    def __init__(
        self,
        snapshots: dict[str, ActiveDirectoryUserSnapshot] | None = None,
    ) -> None:
        self.snapshots = snapshots or {}

    def get_user_snapshot(self, user_identifier: str) -> ActiveDirectoryUserSnapshot:
        snapshot = self.snapshots.get(user_identifier)

        if snapshot is None:
            raise ActiveDirectoryUserNotFoundError(
                f"AD user not found: {user_identifier}"
            )

        return snapshot


def inspect_active_directory_user(
    request: InspectorRequest,
    client: ActiveDirectoryUserInspectorClient,
) -> InspectorResult:
    user_identifier = _get_user_identifier(request)

    if user_identifier is None:
        return _error_result(
            request=request,
            code="missing_user_identifier",
            message=(
                "Missing user_principal_name, sam_account_name, or user identifier "
                "input for Active Directory user inspection."
            ),
            recoverable=True,
        )

    try:
        snapshot = client.get_user_snapshot(user_identifier)
    except ActiveDirectoryUserNotFoundError as exc:
        return InspectorResult(
            inspector=request.inspector,
            target=request.target,
            status=InspectorStatus.ERROR,
            summary=f"AD user not found: {user_identifier}",
            facts=[
                InspectorFact(
                    key="user_exists",
                    value=False,
                    source="read_only_active_directory_metadata",
                )
            ],
            limitations=_default_limitations(),
            errors=[
                InspectorError(
                    code="active_directory_user_not_found",
                    message=str(exc),
                    recoverable=True,
                )
            ],
        )
    except ActiveDirectoryUserInspectionError as exc:
        return _error_result(
            request=request,
            code="active_directory_user_inspection_failed",
            message=str(exc),
            recoverable=True,
        )

    facts = _snapshot_to_facts(snapshot)
    evidence = _snapshot_to_evidence(snapshot)

    return InspectorResult(
        inspector=request.inspector,
        target=request.target,
        status=InspectorStatus.OK,
        summary=f"AD user metadata inspected for {snapshot.user_identifier}.",
        facts=facts,
        evidence=evidence,
        limitations=_default_limitations(),
    )


def _get_user_identifier(request: InspectorRequest) -> str | None:
    candidates = [
        request.inputs.get("user_principal_name"),
        request.inputs.get("sam_account_name"),
        request.inputs.get("user_identifier"),
        request.inputs.get("target_user"),
        request.inputs.get("target_user_email"),
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
    snapshot: ActiveDirectoryUserSnapshot,
) -> list[InspectorFact]:
    facts = [
        InspectorFact(
            key="user_exists",
            value=True,
            source="read_only_active_directory_metadata",
        )
    ]

    optional_fact_values: dict[str, object | None] = {
        "display_name": snapshot.display_name,
        "user_principal_name": snapshot.user_principal_name,
        "sam_account_name": snapshot.sam_account_name,
        "mail": snapshot.mail,
        "enabled": snapshot.enabled,
        "distinguished_name": snapshot.distinguished_name,
        "department": snapshot.department,
        "title": snapshot.title,
        "manager": snapshot.manager,
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
    snapshot: ActiveDirectoryUserSnapshot,
) -> list[InspectorEvidence]:
    evidence = [
        InspectorEvidence(
            label="user_identifier",
            value=snapshot.user_identifier,
        )
    ]

    if snapshot.user_principal_name:
        evidence.append(
            InspectorEvidence(
                label="user_principal_name",
                value=snapshot.user_principal_name,
            )
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
        "Account passwords not inspected",
        "Sensitive attributes beyond basic account metadata not inspected",
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
