from collections.abc import Callable

from inspectors.models import (
    InspectorError,
    InspectorRequest,
    InspectorResult,
    InspectorStatus,
)

InspectorHandler = Callable[[InspectorRequest], InspectorResult]


class InspectorRegistry:
    """Registry and runner for read-only inspectors."""

    def __init__(self) -> None:
        self._handlers: dict[str, InspectorHandler] = {}

    def register(self, inspector_id: str, handler: InspectorHandler) -> None:
        if inspector_id in self._handlers:
            raise ValueError(f"Inspector already registered: {inspector_id}")

        self._handlers[inspector_id] = handler

    def get(self, inspector_id: str) -> InspectorHandler | None:
        return self._handlers.get(inspector_id)

    def run(self, request: InspectorRequest) -> InspectorResult:
        handler = self.get(request.inspector)

        if handler is None:
            return InspectorResult(
                inspector=request.inspector,
                target=request.target,
                status=InspectorStatus.ERROR,
                summary=f"Inspector not found: {request.inspector}",
                errors=[
                    InspectorError(
                        code="inspector_not_found",
                        message=f"No inspector registered for {request.inspector}",
                        recoverable=True,
                    )
                ],
            )

        return handler(request)


def create_default_inspector_registry() -> InspectorRegistry:
    return InspectorRegistry()