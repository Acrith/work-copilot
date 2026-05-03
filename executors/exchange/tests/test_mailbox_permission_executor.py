import pytest

from executors import (
    ExecutorAlreadyRegisteredError,
    ExecutorCapability,
    ExecutorDefinition,
    ExecutorPreview,
    ExecutorRequest,
    ExecutorResult,
    ExecutorStatus,
    create_executor_registry,
    list_executor_ids,
)
from executors.exchange import (
    EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID,
    EXCHANGE_GRANT_FULL_ACCESS_OPERATION,
    EXCHANGE_GRANT_FULL_ACCESS_RIGHTS,
    build_exchange_grant_full_access_preview,
    build_exchange_grant_full_access_request,
    create_exchange_grant_full_access_executor_definition,
    create_mock_exchange_executor_registry,
    execute_exchange_grant_full_access_mock,
    register_mock_exchange_executors,
)

# --------------------- Request builder ---------------------------------


def test_request_builder_returns_typed_request_with_constrained_fields():
    request = build_exchange_grant_full_access_request(
        request_id="56050",
        mailbox="shared@example.com",
        trustee="alice@example.com",
    )

    assert isinstance(request, ExecutorRequest)
    assert request.executor_id == EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID
    assert request.request_id == "56050"
    assert request.operation == EXCHANGE_GRANT_FULL_ACCESS_OPERATION
    assert request.target.type == "exchange_mailbox"
    assert request.target.id == "shared@example.com"
    assert request.target.metadata == {"source": "skill_plan"}
    assert request.source == "skill_plan"
    assert request.inputs == {
        "mailbox": "shared@example.com",
        "trustee": "alice@example.com",
        "access_rights": EXCHANGE_GRANT_FULL_ACCESS_RIGHTS,
    }


def test_request_builder_strips_whitespace_and_passes_optional_auto_mapping():
    request = build_exchange_grant_full_access_request(
        request_id="56050",
        mailbox="  shared@example.com  ",
        trustee="\talice@example.com\n",
        auto_mapping=True,
        source="manual",
        metadata={"reason": "ticket-56050"},
    )

    assert request.inputs["mailbox"] == "shared@example.com"
    assert request.inputs["trustee"] == "alice@example.com"
    assert request.inputs["auto_mapping"] is True
    assert request.source == "manual"
    assert request.target.metadata == {"source": "manual"}
    assert request.metadata == {"reason": "ticket-56050"}


def test_request_builder_rejects_missing_mailbox():
    with pytest.raises(ValueError, match="mailbox"):
        build_exchange_grant_full_access_request(
            request_id="56050",
            mailbox=None,  # type: ignore[arg-type]
            trustee="alice@example.com",
        )


def test_request_builder_rejects_blank_mailbox():
    with pytest.raises(ValueError, match="mailbox"):
        build_exchange_grant_full_access_request(
            request_id="56050",
            mailbox="   ",
            trustee="alice@example.com",
        )


def test_request_builder_rejects_missing_trustee():
    with pytest.raises(ValueError, match="trustee"):
        build_exchange_grant_full_access_request(
            request_id="56050",
            mailbox="shared@example.com",
            trustee="",
        )


def test_request_builder_rejects_blank_trustee():
    with pytest.raises(ValueError, match="trustee"):
        build_exchange_grant_full_access_request(
            request_id="56050",
            mailbox="shared@example.com",
            trustee="\t  \n",
        )


def test_request_builder_does_not_accept_arbitrary_operation_kwarg():
    """The builder constrains the operation; callers cannot inject an
    arbitrary operation name through the public signature.
    """
    with pytest.raises(TypeError):
        build_exchange_grant_full_access_request(
            request_id="56050",
            mailbox="shared@example.com",
            trustee="alice@example.com",
            operation="grant_send_as",  # type: ignore[call-arg]
        )


def test_request_builder_does_not_accept_arbitrary_access_rights_kwarg():
    with pytest.raises(TypeError):
        build_exchange_grant_full_access_request(
            request_id="56050",
            mailbox="shared@example.com",
            trustee="alice@example.com",
            access_rights="SendAs",  # type: ignore[call-arg]
        )


# --------------------- Preview handler ---------------------------------


def test_preview_returns_typed_executor_preview_with_required_fields():
    request = build_exchange_grant_full_access_request(
        request_id="56050",
        mailbox="shared@example.com",
        trustee="alice@example.com",
    )

    preview = build_exchange_grant_full_access_preview(request)

    assert isinstance(preview, ExecutorPreview)
    assert preview.executor_id == EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID
    assert preview.title == "Grant Full Access mailbox permission"
    assert preview.requires_approval is True
    assert "shared@example.com" in preview.summary
    assert "alice@example.com" in preview.summary
    assert preview.changes  # at least one change
    change = preview.changes[0]
    assert change.field == "mailbox_permission"
    assert change.before is None
    assert change.after is not None
    assert "FullAccess" in change.after
    assert "shared@example.com" in change.after
    assert "alice@example.com" in change.after


def test_preview_includes_mock_no_op_warning():
    request = build_exchange_grant_full_access_request(
        request_id="56050",
        mailbox="shared@example.com",
        trustee="alice@example.com",
    )

    preview = build_exchange_grant_full_access_preview(request)

    assert preview.warnings, "preview must surface a mock/no-op warning"
    joined = "\n".join(preview.warnings)
    assert "Mock/no-op executor" in joined
    assert "No external write will be performed." in joined


def test_preview_rejects_request_for_a_different_executor():
    base = build_exchange_grant_full_access_request(
        request_id="56050",
        mailbox="shared@example.com",
        trustee="alice@example.com",
    )
    bad = ExecutorRequest(
        executor_id="some.other.executor",
        request_id=base.request_id,
        target=base.target,
        operation=base.operation,
        inputs=dict(base.inputs),
        source=base.source,
        metadata=dict(base.metadata),
    )

    with pytest.raises(ValueError, match="different executor"):
        build_exchange_grant_full_access_preview(bad)


def test_preview_rejects_unsupported_operation():
    base = build_exchange_grant_full_access_request(
        request_id="56050",
        mailbox="shared@example.com",
        trustee="alice@example.com",
    )
    bad = ExecutorRequest(
        executor_id=base.executor_id,
        request_id=base.request_id,
        target=base.target,
        operation="grant_send_as",
        inputs=dict(base.inputs),
        source=base.source,
        metadata=dict(base.metadata),
    )

    with pytest.raises(ValueError, match="Unsupported operation"):
        build_exchange_grant_full_access_preview(bad)


def test_preview_rejects_unsupported_access_rights():
    base = build_exchange_grant_full_access_request(
        request_id="56050",
        mailbox="shared@example.com",
        trustee="alice@example.com",
    )
    bad_inputs = dict(base.inputs)
    bad_inputs["access_rights"] = "SendAs"
    bad = ExecutorRequest(
        executor_id=base.executor_id,
        request_id=base.request_id,
        target=base.target,
        operation=base.operation,
        inputs=bad_inputs,
        source=base.source,
        metadata=dict(base.metadata),
    )

    with pytest.raises(ValueError, match="Unsupported access_rights"):
        build_exchange_grant_full_access_preview(bad)


# --------------------- Execute handler ---------------------------------


def test_execute_returns_skipped_result_without_external_write():
    request = build_exchange_grant_full_access_request(
        request_id="56050",
        mailbox="shared@example.com",
        trustee="alice@example.com",
        auto_mapping=False,
    )

    result = execute_exchange_grant_full_access_mock(request)

    assert isinstance(result, ExecutorResult)
    assert result.executor_id == EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID
    assert result.status is ExecutorStatus.SKIPPED
    assert result.status is not ExecutorStatus.SUCCESS
    assert "No external write was performed" in result.summary
    assert "mock/no-op" in result.summary
    assert result.errors == []

    assert result.facts, "result should include mailbox/trustee facts"
    fact = result.facts[0]
    assert fact["mailbox"] == "shared@example.com"
    assert fact["trustee"] == "alice@example.com"
    assert fact["access_rights"] == EXCHANGE_GRANT_FULL_ACCESS_RIGHTS
    assert fact["performed"] is False
    assert fact["reason"] == "mock_no_op_executor"
    assert fact["auto_mapping"] is False

    assert result.verification_recommendations
    assert any(
        "exchange.mailbox.inspect" in line
        for line in result.verification_recommendations
    )


def test_execute_rejects_request_for_a_different_executor():
    base = build_exchange_grant_full_access_request(
        request_id="56050",
        mailbox="shared@example.com",
        trustee="alice@example.com",
    )
    bad = ExecutorRequest(
        executor_id="some.other.executor",
        request_id=base.request_id,
        target=base.target,
        operation=base.operation,
        inputs=dict(base.inputs),
        source=base.source,
        metadata=dict(base.metadata),
    )

    with pytest.raises(ValueError, match="different executor"):
        execute_exchange_grant_full_access_mock(bad)


# --------------------- Definition + registry ---------------------------


def test_definition_dispatches_through_handlers():
    definition = create_exchange_grant_full_access_executor_definition()

    assert isinstance(definition, ExecutorDefinition)
    assert definition.id == EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID
    assert (
        definition.capability
        is ExecutorCapability.EXCHANGE_MAILBOX_PERMISSION_WRITE
    )
    assert definition.requires_approval is True

    request = build_exchange_grant_full_access_request(
        request_id="56050",
        mailbox="shared@example.com",
        trustee="alice@example.com",
    )

    preview = definition.build_preview(request)
    assert preview.executor_id == EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID
    assert preview.requires_approval is True

    result = definition.execute(request)
    assert result.status is ExecutorStatus.SKIPPED


def test_default_registry_remains_empty_with_no_real_executors():
    registry = create_executor_registry()

    assert list_executor_ids(registry) == []
    assert EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID not in registry


def test_register_mock_exchange_executors_is_opt_in():
    registry = create_executor_registry()
    assert EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID not in registry

    register_mock_exchange_executors(registry)

    assert EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID in registry
    assert list_executor_ids(registry) == [
        EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID
    ]


def test_create_mock_exchange_executor_registry_returns_only_mock_executor():
    registry = create_mock_exchange_executor_registry()

    assert list_executor_ids(registry) == [
        EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID
    ]


def test_register_mock_exchange_executors_rejects_duplicate():
    registry = create_mock_exchange_executor_registry()

    with pytest.raises(ExecutorAlreadyRegisteredError):
        register_mock_exchange_executors(registry)


# --------------------- Source-level safety ----------------------------


def test_exchange_executor_source_does_not_contain_real_writes():
    """The mock executor source must not reference real PowerShell
    writes, real Exchange command runners, or ServiceDesk write
    integrations. The existing executors-package safety guard scans
    every non-test source recursively, but this focused test pins
    the boundary specifically for the new exchange/ subpackage and
    fails loudly if a future contributor moves real-write code into
    these files instead of into a separate opt-in module.
    """
    from pathlib import Path

    here = Path(__file__).resolve()
    package_dir = here.parents[1]
    sources = [
        path
        for path in package_dir.rglob("*.py")
        if "tests" not in path.parts
    ]
    assert sources, "exchange executor package should contain sources"

    forbidden = [
        "Add-MailboxPermission",
        "Remove-MailboxPermission",
        "Set-Mailbox",
        "Enable-Mailbox",
        "powershell.exe",
        "exchange_command_runner",
        "exchange_powershell_runner",
        "exchange_powershell_script",
        "servicedesk_add_request_note",
    ]

    for source_path in sources:
        text = source_path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in text, (
                f"executors/exchange must not reference {needle!r}; "
                f"found in {source_path}"
            )
