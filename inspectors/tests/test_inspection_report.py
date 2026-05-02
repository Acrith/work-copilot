import pytest

from inspectors.inspection_report import (
    InspectionReportNotFoundError,
    build_servicedesk_inspection_report,
    build_servicedesk_inspection_report_path,
    render_inspection_report_markdown,
)
from inspectors.models import (
    InspectorError,
    InspectorEvidence,
    InspectorFact,
    InspectorResult,
    InspectorStatus,
    InspectorTarget,
)
from inspectors.storage import save_inspector_result


def _ok_mailbox_result() -> InspectorResult:
    return InspectorResult(
        inspector="exchange.mailbox.inspect",
        target=InspectorTarget(type="mailbox", id="user@example.com"),
        status=InspectorStatus.OK,
        summary="Mailbox metadata inspected for user@example.com.",
        facts=[
            InspectorFact(key="mailbox_exists", value=True),
            InspectorFact(key="display_name", value="Example User"),
            InspectorFact(key="primary_smtp_address", value="user@example.com"),
            InspectorFact(key="recipient_type", value="UserMailbox"),
            InspectorFact(key="mailbox_size", value="136.6 MB (143,246,578 bytes)"),
            InspectorFact(key="item_count", value=12345),
            InspectorFact(key="archive_status", value="disabled"),
        ],
        evidence=[InspectorEvidence(label="mailbox_address", value="user@example.com")],
        limitations=[
            "Mailbox content not inspected",
            "No permission changes performed",
        ],
        recommendations=[
            "exchange.archive.enable may be relevant if archive is required.",
        ],
    )


def _error_mailbox_result() -> InspectorResult:
    return InspectorResult(
        inspector="exchange.mailbox.inspect",
        target=InspectorTarget(type="mailbox", id="missing@example.com"),
        status=InspectorStatus.ERROR,
        summary="Mailbox not found: missing@example.com",
        facts=[InspectorFact(key="mailbox_exists", value=False)],
        limitations=["Mailbox content not inspected"],
        errors=[
            InspectorError(
                code="mailbox_not_found",
                message="Mailbox not found: missing@example.com",
                recoverable=True,
            )
        ],
    )


def _partial_mailbox_result() -> InspectorResult:
    return InspectorResult(
        inspector="exchange.mailbox.inspect",
        target=InspectorTarget(type="mailbox", id="user@example.com"),
        status=InspectorStatus.PARTIAL,
        summary="Partial mailbox metadata inspected.",
        facts=[
            InspectorFact(key="mailbox_exists", value=True),
            InspectorFact(key="display_name", value="Example User"),
        ],
        limitations=["Mailbox statistics unavailable"],
    )


def test_build_servicedesk_inspection_report_path_uses_workspace_layout(tmp_path):
    path = build_servicedesk_inspection_report_path(
        workspace=str(tmp_path),
        request_id="55948",
    )

    assert path == (
        tmp_path / ".work_copilot" / "servicedesk" / "55948" / "inspection_report.md"
    )


def test_render_inspection_report_includes_findings_and_recommendations():
    payload = _ok_mailbox_result().to_dict()

    report = render_inspection_report_markdown(
        request_id="55948",
        payload=payload,
    )

    assert "# Inspection report for ServiceDesk request 55948" in report
    assert "## Source" in report
    assert "Inspector: `exchange.mailbox.inspect`" in report
    assert "Status: `ok`" in report
    assert "mailbox: user@example.com" in report
    assert "## Findings" in report
    assert "**display_name**: Example User" in report
    assert "**mailbox_size**: 136.6 MB (143,246,578 bytes)" in report
    assert "**item_count**: 12345" in report
    assert "**mailbox_exists**: yes" in report
    assert "## Limitations" in report
    assert "Mailbox content not inspected" in report
    assert "## Recommendations" in report
    assert (
        "These are read-only recommendations for technician review. "
        "No changes were made to Exchange Online or to the mailbox." in report
    )
    assert "exchange.archive.enable may be relevant" in report
    assert "## Suggested ticket note" in report
    assert "Read-only inspection completed" in report
    assert (
        "Suggested next steps for technician review (no changes performed):"
        in report
    )
    assert "## Local-only safety notes" in report
    assert "not posted to ServiceDesk" in report


def test_render_inspection_report_handles_error_result_honestly():
    payload = _error_mailbox_result().to_dict()

    report = render_inspection_report_markdown(
        request_id="55948",
        payload=payload,
    )

    assert "Status: `error`" in report
    assert "## Errors" in report
    assert "`mailbox_not_found`" in report
    assert "Mailbox not found: missing@example.com" in report
    assert "Read-only inspection did not complete successfully." in report
    assert "No external systems were modified." in report


def test_render_inspection_report_handles_partial_result():
    payload = _partial_mailbox_result().to_dict()

    report = render_inspection_report_markdown(
        request_id="55948",
        payload=payload,
    )

    assert "Status: `partial`" in report
    assert "Mailbox statistics unavailable" in report
    assert "Read-only inspection completed with partial results." in report
    assert "No recommendations were generated from this inspection." in report


def test_render_inspection_report_does_not_leak_sensitive_data():
    payload = _ok_mailbox_result().to_dict()

    report = render_inspection_report_markdown(
        request_id="55948",
        payload=payload,
    )

    # Auth/secret-shaped strings, raw transcripts, and mailbox content must
    # not appear because the inspector JSON does not contain them and the
    # renderer must not invent them.
    forbidden_substrings = [
        "WORK_COPILOT_EXCHANGE_CERTIFICATE",
        "CertificateThumbprint",
        "CertificatePassword",
        "Connect-ExchangeOnline",
        "Get-EXOMailboxStatistics",
        "Get-EXOMailbox -Identity",
        "FromBase64String",
        "AppId",
    ]

    for forbidden in forbidden_substrings:
        assert forbidden not in report, f"Report leaked: {forbidden}"


def test_render_inspection_report_renders_archive_readiness_recommendations():
    archive_readiness_result = InspectorResult(
        inspector="exchange.mailbox.inspect",
        target=InspectorTarget(type="mailbox", id="user@example.com"),
        status=InspectorStatus.OK,
        summary="Mailbox metadata inspected for user@example.com.",
        facts=[
            InspectorFact(key="mailbox_exists", value=True),
            InspectorFact(key="archive_status", value="disabled"),
            InspectorFact(key="quota_warning_status", value="primary_mailbox_near_quota"),
        ],
        limitations=["Mailbox content not inspected"],
        recommendations=[
            "Mailbox appears full and archive is disabled. Review whether enabling "
            "archive (exchange.archive.enable) is appropriate. No change has been made."
        ],
    )

    report = render_inspection_report_markdown(
        request_id="55948",
        payload=archive_readiness_result.to_dict(),
    )

    assert "Mailbox appears full and archive is disabled" in report
    assert "exchange.archive.enable" in report
    assert "No change has been made" in report
    assert "No changes were made to Exchange Online" in report


def test_render_inspection_report_renders_active_directory_user_payload():
    ad_user_result = InspectorResult(
        inspector="active_directory.user.inspect",
        target=InspectorTarget(
            type="active_directory_user", id="user@example.com"
        ),
        status=InspectorStatus.OK,
        summary="AD user metadata inspected for user@example.com.",
        facts=[
            InspectorFact(key="user_exists", value=True),
            InspectorFact(key="display_name", value="Example User"),
            InspectorFact(key="user_principal_name", value="user@example.com"),
            InspectorFact(key="enabled", value=True),
            InspectorFact(key="department", value="Engineering"),
        ],
        limitations=[
            "Account passwords not inspected",
            "No AD writes performed",
        ],
    )

    report = render_inspection_report_markdown(
        request_id="55948",
        payload=ad_user_result.to_dict(),
    )

    assert "Inspector: `active_directory.user.inspect`" in report
    assert "active_directory_user: user@example.com" in report
    assert "**display_name**: Example User" in report
    assert "**enabled**: yes" in report
    assert "**department**: Engineering" in report
    assert "Account passwords not inspected" in report


def test_build_servicedesk_inspection_report_writes_active_directory_user_report(tmp_path):
    save_inspector_result(
        workspace=str(tmp_path),
        request_id="55948",
        result=InspectorResult(
            inspector="active_directory.user.inspect",
            target=InspectorTarget(
                type="active_directory_user", id="user@example.com"
            ),
            status=InspectorStatus.OK,
            summary="AD user metadata inspected for user@example.com.",
            facts=[
                InspectorFact(key="user_exists", value=True),
                InspectorFact(key="display_name", value="Example User"),
            ],
            limitations=["No AD writes performed"],
        ),
    )

    output = build_servicedesk_inspection_report(
        workspace=str(tmp_path),
        request_id="55948",
    )

    assert output.inspector_id == "active_directory.user.inspect"
    assert output.report_path.exists()
    assert "Example User" in output.report_path.read_text(encoding="utf-8")


def test_render_inspection_report_renders_largest_folders_subsection():
    folder_evidence_result = InspectorResult(
        inspector="exchange.mailbox.inspect",
        target=InspectorTarget(type="mailbox", id="user@example.com"),
        status=InspectorStatus.OK,
        summary="Mailbox metadata inspected for user@example.com.",
        facts=[
            InspectorFact(key="mailbox_exists", value=True),
            InspectorFact(key="mailbox_size", value="12 GB"),
            InspectorFact(
                key="largest_folders",
                value=[
                    {
                        "name": "Inbox",
                        "folder_path": "/Inbox",
                        "folder_size": "8 GB (8,589,934,592 bytes)",
                        "items_in_folder": 4321,
                    },
                    {
                        "name": "Sent Items",
                        "folder_path": "/Sent Items",
                        "folder_size": "2 GB (2,147,483,648 bytes)",
                        "items_in_folder": 1234,
                    },
                ],
            ),
        ],
        limitations=["Mailbox content not inspected"],
    )

    report = render_inspection_report_markdown(
        request_id="55948",
        payload=folder_evidence_result.to_dict(),
    )

    assert "### Largest folders" in report
    assert (
        "Folder-level metadata only. Mailbox content, message "
        "subjects/bodies, and attachments were not inspected." in report
    )
    assert "`/Inbox` — 8 GB (8,589,934,592 bytes) (4321 items)" in report
    assert "`/Sent Items` — 2 GB (2,147,483,648 bytes) (1234 items)" in report
    # The raw fact bullet must not also appear under Findings as a stringified list.
    assert "**largest_folders**:" not in report


def test_render_inspection_report_renders_no_archive_recommendation_fallback():
    insufficient_evidence_result = InspectorResult(
        inspector="exchange.mailbox.inspect",
        target=InspectorTarget(type="mailbox", id="user@example.com"),
        status=InspectorStatus.OK,
        summary="Mailbox metadata inspected for user@example.com.",
        facts=[
            InspectorFact(key="mailbox_exists", value=True),
            InspectorFact(key="archive_status", value="disabled"),
        ],
        limitations=["Mailbox content not inspected"],
        recommendations=[
            "No archive-readiness recommendation was generated. Existing facts "
            "do not indicate a mailbox-full or archive-capacity problem. "
            "No change has been made."
        ],
    )

    report = render_inspection_report_markdown(
        request_id="55948",
        payload=insufficient_evidence_result.to_dict(),
    )

    assert "No archive-readiness recommendation was generated" in report
    assert "No change has been made" in report


def test_build_servicedesk_inspection_report_writes_file(tmp_path):
    save_inspector_result(
        workspace=str(tmp_path),
        request_id="55948",
        result=_ok_mailbox_result(),
    )

    output = build_servicedesk_inspection_report(
        workspace=str(tmp_path),
        request_id="55948",
    )

    assert output.request_id == "55948"
    assert output.inspector_id == "exchange.mailbox.inspect"
    assert output.report_path.exists()
    assert output.source_json_path.exists()
    assert output.source_json_path.name == "exchange.mailbox.inspect.json"

    report_text = output.report_path.read_text(encoding="utf-8")

    assert "# Inspection report for ServiceDesk request 55948" in report_text
    assert "## Findings" in report_text
    assert "user@example.com" in report_text


def test_build_servicedesk_inspection_report_raises_when_directory_missing(tmp_path):
    with pytest.raises(InspectionReportNotFoundError, match="Run /sdp inspect-skill"):
        build_servicedesk_inspection_report(
            workspace=str(tmp_path),
            request_id="55948",
        )


def test_build_servicedesk_inspection_report_raises_when_supported_json_missing(tmp_path):
    inspector_dir = (
        tmp_path / ".work_copilot" / "servicedesk" / "55948" / "inspectors"
    )
    inspector_dir.mkdir(parents=True)
    (inspector_dir / "active_directory.user.lookup.json").write_text(
        '{"inspector": "active_directory.user.lookup"}',
        encoding="utf-8",
    )

    with pytest.raises(
        InspectionReportNotFoundError, match="No supported inspector results"
    ):
        build_servicedesk_inspection_report(
            workspace=str(tmp_path),
            request_id="55948",
        )
