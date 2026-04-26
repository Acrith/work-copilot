import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from runtime_events import EventSink, RuntimeEvent, event_payload


def _get_connector_tool_metadata(tool_name: str) -> dict[str, str | None] | None:
    try:
        from tool_registry import get_tool_definition
    except Exception:
        return None

    try:
        definition = get_tool_definition(tool_name)
    except KeyError:
        return None

    if definition.connector is None:
        return None

    return {
        "connector": definition.connector,
        "resource_type": definition.resource_type,
    }


def _summarize_connector_result(
    *,
    tool_name: str,
    result: Any,
) -> dict[str, Any]:
    metadata = _get_connector_tool_metadata(tool_name) or {}

    summary: dict[str, Any] = {
        "redacted": True,
        "kind": "connector_tool_result",
        "connector": metadata.get("connector"),
        "resource_type": metadata.get("resource_type"),
    }

    if isinstance(result, dict):
        summary["result_type"] = "object"
        summary["top_level_keys"] = sorted(str(key) for key in result.keys())

        if "error" in result:
            summary["has_error"] = True

        if "request_id" in result:
            summary["request_id"] = result["request_id"]

        for key, value in result.items():
            if isinstance(value, list):
                summary[f"{key}_count"] = len(value)
            elif isinstance(value, dict):
                summary[f"{key}_type"] = "object"

        nested_request = result.get("request")
        if isinstance(nested_request, dict):
            if "id" in nested_request:
                summary["request_id"] = nested_request["id"]
            if "status" in nested_request:
                summary["has_status"] = True
            if "subject" in nested_request:
                summary["has_subject"] = True
            if "description" in nested_request:
                summary["has_description"] = True

        if "description" in result:
            summary["has_description"] = True

    elif isinstance(result, list):
        summary["result_type"] = "list"
        summary["item_count"] = len(result)

    else:
        summary["result_type"] = type(result).__name__

    return summary


def _sanitize_tool_result_payload(
    *,
    tool_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    metadata = _get_connector_tool_metadata(tool_name)

    if metadata is None:
        return payload

    sanitized = deepcopy(payload)

    if "result" in sanitized:
        sanitized["result"] = _summarize_connector_result(
            tool_name=tool_name,
            result=sanitized["result"],
        )

    return sanitized


def sanitize_event_payload(
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if event_type != "tool_result":
        return payload

    tool_name = payload.get("name")
    tool_payload = payload.get("payload")

    if not isinstance(tool_name, str) or not isinstance(tool_payload, dict):
        return payload

    sanitized = deepcopy(payload)
    sanitized["payload"] = _sanitize_tool_result_payload(
        tool_name=tool_name,
        payload=tool_payload,
    )
    return sanitized


class RunLogger:
    def __init__(self, log_dir: str | Path, metadata: dict[str, Any]) -> None:
        self.log_dir = Path(log_dir)
        self.run_id = uuid4().hex[:12]
        self.started_at = datetime.now(UTC)
        self.metadata = metadata
        self.events: list[dict[str, Any]] = []
        self.saved_path: Path | None = None

    def record(self, event_type: str, **data: Any) -> None:
        self.events.append(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "type": event_type,
                **data,
            }
        )

    def save(self) -> Path:
        if self.saved_path is not None:
            return self.saved_path

        self.log_dir.mkdir(parents=True, exist_ok=True)

        filename_timestamp = self.started_at.strftime("%Y%m%d_%H%M%S")
        path = self.log_dir / f"{filename_timestamp}_{self.run_id}.json"

        payload = {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
            "metadata": self.metadata,
            "events": self.events,
        }

        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        self.saved_path = path
        return path


class RunLogEventSink(EventSink):
    def __init__(self, run_logger: RunLogger) -> None:
        self.run_logger = run_logger

    def emit(self, event: RuntimeEvent) -> None:
        event_type, payload = event_payload(event)
        sanitized_payload = sanitize_event_payload(event_type, payload)
        self.run_logger.record(event_type, **sanitized_payload)

    def save(self) -> Path:
        return self.run_logger.save()