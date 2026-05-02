from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from inspectors.storage import (
    build_inspector_output_dir,
    build_inspector_result_path,
    read_inspector_result_payload,
)

SUPPORTED_REPORT_INSPECTOR_IDS = {
    "exchange.mailbox.inspect",
    "active_directory.user.inspect",
    "active_directory.group.inspect",
    "active_directory.group_membership.inspect",
}


_LOGICAL_INSPECTOR_ORDER = (
    "exchange.mailbox.inspect",
    "active_directory.user.inspect",
    "active_directory.group.inspect",
    "active_directory.group_membership.inspect",
)


class InspectionReportError(Exception):
    """Raised when an inspection report cannot be built locally."""


class InspectionReportNotFoundError(InspectionReportError):
    """Raised when no supported inspector JSON exists for the request."""


@dataclass(frozen=True)
class InspectionReportInspector:
    inspector_id: str
    payload: dict[str, object]
    source_path: Path


@dataclass(frozen=True)
class InspectionReportOutput:
    request_id: str
    report_path: Path
    inspector_id: str
    source_json_path: Path
    inspectors: tuple[InspectionReportInspector, ...] = ()


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
    inspectors = _load_supported_inspector_payloads(
        workspace=workspace,
        request_id=request_id,
    )

    if len(inspectors) == 1:
        report_text = render_inspection_report_markdown(
            request_id=request_id,
            payload=inspectors[0].payload,
        )
    else:
        report_text = render_combined_inspection_report_markdown(
            request_id=request_id,
            inspectors=inspectors,
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
        inspector_id=inspectors[0].inspector_id,
        source_json_path=inspectors[0].source_path,
        inspectors=tuple(inspectors),
    )


# ---------------------- Single-payload report ----------------------------


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

    systems = _classify_systems([inspector_id])

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

    sections.extend(_findings_section_lines(facts))

    sections.extend(_limitations_section_lines(limitations))

    sections.extend(
        _recommendations_section_lines(
            recommendations=recommendations,
            systems=systems,
        )
    )

    if errors:
        sections.extend(_errors_section_lines(errors))

    sections.append("## Suggested ticket note")
    sections.append("")
    sections.append(
        _build_suggested_note(
            status=status,
            summary=summary,
            facts=facts,
            recommendations=recommendations,
            errors=errors,
            systems=systems,
        )
    )
    sections.append("")

    sections.extend(_local_only_safety_section_lines(systems))

    return "\n".join(sections)


# ---------------------- Combined multi-payload report --------------------


def render_combined_inspection_report_markdown(
    *,
    request_id: str,
    inspectors: Sequence[InspectionReportInspector],
) -> str:
    inspector_ids = [inspector.inspector_id for inspector in inspectors]
    statuses = [
        _str(inspector.payload.get("status")) or "unknown"
        for inspector in inspectors
    ]
    overall_status = _overall_status(statuses)
    systems = _classify_systems(inspector_ids)

    sections: list[str] = []

    sections.append(f"# Inspection report for ServiceDesk request {request_id}")
    sections.append("")
    sections.append("## Overview")
    sections.append("")
    sections.append(f"- Inspectors run: {len(inspectors)}")
    sections.append(f"- Overall status: `{overall_status}`")

    targets_label = _format_targets(inspectors)
    if targets_label:
        sections.append(f"- Targets: {targets_label}")

    sections.append("- Local-only: yes")
    sections.append("")

    sections.append("## Inspectors")
    sections.append("")
    for inspector in inspectors:
        inspector_status = _str(inspector.payload.get("status")) or "unknown"
        sections.append(
            f"- `{inspector.inspector_id}` — `{inspector_status}`"
        )
    sections.append("")

    for inspector in inspectors:
        sections.extend(_inspector_section_lines(inspector))

    sections.append("## Suggested ticket note")
    sections.append("")
    sections.append(
        _build_combined_suggested_note(
            inspectors=inspectors,
            overall_status=overall_status,
            systems=systems,
        )
    )
    sections.append("")

    sections.extend(_local_only_safety_section_lines(systems))

    return "\n".join(sections)


def _inspector_section_lines(
    inspector: InspectionReportInspector,
) -> list[str]:
    payload = inspector.payload

    inspector_id = _str(payload.get("inspector")) or inspector.inspector_id
    status = _str(payload.get("status")) or "unknown"
    summary = _str(payload.get("summary")) or "(no summary)"
    target = payload.get("target") or {}
    target_type = _str(target.get("type") if isinstance(target, dict) else None)
    target_id = _str(target.get("id") if isinstance(target, dict) else None)

    facts = _list_of_dicts(payload.get("facts"))
    limitations = _list_of_str(payload.get("limitations"))
    recommendations = _list_of_str(payload.get("recommendations"))
    errors = _list_of_dicts(payload.get("errors"))

    systems = _classify_systems([inspector_id])

    lines: list[str] = []

    lines.append(f"## {inspector_id}")
    lines.append("")
    lines.append("### Source")
    lines.append("")
    lines.append(f"- Inspector: `{inspector_id}`")
    lines.append(f"- Status: `{status}`")

    if target_type or target_id:
        target_label = target_id or "(unknown)"

        if target_type:
            target_label = f"{target_type}: {target_label}"

        lines.append(f"- Target: {target_label}")

    lines.append("")
    lines.append("### Summary")
    lines.append("")
    lines.append(summary)
    lines.append("")

    lines.extend(
        _findings_section_lines(facts, heading_prefix="### ")
    )

    lines.extend(
        _limitations_section_lines(limitations, heading_prefix="### ")
    )

    lines.extend(
        _recommendations_section_lines(
            recommendations=recommendations,
            systems=systems,
            heading_prefix="### ",
        )
    )

    if errors:
        lines.extend(
            _errors_section_lines(errors, heading_prefix="### ")
        )

    return lines


# ---------------------- Section helpers ----------------------------------


def _findings_section_lines(
    facts: list[dict[str, object]],
    *,
    heading_prefix: str = "## ",
) -> list[str]:
    lines: list[str] = [f"{heading_prefix}Findings", ""]

    largest_folders_fact: dict[str, object] | None = None

    if facts:
        for fact in facts:
            key = _str(fact.get("key")) or "(unnamed fact)"

            if key == "largest_folders":
                largest_folders_fact = fact
                continue

            value = _format_fact_value(fact.get("value"))
            lines.append(f"- **{key}**: {value}")
    else:
        lines.append("- No findings were returned by the inspector.")

    if largest_folders_fact is not None:
        folder_rows = _list_of_dicts(largest_folders_fact.get("value"))

        if folder_rows:
            sub_prefix = "#" + heading_prefix.strip() + " "
            lines.append("")
            lines.append(f"{sub_prefix}Largest folders")
            lines.append("")
            lines.append(
                "Folder-level metadata only. Mailbox content, message "
                "subjects/bodies, and attachments were not inspected."
            )
            lines.append("")

            for folder in folder_rows:
                lines.append(_format_folder_bullet(folder))

    lines.append("")

    return lines


def _limitations_section_lines(
    limitations: list[str],
    *,
    heading_prefix: str = "## ",
) -> list[str]:
    lines: list[str] = [f"{heading_prefix}Limitations", ""]

    if limitations:
        for limitation in limitations:
            lines.append(f"- {limitation}")
    else:
        lines.append("- No limitations were reported.")

    lines.append("")

    return lines


def _recommendations_section_lines(
    *,
    recommendations: list[str],
    systems: set[str],
    heading_prefix: str = "## ",
) -> list[str]:
    lines: list[str] = [f"{heading_prefix}Recommendations", ""]

    lines.append(_recommendations_preamble(systems))
    lines.append("")

    if recommendations:
        for recommendation in recommendations:
            lines.append(f"- {recommendation}")
    else:
        lines.append("- No recommendations were generated from this inspection.")

    lines.append("")

    return lines


def _errors_section_lines(
    errors: list[dict[str, object]],
    *,
    heading_prefix: str = "## ",
) -> list[str]:
    lines: list[str] = [f"{heading_prefix}Errors", ""]

    for error in errors:
        code = _str(error.get("code")) or "unknown"
        message = _str(error.get("message")) or "(no message)"
        recoverable = bool(error.get("recoverable"))
        recoverable_label = "recoverable" if recoverable else "not recoverable"
        lines.append(f"- `{code}` ({recoverable_label}): {message}")

    lines.append("")

    return lines


def _local_only_safety_section_lines(systems: set[str]) -> list[str]:
    lines: list[str] = ["## Local-only safety notes", ""]
    lines.append(
        "- This report was generated locally from saved inspector JSON. It was "
        "not posted to ServiceDesk."
    )

    if "exchange" in systems:
        lines.append(
            "- Mailbox content, message subjects/bodies, and attachments were "
            "not inspected."
        )

    if "active_directory" in systems:
        lines.append(
            "- Account passwords, sensitive Active Directory attributes, and "
            "membership object content beyond identifiers were not inspected."
        )

    lines.append(
        "- No authentication secrets, certificates, tokens, credential "
        "paths, or raw PowerShell transcripts are included."
    )
    lines.append("- No ServiceDesk writes performed.")
    lines.append("")

    return lines


def _recommendations_preamble(systems: set[str]) -> str:
    if systems == {"active_directory"}:
        return (
            "These are read-only recommendations for technician review. "
            "No changes were made to Active Directory."
        )

    if systems == {"exchange"}:
        return (
            "These are read-only recommendations for technician review. "
            "No changes were made to Exchange Online or to the mailbox."
        )

    return (
        "These are read-only recommendations for technician review. "
        "No changes were made by this report."
    )


# ---------------------- Suggested ticket notes ---------------------------


def _build_suggested_note(
    *,
    status: str,
    summary: str,
    facts: list[dict[str, object]],
    recommendations: list[str],
    errors: list[dict[str, object]],
    systems: set[str],
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

    lines.extend(_format_fact_lines(facts))

    if recommendations:
        lines.append("")
        lines.append(
            "Suggested next steps for technician review (no changes performed):"
        )

        for recommendation in recommendations:
            lines.append(f"- {recommendation}")

    lines.append("")
    lines.append(_no_changes_summary_line(systems))
    lines.append("This note is for reference only and was not posted automatically.")

    return "\n".join(lines)


def _build_combined_suggested_note(
    *,
    inspectors: Sequence[InspectionReportInspector],
    overall_status: str,
    systems: set[str],
) -> str:
    lines: list[str] = []

    if overall_status == "error":
        lines.append(
            "Read-only inspection did not complete successfully across all inspectors."
        )
    elif overall_status == "partial":
        lines.append(
            "Read-only inspection completed with partial results. "
            "The following information was gathered:"
        )
    else:
        lines.append(
            "Read-only inspection completed. The following information was gathered:"
        )

    aggregated_recommendations: list[str] = []

    for inspector in inspectors:
        payload = inspector.payload
        inspector_id = inspector.inspector_id
        inspector_status = _str(payload.get("status")) or "unknown"
        facts = _list_of_dicts(payload.get("facts"))
        recommendations = _list_of_str(payload.get("recommendations"))

        lines.append("")
        lines.append(f"{inspector_id} (status: {inspector_status}):")
        fact_lines = _format_fact_lines(facts)
        if fact_lines:
            lines.extend(fact_lines)
        else:
            lines.append("- No facts were returned by this inspector.")

        for recommendation in recommendations:
            aggregated_recommendations.append(
                f"[{inspector_id}] {recommendation}"
            )

    if aggregated_recommendations:
        lines.append("")
        lines.append(
            "Suggested next steps for technician review (no changes performed):"
        )
        for recommendation in aggregated_recommendations:
            lines.append(f"- {recommendation}")

    lines.append("")
    lines.append("Scope:")
    lines.append("- " + _no_changes_summary_line(systems))

    if "active_directory" in systems:
        lines.append(
            "- Sensitive Active Directory attributes were not inspected."
        )

    if "exchange" in systems:
        lines.append(
            "- Mailbox content, message subjects/bodies, and attachments were "
            "not inspected."
        )

    lines.append("- No ServiceDesk writes were performed automatically.")

    return "\n".join(lines)


def _format_fact_lines(facts: list[dict[str, object]]) -> list[str]:
    if not facts:
        return []

    lines: list[str] = []

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

    return lines


def _no_changes_summary_line(systems: set[str]) -> str:
    if systems == {"active_directory"}:
        return "No changes were made to Active Directory."

    if systems == {"exchange"}:
        return "No mailbox content was read and no changes were made."

    return "No changes were made by this inspection."


# ---------------------- Loading + classification --------------------------


def _load_supported_inspector_payloads(
    *,
    workspace: str,
    request_id: str,
) -> list[InspectionReportInspector]:
    output_dir = build_inspector_output_dir(
        workspace=workspace,
        request_id=request_id,
    )

    if not output_dir.exists():
        raise InspectionReportNotFoundError(
            f"No inspector results found for request {request_id}. "
            f"Run /sdp inspect-skill {request_id} first."
        )

    found: list[InspectionReportInspector] = []

    ordered_ids = list(_LOGICAL_INSPECTOR_ORDER) + sorted(
        SUPPORTED_REPORT_INSPECTOR_IDS - set(_LOGICAL_INSPECTOR_ORDER)
    )

    for inspector_id in ordered_ids:
        path = build_inspector_result_path(
            workspace=workspace,
            request_id=request_id,
            inspector_id=inspector_id,
        )

        if not path.exists():
            continue

        payload = read_inspector_result_payload(path)

        if not isinstance(payload, dict):
            raise InspectionReportError(
                f"Inspector result at {path} is not a JSON object."
            )

        found.append(
            InspectionReportInspector(
                inspector_id=inspector_id,
                payload=payload,
                source_path=path,
            )
        )

    if not found:
        raise InspectionReportNotFoundError(
            f"No supported inspector results found for request {request_id}. "
            f"Run /sdp inspect-skill {request_id} first."
        )

    return found


def _classify_systems(inspector_ids: list[str]) -> set[str]:
    systems: set[str] = set()

    for inspector_id in inspector_ids:
        if inspector_id.startswith("exchange."):
            systems.add("exchange")
        elif inspector_id.startswith("active_directory."):
            systems.add("active_directory")

    return systems


def _overall_status(statuses: list[str]) -> str:
    if any(s == "error" for s in statuses):
        return "error"

    if any(s == "partial" for s in statuses):
        return "partial"

    if statuses and all(s == "ok" for s in statuses):
        return "ok"

    return "unknown"


def _format_targets(
    inspectors: Sequence[InspectionReportInspector],
) -> str:
    targets: list[str] = []

    for inspector in inspectors:
        target = inspector.payload.get("target") or {}
        target_type = _str(target.get("type") if isinstance(target, dict) else None)
        target_id = _str(target.get("id") if isinstance(target, dict) else None)

        if not (target_type or target_id):
            continue

        label = target_id or "(unknown)"

        if target_type:
            label = f"{target_type}: {label}"

        targets.append(label)

    deduped: list[str] = []
    for label in targets:
        if label not in deduped:
            deduped.append(label)

    return ", ".join(deduped)


# ---------------------- Value formatting ---------------------------------


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
