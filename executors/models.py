"""Typed models for the (future) ServiceDesk executor architecture.

Executors are the write-capable counterpart to inspectors. They are
ALWAYS approval-gated and must build constrained operations from typed
fields — not from arbitrary model-generated shell or PowerShell.

This module is scaffolding only. No real backends are registered, no
external writes happen, and no executor is wired into `/sdp work` or
`/sdp save-note` in this PR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ExecutorStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ExecutorCapability(StrEnum):
    """Coarse capability tag for an executor.

    Used by the registry to advertise what a given executor can do.
    Real executors must always be approval-gated regardless of
    capability.
    """

    EXCHANGE_MAILBOX_PERMISSION_WRITE = (
        "exchange.mailbox_permission.write"
    )
    EXCHANGE_MAILBOX_ARCHIVE_WRITE = "exchange.mailbox_archive.write"
    ACTIVE_DIRECTORY_USER_WRITE = "active_directory.user.write"
    ACTIVE_DIRECTORY_GROUP_MEMBERSHIP_WRITE = (
        "active_directory.group_membership.write"
    )


@dataclass(frozen=True)
class ExecutorTarget:
    type: str
    id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutorRequest:
    """Typed request handed to an executor.

    The `operation` and `inputs` together fully describe what the
    executor should do. Executors must build their constrained
    operation from these typed fields; they must NOT execute
    free-form strings.
    """

    executor_id: str
    request_id: str
    target: ExecutorTarget
    operation: str
    inputs: dict[str, Any] = field(default_factory=dict)
    source: str = "skill_plan"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutorChange:
    """One concrete change an executor will make if approved."""

    field: str
    before: str | None
    after: str | None
    description: str = ""


@dataclass(frozen=True)
class ExecutorPreview:
    """Preview an executor produces BEFORE any external change.

    Every executor must produce a preview, and `requires_approval`
    is structurally always True for Work Copilot executors. The
    flag is exposed as a read-only property rather than an init
    field so a caller (or a future UI layer that trusts the value)
    cannot construct a preview with `requires_approval=False`.

    The TUI/approval layer is responsible for surfacing the preview
    to the operator and gating execution.
    """

    executor_id: str
    title: str
    summary: str
    changes: list[ExecutorChange] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def requires_approval(self) -> bool:
        return True


@dataclass(frozen=True)
class ExecutorError:
    code: str
    message: str
    recoverable: bool = False


@dataclass(frozen=True)
class ExecutorResult:
    """Structured result returned by an executor after execution.

    `verification_recommendations` are read-only follow-ups (e.g.
    "re-run `active_directory.user.inspect` for this user") that the
    operator should run to confirm the change took effect. Executors
    do not run those verifications themselves.
    """

    executor_id: str
    status: ExecutorStatus
    summary: str
    facts: list[dict[str, Any]] = field(default_factory=list)
    errors: list[ExecutorError] = field(default_factory=list)
    verification_recommendations: list[str] = field(default_factory=list)


__all__ = [
    "ExecutorCapability",
    "ExecutorChange",
    "ExecutorError",
    "ExecutorPreview",
    "ExecutorRequest",
    "ExecutorResult",
    "ExecutorStatus",
    "ExecutorTarget",
]
