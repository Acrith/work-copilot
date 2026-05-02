from inspectors.active_directory_group_membership import (
    ActiveDirectoryGroupMembershipSnapshot,
    MockActiveDirectoryGroupMembershipInspectorClient,
    inspect_active_directory_group_membership,
)
from inspectors.models import InspectorRequest, InspectorStatus, InspectorTarget


def _request(
    *,
    user: str | None = "user@example.com",
    group: str | None = "Engineers",
    target_id: str = "user@example.com@Engineers",
) -> InspectorRequest:
    inputs: dict[str, object] = {}

    if user is not None:
        inputs["user_principal_name"] = user

    if group is not None:
        inputs["group_name"] = group

    return InspectorRequest(
        inspector="active_directory.group_membership.inspect",
        request_id="55948",
        target=InspectorTarget(
            type="active_directory_group_membership",
            id=target_id,
            metadata={"source": "test"},
        ),
        inputs=inputs,
    )


def test_inspect_group_membership_returns_member_facts():
    client = MockActiveDirectoryGroupMembershipInspectorClient(
        {
            ("user@example.com", "Engineers"): (
                ActiveDirectoryGroupMembershipSnapshot(
                    user_identifier="user@example.com",
                    group_identifier="Engineers",
                    is_member=True,
                    membership_source="direct",
                )
            )
        }
    )

    result = inspect_active_directory_group_membership(_request(), client)

    assert result.status == InspectorStatus.OK
    facts = {fact.key: fact.value for fact in result.facts}
    assert facts["is_member"] is True
    assert facts["user_identifier"] == "user@example.com"
    assert facts["group_identifier"] == "Engineers"
    assert facts["membership_source"] == "direct"


def test_inspect_group_membership_returns_error_when_inputs_missing():
    client = MockActiveDirectoryGroupMembershipInspectorClient()

    result = inspect_active_directory_group_membership(
        _request(user=None, group=None),
        client,
    )

    assert result.status == InspectorStatus.ERROR
    assert result.errors[0].code == "missing_membership_inputs"


def test_mock_client_returns_not_member_when_pair_unknown():
    client = MockActiveDirectoryGroupMembershipInspectorClient()

    snapshot = client.get_group_membership_snapshot(
        user_identifier="user@example.com",
        group_identifier="Engineers",
    )

    assert snapshot.is_member is False
    assert snapshot.membership_source == "mock_unknown"
