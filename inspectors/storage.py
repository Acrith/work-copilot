import json
from pathlib import Path

from inspectors.models import InspectorResult


def build_inspector_output_dir(*, workspace: str, request_id: str) -> Path:
    return (
        Path(workspace)
        / ".work_copilot"
        / "servicedesk"
        / request_id
        / "inspectors"
    )


def build_inspector_result_path(
    *,
    workspace: str,
    request_id: str,
    inspector_id: str,
) -> Path:
    safe_inspector_id = inspector_id.replace("/", "_").replace("\\", "_")

    return (
        build_inspector_output_dir(
            workspace=workspace,
            request_id=request_id,
        )
        / f"{safe_inspector_id}.json"
    )


def save_inspector_result(
    *,
    workspace: str,
    request_id: str,
    result: InspectorResult,
) -> Path:
    path = build_inspector_result_path(
        workspace=workspace,
        request_id=request_id,
        inspector_id=result.inspector,
    )
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            result.to_dict(),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return path


def read_inspector_result_payload(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))