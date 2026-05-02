from inspectors.active_directory_group import (
    ActiveDirectoryGroupSnapshot,
    MockActiveDirectoryGroupInspectorClient,
    inspect_active_directory_group,
)
from inspectors.active_directory_group_membership import (
    ActiveDirectoryGroupMembershipSnapshot,
    MockActiveDirectoryGroupMembershipInspectorClient,
    inspect_active_directory_group_membership,
)
from inspectors.active_directory_user import (
    ActiveDirectoryUserSnapshot,
    MockActiveDirectoryUserInspectorClient,
    inspect_active_directory_user,
)
from inspectors.exchange_mailbox import (
    ExchangeMailboxSnapshot,
    MockExchangeMailboxInspectorClient,
    inspect_exchange_mailbox,
)
from inspectors.models import InspectorRequest, InspectorResult
from inspectors.registry import InspectorRegistry


def inspect_mock_exchange_mailbox(request: InspectorRequest) -> InspectorResult:
    mailbox_address = str(request.inputs.get("mailbox_address") or request.target.id)

    client = MockExchangeMailboxInspectorClient(
        {
            mailbox_address: ExchangeMailboxSnapshot(
                mailbox_address=mailbox_address,
                display_name="Mock Mailbox User",
                primary_smtp_address=mailbox_address,
                recipient_type="UserMailbox",
                mailbox_size="mock_unknown",
                item_count=None,
                archive_status="disabled",
                auto_expanding_archive_status="not_applicable",
                retention_policy="mock_unknown",
                quota_warning_status="mock_unknown",
            )
        }
    )

    return inspect_exchange_mailbox(request, client)


def inspect_mock_active_directory_user(request: InspectorRequest) -> InspectorResult:
    user_identifier = _resolve_user_identifier(request)

    client = MockActiveDirectoryUserInspectorClient(
        {
            user_identifier: ActiveDirectoryUserSnapshot(
                user_identifier=user_identifier,
                display_name="Mock AD User",
                user_principal_name=user_identifier,
                sam_account_name="mock_user",
                mail=user_identifier,
                enabled=True,
                distinguished_name="CN=Mock AD User,OU=Users,DC=mock,DC=local",
                department="mock_unknown",
                title="mock_unknown",
                manager="mock_unknown",
            )
        }
    )

    return inspect_active_directory_user(request, client)


def inspect_mock_active_directory_group(request: InspectorRequest) -> InspectorResult:
    group_identifier = _resolve_group_identifier(request)

    client = MockActiveDirectoryGroupInspectorClient(
        {
            group_identifier: ActiveDirectoryGroupSnapshot(
                group_identifier=group_identifier,
                name=group_identifier,
                sam_account_name="mock_group",
                mail=None,
                group_scope="Global",
                group_category="Security",
                distinguished_name=(
                    f"CN={group_identifier},OU=Groups,DC=mock,DC=local"
                ),
                member_count=0,
            )
        }
    )

    return inspect_active_directory_group(request, client)


def inspect_mock_active_directory_group_membership(
    request: InspectorRequest,
) -> InspectorResult:
    user_identifier = _resolve_user_identifier(request)
    group_identifier = _resolve_group_identifier(request)

    client = MockActiveDirectoryGroupMembershipInspectorClient(
        {
            (user_identifier, group_identifier): (
                ActiveDirectoryGroupMembershipSnapshot(
                    user_identifier=user_identifier,
                    group_identifier=group_identifier,
                    is_member=False,
                    membership_source="mock_unknown",
                )
            )
        }
    )

    return inspect_active_directory_group_membership(request, client)


def create_mock_inspector_registry() -> InspectorRegistry:
    registry = InspectorRegistry()
    registry.register("exchange.mailbox.inspect", inspect_mock_exchange_mailbox)
    registry.register(
        "active_directory.user.inspect", inspect_mock_active_directory_user
    )
    registry.register(
        "active_directory.group.inspect", inspect_mock_active_directory_group
    )
    registry.register(
        "active_directory.group_membership.inspect",
        inspect_mock_active_directory_group_membership,
    )
    return registry


def _resolve_user_identifier(request: InspectorRequest) -> str:
    candidates = [
        request.inputs.get("user_principal_name"),
        request.inputs.get("sam_account_name"),
        request.inputs.get("user_identifier"),
        request.inputs.get("target_user"),
        request.inputs.get("target_user_email"),
        request.target.id,
    ]

    for candidate in candidates:
        if candidate is None:
            continue

        text = str(candidate).strip()

        if text:
            return text

    return ""


def _resolve_group_identifier(request: InspectorRequest) -> str:
    candidates = [
        request.inputs.get("group_name"),
        request.inputs.get("group_identifier"),
        request.inputs.get("sam_account_name"),
        request.inputs.get("target_group"),
        request.target.id,
    ]

    for candidate in candidates:
        if candidate is None:
            continue

        text = str(candidate).strip()

        if text:
            return text

    return ""
