from collections.abc import Callable
from threading import Event

from approval import ApprovalAction, ApprovalHandler, ApprovalRequest, ApprovalResponse


class TextualApprovalHandler(ApprovalHandler):
    def __init__(
        self,
        *,
        request_callback: Callable[[ApprovalRequest, Event], None],
        response_getter: Callable[[], ApprovalResponse | None],
    ) -> None:
        self.request_callback = request_callback
        self.response_getter = response_getter

    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        approval_event = Event()

        self.request_callback(request, approval_event)
        approval_event.wait()

        response = self.response_getter()

        if response is None:
            return ApprovalResponse(
                action=ApprovalAction.DENY,
                feedback="Textual approval ended without a response.",
            )

        return response