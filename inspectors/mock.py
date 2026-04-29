from inspectors.models import (
    InspectorEvidence,
    InspectorFact,
    InspectorRequest,
    InspectorResult,
    InspectorStatus,
)
from inspectors.registry import InspectorRegistry


def inspect_mock_exchange_mailbox(request: InspectorRequest) -> InspectorResult:
    mailbox_address = str(request.inputs.get("mailbox_address") or request.target.id)

    return InspectorResult(
        inspector=request.inspector,
        target=request.target,
        status=InspectorStatus.OK,
        summary=f"Mock mailbox inspection completed for {mailbox_address}.",
        facts=[
            InspectorFact(
                key="mailbox_exists",
                value=True,
                source="mock_inspector",
            ),
            InspectorFact(
                key="recipient_type",
                value="UserMailbox",
                source="mock_inspector",
            ),
            InspectorFact(
                key="archive_status",
                value="disabled",
                source="mock_inspector",
            ),
            InspectorFact(
                key="auto_expanding_archive_status",
                value="not_applicable",
                source="mock_inspector",
            ),
        ],
        evidence=[
            InspectorEvidence(
                label="mailbox_address",
                value=mailbox_address,
            )
        ],
        limitations=[
            "Mock inspector only; no external system inspected",
            "Mailbox content not inspected",
            "No permission changes performed",
            "No archive or retention changes performed",
        ],
        recommendations=[
            "exchange.archive.enable may be relevant if archive is required",
        ],
    )


def create_mock_inspector_registry() -> InspectorRegistry:
    registry = InspectorRegistry()
    registry.register("exchange.mailbox.inspect", inspect_mock_exchange_mailbox)
    return registry