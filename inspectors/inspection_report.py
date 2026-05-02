from dataclasses import dataclass
from pathlib import Path

from inspectors.storage import (
    build_inspector_output_dir,
    build_inspector_result_path,
    read_inspector_result_payload,
)

SUPPORTED_REPORT_INSPECTOR_IDS = {
    "exchange.mailbox.inspect",
}


class InspectionReportError(Exception):
    """Raised when an inspection report cannot be built locally."""


class InspectionReportNotFoundError(InspectionReportError):
    """Raised when no supported inspector JSON exists for the request."""


@dataclass(frozen=True)
class InspectionReportOutput:
    request_id: str
    report_path: Path
    inspector_id: str
    source_json_path: Path


def build_servicedesk_inspection_report_path(
    *,
    workspace: str,
    request_id: str,
) -> Path:
    return (
        Path(workspace)
        / ".work_copilot"
        / "servicedesk"
        / request_id
        / "inspection_report.md"
    )


def build_servicedesk_inspection_report(
    *,
    workspace: str,
    request_id: str,
) -> InspectionReportOutput:
    inspector_id, source_path, payload = _load_supported_inspector_payload(
        workspace=workspace,
        request_id=request_id,
    )

    report_text = render_inspection_report_markdown(
        request_id=request_id,
        payload=payload,
    )

    report_path = build_servicedesk_inspection_report_path(
        workspace=workspace,
        request_id=request_id,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")

    return InspectionReportOutput(
        request_id=request_id,
        report_path=report_path,
        inspector_id=inspector_id,
        source_json_path=source_path,
    )


def render_inspection_report_markdown(
    *,
    request_id: str,
    payload: dict[str, object],
) -> str:
    inspector_id = _str(payload.get("inspector"))
    status = _str(payload.get("status")) or "unknown"
    summary = _str(payload.get("summary")) or "(no summary)"
    target = payload.get("target") or {}
    target_type = _str(target.get("type") if isinstance(target, dict) else None)
    target_id = _str(target.get("id") if isinstance(target, dict) else None)

    facts = _list_of_dicts(payload.get("facts"))
    limitations = _list_of_str(payload.get("limitations"))
    recommendations = _list_of_str(payload.get("recommendations"))
    errors = _list_of_dicts(payload.get("errors"))

    sections: list[str] = []

    sections.append(f"# Inspection report for ServiceDesk request {request_id}")
    sections.append("")
    sections.append("## Source")
    sections.append("")
    sections.append(f"- Inspector: `{inspector_id or 'unknown'}`")
    sections.append(f"- Status: `{status}`")

    if target_type or target_id:
        target_label = target_id or "(unknown)"

        if target_type:
            target_label = f"{target_type}: {target_label}"

        sections.append(f"- Target: {target_label}")

    sections.append("")
    sections.append("## Summary")
    sections.append("")
    sections.append(summary)
    sections.append("")

    sections.append("## Findings")
    sections.append("")

    largest_folders_fact: dict[str, object] | None = None

    if facts:
        for fact in facts:
            key = _str(fact.get("key")) or "(unnamed fact)"

            if key == "largest_folders":
                largest_folders_fact = fact
                continue

            value = _format_fact_value(fact.get("value"))
            sections.append(f"- **{key}**: {value}")
    else:
        sections.append("- No findings were returned by the inspector.")

    if largest_folders_fact is not None:
        folder_rows = _list_of_dicts(largest_folders_fact.get("value"))

        if folder_rows:
            sections.append("")
            sections.append("### Largest folders")
            sections.append("")
            sections.append(
                "Folder-level metadata only. Mailbox content, message "
                "subjects/bodies, and attachments were not inspected."
            )
            sections.append("")

            for folder in folder_rows:
                sections.append(_format_folder_bullet(folder))

    sections.append("")

    sections.append("## Limitations")
    sections.append("")

    if limitations:
        for limitation in limitations:
            sections.append(f"- {limitation}")
    else:
        sections.append("- No limitations were reported.")

    sections.append("")

    sections.append("## Recommendations")
    sections.append("")
    sections.append(
        "These are read-only recommendations for technician review. "
        "No changes were made to Exchange Online or to the mailbox."
    )
    sections.append("")

    if recommendations:
        for recommendation in recommendations:
            sections.append(f"- {recommendation}")
    else:
        sections.append("- No recommendations were generated from this inspection.")

    sections.append("")

    if errors:
        sections.append("## Errors")
        sections.append("")

        for error in errors:
            code = _str(error.get("code")) or "unknown"
            message = _str(error.get("message")) or "(no message)"
            recoverable = bool(error.get("recoverable"))
            recoverable_label = "recoverable" if recoverable else "not recoverable"
            sections.append(f"- `{code}` ({recoverable_label}): {message}")

        sections.append("")

    sections.append("## Suggested ticket note")
    sections.append("")
    sections.append(
        _build_suggested_note(
            status=status,
            summary=summary,
            facts=facts,
            recommendations=recommendations,
            errors=errors,
        )
    )
    sections.append("")

    sections.append("## Local-only safety notes")
    sections.append("")
    sections.append(
        "- This report was generated locally from saved inspector JSON. It was "
        "not posted to ServiceDesk."
    )
    sections.append(
        "- Mailbox content, message subjects/bodies, and attachments were not "
        "inspected."
    )
    sections.append(
        "- No authentication secrets, certificates, or raw PowerShell "
        "transcripts are included."
    )
    sections.append("")

    return "\n".join(sections)


def _load_supported_inspector_payload(
    *,
    workspace: str,
    request_id: str,
) -> tuple[str, Path, dict[str, object]]:
    output_dir = build_inspector_output_dir(
        workspace=workspace,
        request_id=request_id,
    )

    if not output_dir.exists():
        raise InspectionReportNotFoundError(
            f"No inspector results found for request {request_id}. "
            f"Run /sdp inspect-skill {request_id} first."
        )

    for inspector_id in sorted(SUPPORTED_REPORT_INSPECTOR_IDS):
        path = build_inspector_result_path(
            workspace=workspace,
            request_id=request_id,
            inspector_id=inspector_id,
        )

        if path.exists():
            payload = read_inspector_result_payload(path)

            if not isinstance(payload, dict):
                raise InspectionReportError(
                    f"Inspector result at {path} is not a JSON object."
                )

            return inspector_id, path, payload

    raise InspectionReportNotFoundError(
        f"No supported inspector results found for request {request_id}. "
        f"Run /sdp inspect-skill {request_id} first."
    )


def _build_suggested_note(
    *,
    status: str,
    summary: str,
    facts: list[dict[str, object]],
    recommendations: list[str],
    errors: list[dict[str, object]],
) -> str:
    lines: list[str] = []

    if status == "error":
        lines.append("Read-only inspection did not complete successfully.")

        if errors:
            first_error = _str(errors[0].get("message")) or summary
            lines.append(f"Reason: {first_error}")
        else:
            lines.append(f"Reason: {summary}")

        lines.append("No external systems were modified.")

        return "\n".join(lines)

    if status == "partial":
        lines.append(
            "Read-only inspection completed with partial results. "
            "The following information was gathered:"
        )
    else:
        lines.append(
            "Read-only inspection completed. The following information was gathered:"
        )

    if facts:
        for fact in facts:
            key = _str(fact.get("key"))

            if not key:
                continue

            if key == "largest_folders":
                folder_rows = _list_of_dicts(fact.get("value"))

                if folder_rows:
                    lines.append(
                        f"- largest_folders: {len(folder_rows)} folders "
                        "summarised under Largest folders in the report"
                    )

                continue

            value = _format_fact_value(fact.get("value"))
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- No facts were returned by the inspector.")

    if recommendations:
        lines.append("")
        lines.append(
            "Suggested next steps for technician review (no changes performed):"
        )

        for recommendation in recommendations:
            lines.append(f"- {recommendation}")

    lines.append("")
    lines.append(
        "No mailbox content was read and no changes were made. "
        "This note is for reference only and was not posted automatically."
    )

    return "\n".join(lines)


def _format_fact_value(value: object) -> str:
    if value is None:
        return "(none)"

    if isinstance(value, bool):
        return "yes" if value else "no"

    if isinstance(value, str):
        return value

    return str(value)


def _format_folder_bullet(folder: dict[str, object]) -> str:
    name = _str(folder.get("name"))
    folder_path = _str(folder.get("folder_path"))
    folder_size = _str(folder.get("folder_size"))
    items_in_folder = folder.get("items_in_folder")

    identifier = folder_path or name or "(unnamed folder)"
    size_label = folder_size or "unknown size"
    items_part = ""

    if isinstance(items_in_folder, int):
        items_part = f" ({items_in_folder} items)"

    return f"- `{identifier}` — {size_label}{items_part}"


def _str(value: object) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _list_of_str(value: object) -> list[str]:
    if not isinstance(value, list):
        return []

    return [str(item).strip() for item in value if str(item).strip()]


def _list_of_dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []

    return [item for item in value if isinstance(item, dict)]
