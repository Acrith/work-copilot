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


class ExchangeMailboxNotFoundError(Exception):
    """Raised when the mailbox cannot be found by a read-only lookup."""


class ExchangeMailboxInspectionError(Exception):
    """Raised when mailbox inspection fails before useful facts can be returned."""


@dataclass(frozen=True)
class ExchangeMailboxSnapshot:
    mailbox_address: str
    display_name: str | None = None
    primary_smtp_address: str | None = None
    recipient_type: str | None = None
    mailbox_size: str | None = None
    item_count: int | None = None
    archive_status: str | None = None
    auto_expanding_archive_status: str | None = None
    retention_policy: str | None = None
    quota_warning_status: str | None = None


class ExchangeMailboxInspectorClient(Protocol):
    """Read-only client interface for Exchange mailbox metadata inspection."""

    def get_mailbox_snapshot(self, mailbox_address: str) -> ExchangeMailboxSnapshot:
        """Return read-only mailbox metadata for one mailbox."""


class MockExchangeMailboxInspectorClient:
    """Deterministic mock client for tests and local wiring."""

    def __init__(self, snapshots: dict[str, ExchangeMailboxSnapshot] | None = None) -> None:
        self.snapshots = snapshots or {}

    def get_mailbox_snapshot(self, mailbox_address: str) -> ExchangeMailboxSnapshot:
        snapshot = self.snapshots.get(mailbox_address)

        if snapshot is None:
            raise ExchangeMailboxNotFoundError(f"Mailbox not found: {mailbox_address}")

        return snapshot


def inspect_exchange_mailbox(
    request: InspectorRequest,
    client: ExchangeMailboxInspectorClient,
) -> InspectorResult:
    mailbox_address = _get_mailbox_address(request)

    if mailbox_address is None:
        return _error_result(
            request=request,
            code="missing_mailbox_address",
            message="Missing mailbox_address input for Exchange mailbox inspection.",
            recoverable=True,
        )

    try:
        snapshot = client.get_mailbox_snapshot(mailbox_address)
    except ExchangeMailboxNotFoundError as exc:
        return InspectorResult(
            inspector=request.inspector,
            target=request.target,
            status=InspectorStatus.ERROR,
            summary=f"Mailbox not found: {mailbox_address}",
            facts=[
                InspectorFact(
                    key="mailbox_exists",
                    value=False,
                    source="read_only_exchange_metadata",
                )
            ],
            limitations=_default_limitations(),
            errors=[
                InspectorError(
                    code="mailbox_not_found",
                    message=str(exc),
                    recoverable=True,
                )
            ],
        )
    except ExchangeMailboxInspectionError as exc:
        return _error_result(
            request=request,
            code="exchange_mailbox_inspection_failed",
            message=str(exc),
            recoverable=True,
        )

    facts = _snapshot_to_facts(snapshot)
    evidence = _snapshot_to_evidence(snapshot)
    recommendations = _build_recommendations(snapshot)

    return InspectorResult(
        inspector=request.inspector,
        target=request.target,
        status=InspectorStatus.OK,
        summary=f"Mailbox metadata inspected for {snapshot.mailbox_address}.",
        facts=facts,
        evidence=evidence,
        limitations=_default_limitations(),
        recommendations=recommendations,
    )


def _get_mailbox_address(request: InspectorRequest) -> str | None:
    mailbox_address = request.inputs.get("mailbox_address") or request.target.id

    if not mailbox_address:
        return None

    return str(mailbox_address).strip() or None


def _snapshot_to_facts(snapshot: ExchangeMailboxSnapshot) -> list[InspectorFact]:
    facts = [
        InspectorFact(
            key="mailbox_exists",
            value=True,
            source="read_only_exchange_metadata",
        )
    ]

    optional_fact_values: dict[str, object | None] = {
        "display_name": snapshot.display_name,
        "primary_smtp_address": snapshot.primary_smtp_address,
        "recipient_type": snapshot.recipient_type,
        "mailbox_size": snapshot.mailbox_size,
        "item_count": snapshot.item_count,
        "archive_status": snapshot.archive_status,
        "auto_expanding_archive_status": snapshot.auto_expanding_archive_status,
        "retention_policy": snapshot.retention_policy,
        "quota_warning_status": snapshot.quota_warning_status,
    }

    for key, value in optional_fact_values.items():
        if value is None:
            continue

        facts.append(
            InspectorFact(
                key=key,
                value=value,
                source="read_only_exchange_metadata",
            )
        )

    return facts


def _snapshot_to_evidence(snapshot: ExchangeMailboxSnapshot) -> list[InspectorEvidence]:
    evidence = [
        InspectorEvidence(
            label="mailbox_address",
            value=snapshot.mailbox_address,
        )
    ]

    if snapshot.primary_smtp_address:
        evidence.append(
            InspectorEvidence(
                label="primary_smtp_address",
                value=snapshot.primary_smtp_address,
            )
        )

    if snapshot.recipient_type:
        evidence.append(
            InspectorEvidence(
                label="recipient_type",
                value=snapshot.recipient_type,
            )
        )

    return evidence


def _build_recommendations(snapshot: ExchangeMailboxSnapshot) -> list[str]:
    recommendations: list[str] = []

    archive_status = (snapshot.archive_status or "").lower()
    auto_expanding_status = (snapshot.auto_expanding_archive_status or "").lower()
    quota_status = (snapshot.quota_warning_status or "").lower()

    if archive_status in {"disabled", "not_enabled", "none"}:
        recommendations.append(
            "exchange.archive.enable may be relevant if archive is required."
        )

    archive_quota_issue = "archive" in quota_status and (
        "full" in quota_status or "quota" in quota_status
    )

    if archive_status == "enabled" and archive_quota_issue:
        recommendations.append(
            "exchange.archive.enable_auto_expanding may be relevant if archive capacity "
            "is the issue."
        )

    if archive_status == "enabled" and auto_expanding_status in {"disabled", "not_enabled"}:
        recommendations.append(
            "Confirm whether auto-expanding archive is needed before any archive expansion."
        )

    return recommendations


def _default_limitations() -> list[str]:
    return [
        "Mailbox content not inspected",
        "Attachments not inspected",
        "No permission changes performed",
        "No archive or retention changes performed",
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