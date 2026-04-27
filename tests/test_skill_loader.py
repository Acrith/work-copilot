from textwrap import dedent

from skills.loader import format_skill_definitions_for_prompt, load_skill_definitions


def test_load_skill_definitions_from_yaml(tmp_path):
    definition_path = tmp_path / "active_directory.create_user.yaml"
    definition_path.write_text(
        dedent(
            """
            id: active_directory.create_user
            name: Create Active Directory user
            version: 1
            status: draft_only

            description: >
              Handles requests to create a new employee/domain account.

            intents:
              - create new AD user
              - onboard employee

            required_information:
              - first_name
              - last_name
              - country

            systems:
              - Active Directory
              - Microsoft 365

            risk_level: high

            approval_requirements:
              - requester/manager authorization

            allowed_actions_now:
              - classify
              - identify_missing_information

            forbidden_actions_now:
              - create_account
              - modify_groups
            """
        ).strip(),
        encoding="utf-8",
    )

    skills = load_skill_definitions(tmp_path)

    assert len(skills) == 1

    skill = skills[0]
    assert skill.id == "active_directory.create_user"
    assert skill.name == "Create Active Directory user"
    assert skill.version == 1
    assert skill.status == "draft_only"
    assert skill.risk_level == "high"
    assert skill.intents == ["create new AD user", "onboard employee"]
    assert skill.required_information == ["first_name", "last_name", "country"]
    assert skill.systems == ["Active Directory", "Microsoft 365"]
    assert skill.approval_requirements == ["requester/manager authorization"]
    assert skill.allowed_actions_now == [
        "classify",
        "identify_missing_information",
    ]
    assert skill.forbidden_actions_now == ["create_account", "modify_groups"]


def test_format_skill_definitions_for_prompt_includes_safety_fields(tmp_path):
    definition_path = tmp_path / "m365.mailbox_permissions.yaml"
    definition_path.write_text(
        dedent(
            """
            id: m365.mailbox_permissions
            name: Change mailbox permissions
            version: 1
            status: draft_only

            description: >
              Handles requests to add, remove, or review mailbox permissions.

            intents:
              - mailbox access
              - shared mailbox permissions

            required_information:
              - mailbox
              - target_user
              - permission_type

            systems:
              - Microsoft 365
              - Exchange Online

            risk_level: medium

            approval_requirements:
              - mailbox owner approval

            allowed_actions_now:
              - classify
              - draft_internal_plan

            forbidden_actions_now:
              - modify_mailbox_permissions
            """
        ).strip(),
        encoding="utf-8",
    )

    skills = load_skill_definitions(tmp_path)
    prompt_text = format_skill_definitions_for_prompt(skills)

    assert "## m365.mailbox_permissions" in prompt_text
    assert "Name: Change mailbox permissions" in prompt_text
    assert "Status: draft_only" in prompt_text
    assert "Risk level: medium" in prompt_text
    assert "- mailbox access" in prompt_text
    assert "- permission_type" in prompt_text
    assert "- Exchange Online" in prompt_text
    assert "- mailbox owner approval" in prompt_text
    assert "- draft_internal_plan" in prompt_text
    assert "- modify_mailbox_permissions" in prompt_text