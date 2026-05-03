import pytest

from executors import (
    ExecutorAlreadyRegisteredError,
    ExecutorCapability,
    ExecutorChange,
    ExecutorDefinition,
    ExecutorError,
    ExecutorNotFoundError,
    ExecutorPreview,
    ExecutorRegistry,
    ExecutorRequest,
    ExecutorResult,
    ExecutorStatus,
    ExecutorTarget,
    create_executor_registry,
    get_executor,
    list_executor_ids,
    register_executor,
)


def _stub_request(executor_id: str = "stub.executor") -> ExecutorRequest:
    return ExecutorRequest(
        executor_id=executor_id,
        request_id="56050",
        target=ExecutorTarget(type="stub", id="stub-target"),
        operation="stub.operation",
        inputs={"k": "v"},
    )


def _stub_preview_handler(request: ExecutorRequest) -> ExecutorPreview:
    return ExecutorPreview(
        executor_id=request.executor_id,
        title="Stub preview",
        summary="Stub preview summary",
        changes=[
            ExecutorChange(
                field="example_field",
                before="old",
                after="new",
                description="example change",
            )
        ],
    )


def _stub_execute_handler(request: ExecutorRequest) -> ExecutorResult:
    return ExecutorResult(
        executor_id=request.executor_id,
        status=ExecutorStatus.SUCCESS,
        summary="Stub execution succeeded",
        verification_recommendations=[
            "Re-run the corresponding inspector to confirm.",
        ],
    )


def _stub_definition(
    executor_id: str = "stub.executor",
) -> ExecutorDefinition:
    return ExecutorDefinition(
        id=executor_id,
        description="Test stub executor (no real backend).",
        capability=ExecutorCapability.ACTIVE_DIRECTORY_USER_WRITE,
        preview_handler=_stub_preview_handler,
        execute_handler=_stub_execute_handler,
    )


# --------------------- Default registry shape --------------------------


def test_default_registry_has_no_real_executors():
    registry = create_executor_registry()

    assert isinstance(registry, ExecutorRegistry)
    assert list_executor_ids(registry) == []
    assert len(registry) == 0


# --------------------- Register / retrieve ----------------------------


def test_register_and_retrieve_executor_definition():
    registry = create_executor_registry()
    definition = _stub_definition()

    register_executor(registry, definition)

    assert "stub.executor" in registry
    assert list_executor_ids(registry) == ["stub.executor"]
    assert get_executor(registry, "stub.executor") is definition
    assert registry.require("stub.executor") is definition


def test_register_duplicate_executor_id_is_rejected():
    registry = create_executor_registry()
    register_executor(registry, _stub_definition())

    with pytest.raises(ExecutorAlreadyRegisteredError):
        register_executor(registry, _stub_definition())


def test_get_missing_executor_returns_none():
    registry = create_executor_registry()

    assert get_executor(registry, "no.such.executor") is None


def test_require_missing_executor_raises_clear_error():
    registry = create_executor_registry()

    with pytest.raises(ExecutorNotFoundError) as excinfo:
        registry.require("no.such.executor")
    assert "no.such.executor" in str(excinfo.value)


def test_list_executor_ids_returns_sorted_ids():
    registry = create_executor_registry()
    register_executor(registry, _stub_definition("a.first"))
    register_executor(registry, _stub_definition("c.third"))
    register_executor(registry, _stub_definition("b.second"))

    assert list_executor_ids(registry) == ["a.first", "b.second", "c.third"]


# --------------------- Preview / result models ------------------------


def test_executor_preview_defaults_require_approval_true():
    preview = ExecutorPreview(
        executor_id="stub.executor",
        title="t",
        summary="s",
    )

    assert preview.requires_approval is True
    assert preview.changes == []
    assert preview.warnings == []


def test_executor_preview_cannot_be_constructed_without_requiring_approval():
    """`requires_approval` is a read-only property on ExecutorPreview,
    not an init field. A caller (or a future UI layer that trusts the
    value) must not be able to construct a preview that opts out of
    approval.
    """
    # Passing `requires_approval=` as a kwarg must raise because it is
    # no longer an init field — the structural guarantee is enforced
    # at construction time, not by convention.
    with pytest.raises(TypeError):
        ExecutorPreview(
            executor_id="stub.executor",
            title="t",
            summary="s",
            requires_approval=False,
        )

    # And a normally-constructed preview always reports True.
    default_preview = ExecutorPreview(
        executor_id="stub.executor",
        title="t",
        summary="s",
    )
    assert default_preview.requires_approval is True


def test_executor_definition_requires_approval_property_is_true():
    definition = _stub_definition()

    # The property is True for every definition; subclasses or
    # instances cannot set it to False because it is computed.
    assert definition.requires_approval is True


def test_executor_result_supports_success_status():
    result = ExecutorResult(
        executor_id="stub.executor",
        status=ExecutorStatus.SUCCESS,
        summary="ok",
    )

    assert result.status is ExecutorStatus.SUCCESS
    assert result.errors == []
    assert result.facts == []
    assert result.verification_recommendations == []


def test_executor_result_supports_failed_status_with_errors():
    result = ExecutorResult(
        executor_id="stub.executor",
        status=ExecutorStatus.FAILED,
        summary="boom",
        errors=[
            ExecutorError(
                code="permission_denied",
                message="Missing privilege.",
                recoverable=False,
            ),
        ],
    )

    assert result.status is ExecutorStatus.FAILED
    assert len(result.errors) == 1
    assert result.errors[0].code == "permission_denied"
    assert result.errors[0].recoverable is False


def test_executor_result_supports_skipped_status():
    result = ExecutorResult(
        executor_id="stub.executor",
        status=ExecutorStatus.SKIPPED,
        summary="not approved",
    )

    assert result.status is ExecutorStatus.SKIPPED


# --------------------- Definition handlers ----------------------------


def test_executor_definition_dispatches_preview_and_execute():
    definition = _stub_definition()
    request = _stub_request()

    preview = definition.build_preview(request)
    assert preview.executor_id == "stub.executor"
    assert preview.title == "Stub preview"
    assert preview.requires_approval is True

    result = definition.execute(request)
    assert result.executor_id == "stub.executor"
    assert result.status is ExecutorStatus.SUCCESS
    assert result.verification_recommendations == [
        "Re-run the corresponding inspector to confirm.",
    ]


# --------------------- Source-level safety guard ----------------------


def test_executors_package_contains_no_powershell_writes_or_servicedesk_writes():
    """Source-level guard: the executors scaffold must not contain any
    real PowerShell write commands, ServiceDesk write integration, or
    AD/Exchange write helpers. Real backends will be added in later
    opt-in PRs; this PR is types/registry only.
    """
    from pathlib import Path

    package_dir = Path(__file__).resolve().parents[1]
    # Only scan non-test sources. Test files (in any `tests/`
    # directory under the package, including subpackage tests) list
    # the forbidden tokens as string literals so the assertion can
    # run.
    sources = [
        path
        for path in package_dir.rglob("*.py")
        if "tests" not in path.parts
    ]
    assert sources, "executors package should contain source files"

    forbidden = [
        "Add-MailboxPermission",
        "Remove-MailboxPermission",
        "Set-Mailbox",
        "Enable-Mailbox",
        "Set-ADUser",
        "New-ADUser",
        "Remove-ADUser",
        "Add-ADGroupMember",
        "Remove-ADGroupMember",
        "servicedesk_add_request_note",
        "servicedesk_update_request",
        "servicedesk_close_request",
        "powershell.exe",
        "exchange_command_runner",
        "active_directory_command_runner",
    ]

    for source_path in sources:
        text = source_path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in text, (
                f"executors scaffold must not reference {needle!r}; "
                f"found in {source_path}"
            )
