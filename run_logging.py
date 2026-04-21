import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from runtime_events import EventSink, RuntimeEvent, event_payload


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
        self.run_logger.record(event_type, **payload)

    def save(self) -> Path:
        return self.run_logger.save()
