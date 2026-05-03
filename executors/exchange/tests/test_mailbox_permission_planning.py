import pytest

from executors import (
    ExecutorPreview,
    ExecutorRequest,
)
from executors.exchange import (
    EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID,
    EXCHANGE_GRANT_FULL_ACCESS_RIGHTS,
    SUPPORTED_SKILL_IDS,
    ExecutorPlanningResult,
    plan_exchange_grant_full_access_preview_from_skill_plan,
)
from servicedesk_skill_plan.models import (
    ExtractedInput,
    ParsedServiceDeskSkillPlan,
)


def _present(field_name: str, value: str) -> ExtractedInput:
    return ExtractedInput(
        field=field_name,
        status="present",
        value=value,
        evidence="from request body",
        needed_now="yes",
    )


def _missing(field_name: str) -> ExtractedInput:
    return ExtractedInput(
        field=field_name,
        status="missing",
        value="",
        evidence="not provided",
        needed_now="yes",
    )


def _make_plan(
    *,
    skill_match: str | None = "exchange.shared_mailbox.grant_full_access",
    extracted_inputs: list[ExtractedInput] | None = None,
) -> ParsedServiceDeskSkillPlan:
    metadata: dict[str, str] = {}
    if skill_match is not None:
        metadata["Skill match"] = skill_match
    return ParsedServiceDeskSkillPlan(
        metadata=metadata,
        extracted_inputs=list(extracted_inputs or []),
    )


# --------------------- Applicable: full preview built ------------------


def test_planner_builds_preview_when_skill_mailbox_and_trustee_present():
    plan = _make_plan(
        extracted_inputs=[
            _present("shared_mailbox_address", "shared@example.com"),
            _present("target_user", "alice@example.com"),
        ],
    )

    result = plan_exchange_grant_full_access_preview_from_skill_plan(
        plan, request_id="56050"
    )

    assert isinstance(result, ExecutorPlanningResult)
    assert result.applicable is True
    assert result.missing_inputs == []
    assert result.unsupported_reason is None

    assert isinstance(result.request, ExecutorRequest)
    assert result.request.executor_id == (
        EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID
    )
    assert result.request.inputs["mailbox"] == "shared@example.com"
    assert result.request.inputs["trustee"] == "alice@example.com"
    assert result.request.inputs["access_rights"] == (
        EXCHANGE_GRANT_FULL_ACCESS_RIGHTS
    )
    assert "auto_mapping" not in result.request.inputs

    assert isinstance(result.preview, ExecutorPreview)
    assert result.preview.requires_approval is True
    assert "shared@example.com" in result.preview.summary
    assert "alice@example.com" in result.preview.summary
    # Mock/no-op warning still present.
    assert any(
        "Mock/no-op executor" in w for w in result.preview.warnings
    )


def test_planner_threads_automapping_preference_when_present():
    plan = _make_plan(
        extracted_inputs=[
            _present("shared_mailbox_address", "shared@example.com"),
            _present("target_user", "alice@example.com"),
            _present("automapping_preference", "yes"),
        ],
    )

    result = plan_exchange_grant_full_access_preview_from_skill_plan(
        plan, request_id="56050"
    )

    assert result.applicable is True
    assert result.request is not None
    assert result.request.inputs.get("auto_mapping") is True


def test_planner_accepts_mailbox_address_alias():
    plan = _make_plan(
        extracted_inputs=[
            _present("mailbox_address", "user@example.com"),
            _present("target_user_email", "alice@example.com"),
        ],
    )

    result = plan_exchange_grant_full_access_preview_from_skill_plan(
        plan, request_id="56050"
    )

    assert result.applicable is True
    assert result.request is not None
    assert result.request.inputs["mailbox"] == "user@example.com"
    assert result.request.inputs["trustee"] == "alice@example.com"


def test_planner_accepts_executor_id_as_skill_match():
    plan = _make_plan(
        skill_match=EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID,
        extracted_inputs=[
            _present("shared_mailbox_address", "shared@example.com"),
            _present("target_user", "alice@example.com"),
        ],
    )

    result = plan_exchange_grant_full_access_preview_from_skill_plan(
        plan, request_id="56050"
    )

    assert result.applicable is True
    assert result.preview is not None


# --------------------- Applicable: missing inputs ----------------------


def test_planner_reports_missing_mailbox():
    plan = _make_plan(
        extracted_inputs=[
            _present("target_user", "alice@example.com"),
        ],
    )

    result = plan_exchange_grant_full_access_preview_from_skill_plan(
        plan, request_id="56050"
    )

    assert result.applicable is True
    assert result.preview is None
    assert result.request is None
    assert "mailbox" in result.missing_inputs
    assert "trustee" not in result.missing_inputs


def test_planner_reports_missing_trustee():
    plan = _make_plan(
        extracted_inputs=[
            _present("shared_mailbox_address", "shared@example.com"),
        ],
    )

    result = plan_exchange_grant_full_access_preview_from_skill_plan(
        plan, request_id="56050"
    )

    assert result.applicable is True
    assert result.preview is None
    assert result.request is None
    assert "trustee" in result.missing_inputs
    assert "mailbox" not in result.missing_inputs


def test_planner_reports_both_missing_when_both_absent():
    plan = _make_plan(extracted_inputs=[])

    result = plan_exchange_grant_full_access_preview_from_skill_plan(
        plan, request_id="56050"
    )

    assert result.applicable is True
    assert result.preview is None
    assert result.request is None
    assert set(result.missing_inputs) == {"mailbox", "trustee"}


def test_planner_treats_non_present_status_as_missing():
    """An ExtractedInput with status != 'present' must not be picked
    even if it has a value — the validator and inspector helpers use
    the same rule.
    """
    plan = _make_plan(
        extracted_inputs=[
            _missing("shared_mailbox_address"),
            _present("target_user", "alice@example.com"),
        ],
    )

    result = plan_exchange_grant_full_access_preview_from_skill_plan(
        plan, request_id="56050"
    )

    assert result.applicable is True
    assert result.preview is None
    assert "mailbox" in result.missing_inputs


# --------------------- Not applicable / unsupported --------------------


def test_planner_rejects_unsupported_skill():
    plan = _make_plan(
        skill_match="active_directory.user.update_profile_attributes",
        extracted_inputs=[
            _present("shared_mailbox_address", "shared@example.com"),
            _present("target_user", "alice@example.com"),
        ],
    )

    result = plan_exchange_grant_full_access_preview_from_skill_plan(
        plan, request_id="56050"
    )

    assert result.applicable is False
    assert result.preview is None
    assert result.request is None
    assert result.unsupported_reason is not None
    assert (
        "active_directory.user.update_profile_attributes"
        in result.unsupported_reason
    )


def test_planner_rejects_missing_skill_match_metadata():
    plan = _make_plan(
        skill_match=None,
        extracted_inputs=[
            _present("shared_mailbox_address", "shared@example.com"),
            _present("target_user", "alice@example.com"),
        ],
    )

    result = plan_exchange_grant_full_access_preview_from_skill_plan(
        plan, request_id="56050"
    )

    assert result.applicable is False
    assert result.preview is None
    assert result.unsupported_reason is not None
    assert "no `Skill match`" in result.unsupported_reason


def test_planner_rejects_skill_match_value_none():
    plan = _make_plan(
        skill_match="none",
        extracted_inputs=[
            _present("shared_mailbox_address", "shared@example.com"),
            _present("target_user", "alice@example.com"),
        ],
    )

    result = plan_exchange_grant_full_access_preview_from_skill_plan(
        plan, request_id="56050"
    )

    assert result.applicable is False
    assert result.unsupported_reason is not None


def test_planner_supported_skill_ids_includes_canonical_and_executor_id():
    """Lock in the supported skill list so a future regression that
    drops one of the two accepted ids fails loudly.
    """
    assert "exchange.shared_mailbox.grant_full_access" in SUPPORTED_SKILL_IDS
    assert (
        EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID in SUPPORTED_SKILL_IDS
    )


# --------------------- Preview-only contract ---------------------------


def test_planner_does_not_call_execute_handler(monkeypatch):
    """Planner must build a preview only — it must never invoke the
    executor's execute handler. Monkeypatch the execute handler to
    raise; the planner call must still succeed.
    """
    import executors.exchange.mailbox_permission as mailbox_permission_module
    import executors.exchange.planning as planning_module

    def _boom(_request):
        raise AssertionError(
            "execute handler must not be called from the planner"
        )

    monkeypatch.setattr(
        mailbox_permission_module,
        "execute_exchange_grant_full_access_mock",
        _boom,
    )
    monkeypatch.setattr(
        planning_module,
        "build_exchange_grant_full_access_request",
        planning_module.build_exchange_grant_full_access_request,
    )

    plan = _make_plan(
        extracted_inputs=[
            _present("shared_mailbox_address", "shared@example.com"),
            _present("target_user", "alice@example.com"),
        ],
    )

    result = plan_exchange_grant_full_access_preview_from_skill_plan(
        plan, request_id="56050"
    )

    assert result.applicable is True
    assert result.preview is not None
    assert result.request is not None


def test_planner_does_not_register_executor_globally():
    """Importing and using the planner must not mutate the default
    executor registry.
    """
    from executors import create_executor_registry, list_executor_ids

    plan = _make_plan(
        extracted_inputs=[
            _present("shared_mailbox_address", "shared@example.com"),
            _present("target_user", "alice@example.com"),
        ],
    )
    plan_exchange_grant_full_access_preview_from_skill_plan(
        plan, request_id="56050"
    )

    registry = create_executor_registry()
    assert list_executor_ids(registry) == []


# --------------------- Source-level safety -----------------------------


def test_planning_module_does_not_import_real_runners_or_powershell():
    """The planning module must remain pure/local: no PowerShell write
    tokens, no Exchange command runners, no ServiceDesk write
    integrations.
    """
    from pathlib import Path

    here = Path(__file__).resolve()
    planning_path = here.parents[1] / "planning.py"
    assert planning_path.is_file()
    text = planning_path.read_text(encoding="utf-8")

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
        "servicedesk_update_request",
        "servicedesk_close_request",
    ]
    for needle in forbidden:
        assert needle not in text, (
            f"planning module must not reference {needle!r}"
        )


# --------------------- Sanity check on the missing-inputs fixture ------


def test_planning_result_is_frozen():
    result = ExecutorPlanningResult(applicable=False)

    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        result.applicable = True  # type: ignore[misc]
