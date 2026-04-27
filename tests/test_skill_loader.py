from pathlib import Path
from textwrap import dedent

import pytest

from skills.loader import format_skill_definitions_for_prompt, load_skill_definitions

DEFINITIONS_DIR = Path(__file__).resolve().parents[1] / "skills" / "definitions"



def test_load_skill_definitions_from_yaml(tmp_path):
    definition_path = (
        tmp_path / "active_directory.user.provision_standard_account.yaml"
    )
    definition_path.write_text(
        dedent(
            """
            id: active_directory.user.provision_standard_account
            family: active_directory.user
            name: Provision standard Active Directory user account
            version: 1
            status: draft_only

            description: >
              Prepares a plan to provision a standard company user account.

            when_to_use:
              - Ticket asks to create a new user account
              - Ticket contains onboarding account provisioning details

            when_not_to_use:
              - Ticket is about disabling an existing account

            required_inputs:
              - name: first_name
                description: User given name
                required: true
              - name: last_name
                description: User surname
                required: true
              - name: country
                description: Country for OU mapping
                required: true

            derived_outputs:
              - ou_path
              - report_entry

            output_artifacts:
              - missing_information_checklist
              - internal_provisioning_plan

            systems:
              - Active Directory
              - Microsoft 365

            data_sensitivity:
              - personal_data
              - credentials

            execution_mode:
              current: manual
              future: approval_gated_typed_tools

            risk_level: high

            approval_requirements:
              - requester/manager authorization

            allowed_actions_now:
              - classify
              - identify_missing_information

            forbidden_actions_now:
              - create_account
              - modify_groups

            current_manual_adapter:
              type: excel_queue_and_powershell_script
              queue_file: ToCreate.xlsx

            future_tool_bindings:
              execute:
                - active_directory.user.create

            automation_readiness: partial
            """
        ).strip(),
        encoding="utf-8",
    )

    skills = load_skill_definitions(tmp_path)

    assert len(skills) == 1

    skill = skills[0]
    assert skill.id == "active_directory.user.provision_standard_account"
    assert skill.family == "active_directory.user"
    assert skill.name == "Provision standard Active Directory user account"
    assert skill.version == 1
    assert skill.status == "draft_only"
    assert skill.description.strip() == (
        "Prepares a plan to provision a standard company user account."
    )
    assert skill.when_to_use == [
        "Ticket asks to create a new user account",
        "Ticket contains onboarding account provisioning details",
    ]
    assert skill.when_not_to_use == [
        "Ticket is about disabling an existing account",
    ]
    assert [item.name for item in skill.required_inputs] == [
        "first_name",
        "last_name",
        "country",
    ]
    assert [item.description for item in skill.required_inputs] == [
        "User given name",
        "User surname",
        "Country for OU mapping",
    ]
    assert [item.required for item in skill.required_inputs] == [
        True,
        True,
        True,
    ]
    assert skill.derived_outputs == ["ou_path", "report_entry"]
    assert skill.output_artifacts == [
        "missing_information_checklist",
        "internal_provisioning_plan",
    ]
    assert skill.systems == ["Active Directory", "Microsoft 365"]
    assert skill.data_sensitivity == ["personal_data", "credentials"]
    assert skill.execution_mode == {
        "current": "manual",
        "future": "approval_gated_typed_tools",
    }
    assert skill.risk_level == "high"
    assert skill.approval_requirements == ["requester/manager authorization"]
    assert skill.allowed_actions_now == [
        "classify",
        "identify_missing_information",
    ]
    assert skill.forbidden_actions_now == ["create_account", "modify_groups"]
    assert skill.current_manual_adapter == {
        "type": "excel_queue_and_powershell_script",
        "queue_file": "ToCreate.xlsx",
    }
    assert skill.future_tool_bindings == {
        "execute": ["active_directory.user.create"],
    }
    assert skill.automation_readiness == "partial"
    assert skill.intents == []
    assert skill.required_information == []


def test_format_skill_definitions_for_prompt_includes_richer_schema(tmp_path):
    definition_path = tmp_path / "exchange.shared_mailbox.grant_full_access.yaml"
    definition_path.write_text(
        dedent(
            """
            id: exchange.shared_mailbox.grant_full_access
            family: exchange.shared_mailbox
            name: Grant shared mailbox Full Access
            version: 2
            status: draft_only

            description: >
              Prepares a plan to grant Full Access permissions to a shared mailbox.

            when_to_use:
              - shared mailbox full access
              - add user to shared mailbox

            when_not_to_use:
              - mailbox creation
              - mailbox quota troubleshooting

            required_inputs:
              - name: mailbox_address
                description: Shared mailbox address
                required: true
              - name: target_user
                description: User who should receive access
                required: true
              - name: approval_status
                description: Whether mailbox owner approval is present
                required: true

            derived_outputs:
              - approval_description

            output_artifacts:
              - requester_reply_draft
              - internal_permission_plan

            systems:
              - Microsoft 365
              - Exchange Online

            data_sensitivity:
              - personal_data
              - access_rights

            execution_mode:
              current: manual
              future: approval_gated_typed_tools

            risk_level: high

            approval_requirements:
              - mailbox owner approval
              - target user confirmation

            allowed_actions_now:
              - classify
              - draft_internal_plan

            forbidden_actions_now:
              - grant_full_access
              - modify_mailbox_permissions

            current_manual_adapter:
              type: manual_exchange_admin_center_or_powershell

            future_tool_bindings:
              inspect:
                - exchange.shared_mailbox.permissions.inspect
              execute:
                - exchange.shared_mailbox.grant_full_access

            automation_readiness: partial
            """
        ).strip(),
        encoding="utf-8",
    )

    skills = load_skill_definitions(tmp_path)
    prompt_text = format_skill_definitions_for_prompt(skills)

    assert "## exchange.shared_mailbox.grant_full_access" in prompt_text
    assert "Family: exchange.shared_mailbox" in prompt_text
    assert "Name: Grant shared mailbox Full Access" in prompt_text
    assert "Version: 2" in prompt_text
    assert "Status: draft_only" in prompt_text
    assert "Risk level: high" in prompt_text
    assert "Description:" in prompt_text
    assert "Prepares a plan to grant Full Access permissions" in prompt_text
    assert "When to use:" in prompt_text
    assert "- shared mailbox full access" in prompt_text
    assert "When not to use:" in prompt_text
    assert "- mailbox quota troubleshooting" in prompt_text
    assert "Required inputs:" in prompt_text
    assert (
        "- mailbox_address: Shared mailbox address (required: true)"
        in prompt_text
    )
    assert (
        "- target_user: User who should receive access (required: true)"
        in prompt_text
    )
    assert "Derived outputs:" in prompt_text
    assert "- approval_description" in prompt_text
    assert "Output artifacts:" in prompt_text
    assert "- requester_reply_draft" in prompt_text
    assert "Systems:" in prompt_text
    assert "- Exchange Online" in prompt_text
    assert "Data sensitivity:" in prompt_text
    assert "- access_rights" in prompt_text
    assert "Execution mode:" in prompt_text
    assert "- current: manual" in prompt_text
    assert "- future: approval_gated_typed_tools" in prompt_text
    assert "Approval requirements:" in prompt_text
    assert "- mailbox owner approval" in prompt_text
    assert "Allowed actions now:" in prompt_text
    assert "- draft_internal_plan" in prompt_text
    assert "Forbidden actions now:" in prompt_text
    assert "- grant_full_access" in prompt_text
    assert "Current manual adapter:" in prompt_text
    assert "- type: manual_exchange_admin_center_or_powershell" in prompt_text
    assert "Future tool bindings:" in prompt_text
    assert "- inspect:" in prompt_text
    assert "exchange.shared_mailbox.permissions.inspect" in prompt_text
    assert "exchange.shared_mailbox.grant_full_access" in prompt_text
    assert "Automation readiness:" in prompt_text
    assert "- partial" in prompt_text


def test_load_skill_definitions_rejects_non_mapping(tmp_path):
    definition_path = tmp_path / "bad.yaml"
    definition_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a mapping"):
        load_skill_definitions(tmp_path)


def test_load_skill_definitions_rejects_missing_required_fields(tmp_path):
    definition_path = tmp_path / "missing_name.yaml"
    definition_path.write_text(
        dedent(
            """
            id: missing_name
            version: 1
            status: draft_only
            """
        ).strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required field 'name'"):
        load_skill_definitions(tmp_path)


def test_builtin_skill_definitions_are_draft_only_and_well_formed():
    skills = load_skill_definitions(DEFINITIONS_DIR)

    for skill in skills:
        assert skill.id
        assert skill.name
        assert skill.status == "draft_only"
        assert skill.when_to_use
        assert skill.when_not_to_use
        assert skill.required_inputs
        assert skill.systems
        assert skill.risk_level
        assert skill.allowed_actions_now
        assert skill.forbidden_actions_now
        assert skill.automation_readiness is not None

        forbidden_actions_text = " ".join(skill.forbidden_actions_now)
        assert forbidden_actions_text