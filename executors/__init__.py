"""ServiceDesk executor architecture (scaffolding only).

Executors are the future, write-capable counterpart to read-only
inspectors. Every executor is approval-gated, must produce a
preview before any external change, and must be built from typed
fields rather than arbitrary model-generated shell or PowerShell.

This package currently exposes only the framework types and an empty
registry. No real executor backend is registered, no external write
happens, and no executor is wired into `/sdp work` or
`/sdp save-note`. Real executors will be added as opt-in backends in
later PRs.
"""

from executors.models import (
    ExecutorCapability,
    ExecutorChange,
    ExecutorError,
    ExecutorPreview,
    ExecutorRequest,
    ExecutorResult,
    ExecutorStatus,
    ExecutorTarget,
)
from executors.registry import (
    ExecutorAlreadyRegisteredError,
    ExecutorDefinition,
    ExecutorExecuteHandler,
    ExecutorNotFoundError,
    ExecutorPreviewHandler,
    ExecutorRegistry,
    create_executor_registry,
    get_executor,
    list_executor_ids,
    register_executor,
)

__all__ = [
    "ExecutorAlreadyRegisteredError",
    "ExecutorCapability",
    "ExecutorChange",
    "ExecutorDefinition",
    "ExecutorError",
    "ExecutorExecuteHandler",
    "ExecutorNotFoundError",
    "ExecutorPreview",
    "ExecutorPreviewHandler",
    "ExecutorRegistry",
    "ExecutorRequest",
    "ExecutorResult",
    "ExecutorStatus",
    "ExecutorTarget",
    "create_executor_registry",
    "get_executor",
    "list_executor_ids",
    "register_executor",
]
