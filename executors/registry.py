"""Registry scaffold for the (future) ServiceDesk executor architecture.

Executors are write-capable and must always be approval-gated. This
module is scaffolding only — it does not register any real executor
backend, does not perform any external write, and is not wired into
`/sdp work` or `/sdp save-note` in this PR.

The default registry returned by `create_executor_registry()` is
empty by design; real executors will be added in later PRs as opt-in
backends.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from executors.models import (
    ExecutorCapability,
    ExecutorPreview,
    ExecutorRequest,
    ExecutorResult,
)

ExecutorPreviewHandler = Callable[[ExecutorRequest], ExecutorPreview]
ExecutorExecuteHandler = Callable[[ExecutorRequest], ExecutorResult]


@dataclass(frozen=True)
class ExecutorDefinition:
    """Static description of an executor and its handlers.

    `capability` is a coarse tag the registry can use to advertise
    what this executor can do. `requires_approval` is structural — it
    is True for every real executor and is exposed here as a property
    rather than a field so subclasses cannot weaken the boundary.
    """

    id: str
    description: str
    capability: ExecutorCapability
    preview_handler: ExecutorPreviewHandler
    execute_handler: ExecutorExecuteHandler

    @property
    def requires_approval(self) -> bool:
        return True

    def build_preview(self, request: ExecutorRequest) -> ExecutorPreview:
        return self.preview_handler(request)

    def execute(self, request: ExecutorRequest) -> ExecutorResult:
        return self.execute_handler(request)


class ExecutorAlreadyRegisteredError(ValueError):
    pass


class ExecutorNotFoundError(KeyError):
    pass


class ExecutorRegistry:
    """Registry for `ExecutorDefinition` instances.

    Empty by default. Adding an executor here does not wire it into
    any user-facing command — that is intentionally a separate
    decision in a later PR.
    """

    def __init__(self) -> None:
        self._definitions: dict[str, ExecutorDefinition] = {}

    def register(self, definition: ExecutorDefinition) -> None:
        if definition.id in self._definitions:
            raise ExecutorAlreadyRegisteredError(
                f"Executor already registered: {definition.id}"
            )
        self._definitions[definition.id] = definition

    def get(self, executor_id: str) -> ExecutorDefinition | None:
        return self._definitions.get(executor_id)

    def require(self, executor_id: str) -> ExecutorDefinition:
        definition = self.get(executor_id)
        if definition is None:
            raise ExecutorNotFoundError(
                f"No executor registered for id: {executor_id}"
            )
        return definition

    def list_executor_ids(self) -> list[str]:
        return sorted(self._definitions)

    def __contains__(self, executor_id: str) -> bool:
        return executor_id in self._definitions

    def __len__(self) -> int:
        return len(self._definitions)


def create_executor_registry() -> ExecutorRegistry:
    """Return a new, empty executor registry.

    No real executors are registered by default. Real executors will
    be added as opt-in backends in later PRs.
    """
    return ExecutorRegistry()


def register_executor(
    registry: ExecutorRegistry,
    definition: ExecutorDefinition,
) -> None:
    registry.register(definition)


def get_executor(
    registry: ExecutorRegistry,
    executor_id: str,
) -> ExecutorDefinition | None:
    return registry.get(executor_id)


def list_executor_ids(registry: ExecutorRegistry) -> list[str]:
    return registry.list_executor_ids()


__all__ = [
    "ExecutorAlreadyRegisteredError",
    "ExecutorDefinition",
    "ExecutorExecuteHandler",
    "ExecutorNotFoundError",
    "ExecutorPreviewHandler",
    "ExecutorRegistry",
    "create_executor_registry",
    "get_executor",
    "list_executor_ids",
    "register_executor",
]
