"""Local-only persistence of ServiceDesk skill-plan validation results.

Writes a small JSON sidecar next to `latest_skill_plan.md` so the TUI's
advisory validation output also lives on disk for later inspection,
debugging, or future tooling. No ServiceDesk, AD, or Exchange writes.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from draft_exports import (
    build_servicedesk_latest_skill_plan_json_path,
    build_servicedesk_latest_skill_plan_path,
    build_servicedesk_latest_skill_plan_validation_path,
)
from servicedesk_skill_plan.models import (
    ExtractedInput,
    ParsedServiceDeskSkillPlan,
    SkillPlanAutomationHandoff,
)
from servicedesk_skill_plan.parser import parse_servicedesk_skill_plan
from servicedesk_skill_plan.validation import (
    SkillPlanValidationFinding,
    format_skill_plan_validation_findings,
    validate_servicedesk_skill_plan,
)

SKILL_PLAN_JSON_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SkillPlanValidationPersistenceResult:
    """Bundled result for the persisting validator.

    `lines` are the formatted advisory log lines (compatible with the
    existing TUI logger). `payload` is the JSON-serializable validation
    record that is also written to disk.
    """

    lines: list[str]
    payload: dict[str, object]


def validate_skill_plan_text_for_persistence(
    text: str,
) -> SkillPlanValidationPersistenceResult:
    """Parse + validate a saved skill plan and return both the existing
    advisory log lines and a JSON-serializable payload. Never raises.

    On unexpected parse/validate failure, returns a payload with
    `has_errors=True` and a single synthetic `validation_unavailable`
    finding so the persisted record stays honest about why validation
    could not be completed.
    """
    try:
        plan = parse_servicedesk_skill_plan(text)
        findings = validate_servicedesk_skill_plan(plan)
    except Exception as exc:  # noqa: BLE001 - persistence path must not raise
        message = f"Skill plan validation unavailable: {exc}"
        return SkillPlanValidationPersistenceResult(
            lines=[message],
            payload={
                "has_errors": True,
                "findings": [
                    {
                        "severity": "error",
                        "code": "validation_unavailable",
                        "message": message,
                    }
                ],
            },
        )

    lines = format_skill_plan_validation_findings(findings)
    has_errors = any(finding.severity == "error" for finding in findings)

    return SkillPlanValidationPersistenceResult(
        lines=lines,
        payload={
            "has_errors": has_errors,
            "findings": [_finding_to_dict(finding) for finding in findings],
        },
    )


def _finding_to_dict(finding: SkillPlanValidationFinding) -> dict[str, str]:
    return {
        "severity": finding.severity,
        "code": finding.code,
        "message": finding.message,
    }


def persist_skill_plan_validation_payload(
    *,
    workspace: str,
    request_id: str,
    payload: dict[str, object],
) -> Path:
    """Write the validation payload as a JSON sidecar.

    Creates parent directories as needed. Returns the written path.
    """
    path = build_servicedesk_latest_skill_plan_validation_path(
        workspace=workspace,
        request_id=request_id,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return path


def persist_and_format_skill_plan_validation(
    *,
    workspace: str,
    request_id: str,
    text: str,
) -> list[str]:
    """Validate `text`, persist the JSON sidecar, and return advisory
    log lines for the TUI.

    If JSON persistence itself fails, the validation lines are returned
    unchanged plus an extra advisory line describing the persistence
    failure. The validation lines themselves are unaffected so the TUI
    flow is preserved.
    """
    result = validate_skill_plan_text_for_persistence(text)

    try:
        persist_skill_plan_validation_payload(
            workspace=workspace,
            request_id=request_id,
            payload=result.payload,
        )
    except Exception as exc:  # noqa: BLE001 - persistence is advisory
        return [
            *result.lines,
            f"Skill plan validation persistence unavailable: {exc}",
        ]

    return result.lines


def serialize_parsed_skill_plan(
    plan: ParsedServiceDeskSkillPlan,
    *,
    request_id: str,
) -> dict[str, object]:
    """Convert a `ParsedServiceDeskSkillPlan` into a stable JSON-ready
    dict using the parser's existing field shapes.

    Stays close to the parser models: status / needed_now /
    ready_for_inspection / ready_for_execution remain strings, and
    suggested tool lists remain lists of strings.
    """
    return {
        "schema_version": SKILL_PLAN_JSON_SCHEMA_VERSION,
        "request_id": request_id,
        "metadata": dict(plan.metadata),
        "extracted_inputs": [
            _extracted_input_to_dict(item) for item in plan.extracted_inputs
        ],
        "missing_information_needed_now": list(
            plan.missing_information_needed_now
        ),
        "current_blocker": plan.current_blocker,
        "automation_handoff": _automation_handoff_to_dict(
            plan.automation_handoff
        ),
    }


def _extracted_input_to_dict(item: ExtractedInput) -> dict[str, str]:
    return {
        "field": item.field,
        "status": item.status,
        "value": item.value,
        "evidence": item.evidence,
        "needed_now": item.needed_now,
    }


def _automation_handoff_to_dict(
    handoff: SkillPlanAutomationHandoff,
) -> dict[str, object]:
    return {
        "ready_for_inspection": handoff.ready_for_inspection,
        "ready_for_execution": handoff.ready_for_execution,
        "suggested_inspector_tools": list(handoff.suggested_inspector_tools),
        "suggested_execute_tools": list(handoff.suggested_execute_tools),
        "automation_blocker": handoff.automation_blocker,
    }


def persist_skill_plan_json_sidecar(
    *,
    workspace: str,
    request_id: str,
    text: str,
) -> list[str]:
    """Parse `text` and write the structured `latest_skill_plan.json`
    sidecar. Never raises.

    Returns advisory log lines (empty on a clean success). On parse
    failure, removes any stale `latest_skill_plan.json` so future
    workflow code does not trust outdated structured data, and returns
    a single advisory line. On write failure, also makes a best-effort
    attempt to remove any stale `latest_skill_plan.json` for the same
    reason, and returns a single advisory line.
    """
    path = build_servicedesk_latest_skill_plan_json_path(
        workspace=workspace,
        request_id=request_id,
    )

    try:
        plan = parse_servicedesk_skill_plan(text)
    except Exception as exc:  # noqa: BLE001 - persistence path must not raise
        _best_effort_unlink(path)
        return [f"Skill plan JSON sidecar unavailable: {exc}"]

    payload = serialize_parsed_skill_plan(plan, request_id=request_id)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001 - persistence is advisory
        # latest_skill_plan.json is intended to become trusted workflow
        # input. If we cannot write the fresh payload, do not leave an
        # older version in place that future workflow code might trust.
        _best_effort_unlink(path)
        return [f"Skill plan JSON sidecar unavailable: {exc}"]

    return []


def _best_effort_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:  # noqa: BLE001 - best-effort cleanup
        pass


def build_persisting_validation_callback(
    *,
    workspace: str,
    request_id: str,
) -> Callable[[str], list[str]]:
    """Return a `post_save_callback` for the model-turn worker that
    validates the saved skill plan, persists the validation JSON
    sidecar and the structured skill-plan JSON sidecar, and returns the
    advisory log lines.
    """

    def _callback(text: str) -> list[str]:
        validation_lines = persist_and_format_skill_plan_validation(
            workspace=workspace,
            request_id=request_id,
            text=text,
        )
        json_lines = persist_skill_plan_json_sidecar(
            workspace=workspace,
            request_id=request_id,
            text=text,
        )
        return [*validation_lines, *json_lines]

    return _callback


def refresh_skill_plan_sidecars_from_markdown(
    *,
    workspace: str,
    request_id: str,
) -> list[str]:
    """Local-only sidecar refresh: re-parse `latest_skill_plan.md` from
    disk and rewrite both sidecars (validation JSON + structured JSON)
    without calling the model or any external system. Never raises.

    Use case: a manually-edited `latest_skill_plan.md` left the sidecars
    stale or unreadable, and we want to bring them back in sync without
    re-prompting the model (which would overwrite the manual edits).

    Returns advisory log lines suitable for the TUI. If the Markdown is
    missing, returns a single advisory line without touching either
    sidecar.
    """
    md_path = build_servicedesk_latest_skill_plan_path(
        workspace=workspace, request_id=request_id
    )

    if not md_path.exists():
        return [
            f"No local skill plan found for request {request_id}; "
            "cannot refresh sidecars from latest_skill_plan.md.",
        ]

    try:
        text = md_path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - refresh path must not raise
        return [
            "Skill plan sidecar refresh unavailable: "
            f"could not read latest_skill_plan.md: {exc}",
        ]

    validation_lines = persist_and_format_skill_plan_validation(
        workspace=workspace,
        request_id=request_id,
        text=text,
    )
    json_lines = persist_skill_plan_json_sidecar(
        workspace=workspace,
        request_id=request_id,
        text=text,
    )
    return [*validation_lines, *json_lines]


# ---------- Structured skill-plan JSON sidecar loader -------------------


class SkillPlanJsonLoadError(Exception):
    """Raised internally by `deserialize_skill_plan_payload` when the
    payload cannot be safely reconstructed. The loader catches this and
    converts it into a `SkillPlanJsonLoadResult` with `readable=False`.
    """


@dataclass(frozen=True)
class SkillPlanJsonLoadResult:
    """Result of attempting to load `latest_skill_plan.json`.

    Display/consumer-friendly: never raises. Distinguishes missing
    (`exists=False`), unreadable (`exists=True, readable=False`), stale
    (`exists=True, readable=False, stale=True`), and successfully
    loaded (`readable=True, plan=<...>`).
    """

    exists: bool = False
    readable: bool = False
    plan: ParsedServiceDeskSkillPlan | None = None
    error: str | None = None
    stale: bool = False


def deserialize_skill_plan_payload(
    payload: object,
) -> ParsedServiceDeskSkillPlan:
    """Reconstruct a `ParsedServiceDeskSkillPlan` from a JSON-decoded
    payload.

    Pure function: no filesystem access. Raises
    `SkillPlanJsonLoadError` on shape problems (non-object payload,
    unsupported `schema_version`, non-list tool fields). Tolerates
    missing optional sections by falling back to parser-model defaults.
    """
    if not isinstance(payload, dict):
        raise SkillPlanJsonLoadError(
            "Structured skill plan sidecar is not a JSON object."
        )

    schema_version = payload.get("schema_version")
    if schema_version != SKILL_PLAN_JSON_SCHEMA_VERSION:
        raise SkillPlanJsonLoadError(
            "Structured skill plan sidecar has unsupported "
            f"schema_version {schema_version!r}; expected "
            f"{SKILL_PLAN_JSON_SCHEMA_VERSION}."
        )

    metadata = _deserialize_metadata(payload.get("metadata"))
    extracted_inputs = _deserialize_extracted_inputs(
        payload.get("extracted_inputs")
    )
    missing_info = _deserialize_string_list(
        payload.get("missing_information_needed_now"),
        field_name="missing_information_needed_now",
    )
    current_blocker = _deserialize_optional_str(
        payload.get("current_blocker"),
        field_name="current_blocker",
    )
    handoff = _deserialize_automation_handoff(
        payload.get("automation_handoff")
    )

    return ParsedServiceDeskSkillPlan(
        metadata=metadata,
        extracted_inputs=extracted_inputs,
        missing_information_needed_now=missing_info,
        current_blocker=current_blocker,
        automation_handoff=handoff,
    )


def _deserialize_metadata(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SkillPlanJsonLoadError(
            "Structured skill plan sidecar `metadata` must be a JSON "
            "object."
        )
    metadata: dict[str, str] = {}
    for key, raw in value.items():
        if not isinstance(key, str):
            raise SkillPlanJsonLoadError(
                "Structured skill plan sidecar `metadata` has a "
                "non-string key."
            )
        if raw is None:
            metadata[key] = ""
        elif isinstance(raw, str):
            metadata[key] = raw
        else:
            raise SkillPlanJsonLoadError(
                "Structured skill plan sidecar `metadata` value for "
                f"`{key}` is not a string."
            )
    return metadata


def _deserialize_extracted_inputs(value: object) -> list[ExtractedInput]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SkillPlanJsonLoadError(
            "Structured skill plan sidecar `extracted_inputs` must be a "
            "JSON array."
        )
    inputs: list[ExtractedInput] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise SkillPlanJsonLoadError(
                "Structured skill plan sidecar `extracted_inputs` entry "
                f"at index {index} is not a JSON object."
            )
        inputs.append(
            ExtractedInput(
                field=_input_str_field(item, "field", index),
                status=_input_str_field(item, "status", index),
                value=_input_str_field(item, "value", index),
                evidence=_input_str_field(item, "evidence", index),
                needed_now=_input_str_field(item, "needed_now", index),
            )
        )
    return inputs


def _input_str_field(item: dict, key: str, index: int) -> str:
    raw = item.get(key)
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise SkillPlanJsonLoadError(
            "Structured skill plan sidecar `extracted_inputs` entry "
            f"at index {index} has non-string `{key}`."
        )
    return raw


def _deserialize_automation_handoff(
    value: object,
) -> SkillPlanAutomationHandoff:
    if value is None:
        return SkillPlanAutomationHandoff()
    if not isinstance(value, dict):
        raise SkillPlanJsonLoadError(
            "Structured skill plan sidecar `automation_handoff` must be "
            "a JSON object."
        )
    return SkillPlanAutomationHandoff(
        ready_for_inspection=_deserialize_optional_str(
            value.get("ready_for_inspection"),
            field_name="automation_handoff.ready_for_inspection",
        ),
        ready_for_execution=_deserialize_optional_str(
            value.get("ready_for_execution"),
            field_name="automation_handoff.ready_for_execution",
        ),
        suggested_inspector_tools=_deserialize_string_list(
            value.get("suggested_inspector_tools"),
            field_name="automation_handoff.suggested_inspector_tools",
        ),
        suggested_execute_tools=_deserialize_string_list(
            value.get("suggested_execute_tools"),
            field_name="automation_handoff.suggested_execute_tools",
        ),
        automation_blocker=_deserialize_optional_str(
            value.get("automation_blocker"),
            field_name="automation_handoff.automation_blocker",
        ),
    )


def _deserialize_string_list(value: object, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SkillPlanJsonLoadError(
            f"Structured skill plan sidecar `{field_name}` must be a JSON "
            "array of strings."
        )
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise SkillPlanJsonLoadError(
                f"Structured skill plan sidecar `{field_name}` contains a "
                "non-string entry."
            )
        items.append(item)
    return items


def _deserialize_optional_str(
    value: object, *, field_name: str
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SkillPlanJsonLoadError(
            f"Structured skill plan sidecar `{field_name}` must be a "
            "string or null."
        )
    return value


def load_skill_plan_json_sidecar(
    *,
    workspace: str,
    request_id: str,
) -> SkillPlanJsonLoadResult:
    """Load `latest_skill_plan.json` for a request. Never raises.

    Returns:
    - `exists=False, readable=False, plan=None` when the JSON sidecar
      file is missing.
    - `exists=True, readable=False, stale=True` when the JSON sidecar
      is older than `latest_skill_plan.md` (a conservative freshness
      check, since users may manually edit the Markdown).
    - `exists=True, readable=False, error=<...>` on read/parse/shape
      failures.
    - `exists=True, readable=True, plan=<...>` on success.
    """
    json_path = build_servicedesk_latest_skill_plan_json_path(
        workspace=workspace, request_id=request_id
    )

    if not json_path.exists():
        return SkillPlanJsonLoadResult()

    md_path = build_servicedesk_latest_skill_plan_path(
        workspace=workspace, request_id=request_id
    )
    try:
        if md_path.exists():
            md_mtime = md_path.stat().st_mtime
            json_mtime = json_path.stat().st_mtime
            if json_mtime < md_mtime:
                return SkillPlanJsonLoadResult(
                    exists=True,
                    readable=False,
                    stale=True,
                    error=(
                        "Structured skill plan sidecar is older than "
                        "latest_skill_plan.md."
                    ),
                )
    except Exception as exc:  # noqa: BLE001 - loader must not raise
        return SkillPlanJsonLoadResult(
            exists=True,
            readable=False,
            error=(
                "Structured skill plan sidecar freshness check failed: "
                f"{exc}"
            ),
        )

    try:
        raw = json_path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 - loader must not raise
        return SkillPlanJsonLoadResult(
            exists=True,
            readable=False,
            error=(
                "Structured skill plan sidecar could not be read: "
                f"{exc}"
            ),
        )

    try:
        plan = deserialize_skill_plan_payload(payload)
    except SkillPlanJsonLoadError as exc:
        return SkillPlanJsonLoadResult(
            exists=True,
            readable=False,
            error=str(exc),
        )

    return SkillPlanJsonLoadResult(
        exists=True,
        readable=True,
        plan=plan,
    )
