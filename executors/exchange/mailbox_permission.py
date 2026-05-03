"""Mock/no-op Exchange mailbox permission executor definition.

Represents a future approval-gated operation that grants Full Access
permission on a mailbox to a trustee. This module is mock/no-op only:

- the request builder accepts only typed `mailbox` / `trustee` /
  optional `auto_mapping` fields, never an arbitrary operation name
  or shell/PowerShell string;
- the preview describes the constrained operation and warns that
  this is a mock/no-op definition;
- the execute handler always returns `ExecutorStatus.SKIPPED` with a
  clear "no external write was performed" summary;
- this executor is NOT registered in the default
  `create_executor_registry()`. Callers must opt in explicitly via
  `register_mock_exchange_executors(...)` or
  `create_mock_exchange_executor_registry()`.

No real Exchange backend is contacted, no PowerShell write is run,
and no ServiceDesk write happens.
"""

from __future__ import annotations

from typing import Any

from executors.models import (
    ExecutorCapability,
    ExecutorChange,
    ExecutorPreview,
    ExecutorRequest,
    ExecutorResult,
    ExecutorStatus,
    ExecutorTarget,
)
from executors.registry import (
    ExecutorDefinition,
    ExecutorRegistry,
    create_executor_registry,
    register_executor,
)

EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID = (
    "exchange.mailbox_permission.grant_full_access"
)
EXCHANGE_GRANT_FULL_ACCESS_OPERATION = "grant_full_access"
EXCHANGE_GRANT_FULL_ACCESS_RIGHTS = "FullAccess"

_MOCK_NO_OP_WARNING = (
    "Mock/no-op executor: this definition is scaffolding for a future "
    "approval-gated Exchange write. No external write will be "
    "performed."
)
_MOCK_NO_OP_EXECUTE_SUMMARY = (
    "No external write was performed: "
    "exchange.mailbox_permission.grant_full_access is a mock/no-op "
    "executor in this build. Approval and real backend wiring will "
    "be added in a future PR."
)


def build_exchange_grant_full_access_request(
    *,
    request_id: str,
    mailbox: str,
    trustee: str,
    auto_mapping: bool | None = None,
    source: str = "skill_plan",
    metadata: dict[str, Any] | None = None,
) -> ExecutorRequest:
    """Build a typed `ExecutorRequest` for the (future) Exchange Full
    Access grant.

    The builder constrains the operation and access-rights values; it
    never accepts arbitrary operation names or shell/PowerShell
    strings. Missing or blank `mailbox` / `trustee` raise
    `ValueError`.
    """
    cleaned_mailbox = _required_str_field(mailbox, field_name="mailbox")
    cleaned_trustee = _required_str_field(trustee, field_name="trustee")

    inputs: dict[str, Any] = {
        "mailbox": cleaned_mailbox,
        "trustee": cleaned_trustee,
        "access_rights": EXCHANGE_GRANT_FULL_ACCESS_RIGHTS,
    }
    if auto_mapping is not None:
        inputs["auto_mapping"] = bool(auto_mapping)

    return ExecutorRequest(
        executor_id=EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID,
        request_id=request_id,
        target=ExecutorTarget(
            type="exchange_mailbox",
            id=cleaned_mailbox,
            metadata={"source": source},
        ),
        operation=EXCHANGE_GRANT_FULL_ACCESS_OPERATION,
        inputs=inputs,
        source=source,
        metadata=dict(metadata or {}),
    )


def _required_str_field(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(
            f"`{field_name}` must be a non-empty string"
        )
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(
            f"`{field_name}` must not be blank"
        )
    return cleaned


def build_exchange_grant_full_access_preview(
    request: ExecutorRequest,
) -> ExecutorPreview:
    """Build a preview for the (future) Exchange Full Access grant.

    Always opt-in to approval at the model level: `requires_approval`
    is structurally True via the `ExecutorPreview` property.
    """
    _ensure_grant_full_access_request(request)

    mailbox = str(request.inputs.get("mailbox", ""))
    trustee = str(request.inputs.get("trustee", ""))
    access_rights = str(
        request.inputs.get(
            "access_rights", EXCHANGE_GRANT_FULL_ACCESS_RIGHTS
        )
    )
    auto_mapping = request.inputs.get("auto_mapping")

    summary_lines = [
        f"Grant `{access_rights}` mailbox permission on `{mailbox}` "
        f"to trustee `{trustee}`.",
    ]
    if auto_mapping is not None:
        summary_lines.append(
            f"Auto-mapping: {'yes' if auto_mapping else 'no'}."
        )

    changes = [
        ExecutorChange(
            field="mailbox_permission",
            before=None,
            after=(
                f"{trustee} has {access_rights} on mailbox {mailbox}"
            ),
            description=(
                f"Add {access_rights} permission for `{trustee}` on "
                f"mailbox `{mailbox}`."
            ),
        )
    ]

    return ExecutorPreview(
        executor_id=EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID,
        title="Grant Full Access mailbox permission",
        summary=" ".join(summary_lines),
        changes=changes,
        warnings=[_MOCK_NO_OP_WARNING],
    )


def execute_exchange_grant_full_access_mock(
    request: ExecutorRequest,
) -> ExecutorResult:
    """Mock/no-op execute handler.

    Always returns `ExecutorStatus.SKIPPED`. Does not contact
    Exchange, does not run any PowerShell, does not contact
    ServiceDesk. The `verification_recommendations` describe the
    read-only follow-up an operator should run after a future real
    write — this handler does not run them itself.
    """
    _ensure_grant_full_access_request(request)

    mailbox = str(request.inputs.get("mailbox", ""))
    trustee = str(request.inputs.get("trustee", ""))
    access_rights = str(
        request.inputs.get(
            "access_rights", EXCHANGE_GRANT_FULL_ACCESS_RIGHTS
        )
    )

    facts: list[dict[str, Any]] = [
        {
            "mailbox": mailbox,
            "trustee": trustee,
            "access_rights": access_rights,
            "performed": False,
            "reason": "mock_no_op_executor",
        }
    ]
    if "auto_mapping" in request.inputs:
        facts[0]["auto_mapping"] = bool(request.inputs["auto_mapping"])

    return ExecutorResult(
        executor_id=EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID,
        status=ExecutorStatus.SKIPPED,
        summary=_MOCK_NO_OP_EXECUTE_SUMMARY,
        facts=facts,
        verification_recommendations=[
            "After a future real write, re-run "
            "`exchange.mailbox.inspect` for the mailbox to confirm the "
            "permission grant and re-check the trustee. This handler "
            "does not run that verification itself.",
        ],
    )


def _ensure_grant_full_access_request(request: ExecutorRequest) -> None:
    if request.executor_id != EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID:
        raise ValueError(
            "ExecutorRequest is for a different executor: "
            f"{request.executor_id}"
        )
    if request.operation != EXCHANGE_GRANT_FULL_ACCESS_OPERATION:
        raise ValueError(
            "Unsupported operation for "
            f"{EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID}: "
            f"{request.operation}"
        )
    access_rights = request.inputs.get(
        "access_rights", EXCHANGE_GRANT_FULL_ACCESS_RIGHTS
    )
    if access_rights != EXCHANGE_GRANT_FULL_ACCESS_RIGHTS:
        raise ValueError(
            "Unsupported access_rights for "
            f"{EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID}: "
            f"{access_rights}"
        )


def create_exchange_grant_full_access_executor_definition() -> (
    ExecutorDefinition
):
    return ExecutorDefinition(
        id=EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID,
        description=(
            "Mock/no-op definition for the future approval-gated "
            "Exchange Full Access mailbox permission grant. Execute "
            "always returns SKIPPED in this build."
        ),
        capability=ExecutorCapability.EXCHANGE_MAILBOX_PERMISSION_WRITE,
        preview_handler=build_exchange_grant_full_access_preview,
        execute_handler=execute_exchange_grant_full_access_mock,
    )


def register_mock_exchange_executors(registry: ExecutorRegistry) -> None:
    """Opt-in registration of the mock Exchange executor definitions.

    Not called from `create_executor_registry()`. Callers must
    intentionally invoke this to opt in.
    """
    register_executor(
        registry,
        create_exchange_grant_full_access_executor_definition(),
    )


def create_mock_exchange_executor_registry() -> ExecutorRegistry:
    """Convenience: a fresh registry pre-populated with the mock
    Exchange executor definitions only.
    """
    registry = create_executor_registry()
    register_mock_exchange_executors(registry)
    return registry
