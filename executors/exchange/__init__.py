"""Mock/no-op Exchange executor definitions.

This package only contains executor definition shapes for future,
approval-gated Exchange writes. None of these executors perform any
real external write today: their execute handlers always return
`ExecutorStatus.SKIPPED` with a clear "no external write was
performed" summary.

No executor in this package is registered in the default
`create_executor_registry()`; callers that want the mock definitions
must opt in via `register_mock_exchange_executors(...)` or
`create_mock_exchange_executor_registry()`.
"""

from executors.exchange.mailbox_permission import (
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
from executors.exchange.planning import (
    SUPPORTED_SKILL_IDS,
    ExecutorPlanningResult,
    plan_exchange_grant_full_access_preview_from_skill_plan,
)

__all__ = [
    "EXCHANGE_GRANT_FULL_ACCESS_EXECUTOR_ID",
    "EXCHANGE_GRANT_FULL_ACCESS_OPERATION",
    "EXCHANGE_GRANT_FULL_ACCESS_RIGHTS",
    "ExecutorPlanningResult",
    "SUPPORTED_SKILL_IDS",
    "build_exchange_grant_full_access_preview",
    "build_exchange_grant_full_access_request",
    "create_exchange_grant_full_access_executor_definition",
    "create_mock_exchange_executor_registry",
    "execute_exchange_grant_full_access_mock",
    "plan_exchange_grant_full_access_preview_from_skill_plan",
    "register_mock_exchange_executors",
]
