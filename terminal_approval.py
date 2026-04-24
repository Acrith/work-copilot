from approval import ApprovalHandler, ApprovalRequest, ApprovalResponse
from console_ui import approval_prompt, print_mutation_preview


class TerminalApprovalHandler(ApprovalHandler):
    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        if request.preview is not None:
            print_mutation_preview(
                request.function_name,
                request.preview_path or "",
                request.preview,
            )

        return approval_prompt(request.function_name, request.args)
