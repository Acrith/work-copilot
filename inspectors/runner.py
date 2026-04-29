from dataclasses import dataclass
from pathlib import Path

from inspectors.models import InspectorRequest, InspectorResult
from inspectors.registry import InspectorRegistry
from inspectors.storage import save_inspector_result


@dataclass(frozen=True)
class InspectorRunOutput:
    result: InspectorResult
    saved_path: Path


def run_inspector_and_save(
    *,
    registry: InspectorRegistry,
    request: InspectorRequest,
    workspace: str,
) -> InspectorRunOutput:
    if request.request_id is None or not request.request_id.strip():
        raise ValueError("request_id is required to save inspector result")

    result = registry.run(request)
    saved_path = save_inspector_result(
        workspace=workspace,
        request_id=request.request_id,
        result=result,
    )

    return InspectorRunOutput(
        result=result,
        saved_path=saved_path,
    )