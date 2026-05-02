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


_ARCHIVE_DISABLED_VALUES = {"disabled", "not_enabled", "none", "not applicable", "not_applicable"}
_ARCHIVE_ENABLED_VALUES = {"enabled", "active"}
_ARCHIVE_AUTO_DISABLED_VALUES = {"disabled", "not_enabled", "false", "off"}


def _build_recommendations(snapshot: ExchangeMailboxSnapshot) -> list[str]:
    archive_status = (snapshot.archive_status or "").lower()
    auto_expanding_status = (snapshot.auto_expanding_archive_status or "").lower()
    quota_status = (snapshot.quota_warning_status or "").lower()

    primary_full = _primary_mailbox_appears_full(quota_status)
    archive_full = _archive_mailbox_appears_full(quota_status)
    appears_large = primary_full or archive_full
    archive_disabled = archive_status in _ARCHIVE_DISABLED_VALUES
    archive_enabled = archive_status in _ARCHIVE_ENABLED_VALUES
    auto_expanding_disabled = auto_expanding_status in _ARCHIVE_AUTO_DISABLED_VALUES
    has_archive_signal = bool(archive_status) and (
        appears_large or "archive" in quota_status
    )

    recommendations: list[str] = []

    if archive_disabled and primary_full:
        recommendations.append(
            "Mailbox appears full and archive is disabled. Review whether enabling "
            "archive (exchange.archive.enable) is appropriate. No change has been made."
        )
    elif archive_disabled and has_archive_signal:
        recommendations.append(
            "Archive is disabled. Review whether enabling archive "
            "(exchange.archive.enable) is appropriate based on the requester's needs. "
            "No change has been made."
        )

    if archive_enabled and archive_full and auto_expanding_disabled:
        recommendations.append(
            "Archive is enabled and appears full while auto-expanding archive is "
            "disabled. Review whether auto-expanding archive "
            "(exchange.archive.enable_auto_expanding) is appropriate. "
            "No change has been made."
        )
    elif archive_enabled and archive_full:
        recommendations.append(
            "Archive is enabled and appears full. Review the retention policy and "
            "archive capacity before any change. No change has been made."
        )
    elif archive_enabled and primary_full:
        recommendations.append(
            "Primary mailbox appears full while archive is enabled. Review the "
            "retention policy and confirm archive move policy is processing. "
            "No change has been made."
        )
    elif archive_enabled and auto_expanding_disabled and "archive" in quota_status:
        recommendations.append(
            "Archive is enabled and a quota signal mentions the archive while "
            "auto-expanding archive is disabled. Review whether auto-expanding "
            "archive is appropriate. No change has been made."
        )

    if not recommendations:
        if appears_large and not archive_status:
            recommendations.append(
                "Mailbox appears full but archive status is unknown. Manual review "
                "of archive configuration is recommended. No change has been made."
            )
        else:
            recommendations.append(
                "No archive-readiness recommendation was generated. Existing facts "
                "do not indicate a mailbox-full or archive-capacity problem. "
                "No change has been made."
            )

    return recommendations


def _primary_mailbox_appears_full(quota_status: str) -> bool:
    if not quota_status:
        return False

    if "archive" in quota_status:
        return False

    return _quota_indicates_full(quota_status)


def _archive_mailbox_appears_full(quota_status: str) -> bool:
    if not quota_status or "archive" not in quota_status:
        return False

    return _quota_indicates_full(quota_status)


def _quota_indicates_full(quota_status: str) -> bool:
    return any(
        marker in quota_status
        for marker in (
            "full",
            "warning",
            "near_quota",
            "near quota",
            "send_prohibited",
            "send prohibited",
            "send_receive_prohibited",
            "send receive prohibited",
            "issuewarning",
            "prohibitsend",
        )
    )


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