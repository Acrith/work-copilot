import argparse
import os
import sys

from dotenv import load_dotenv

from agent_runtime import run_agent
from permissions import PermissionContext, PermissionMode, load_rules
from providers.factory import (
    DEFAULT_PROVIDER,
    create_provider,
    get_default_model,
)

MAX_ITERATIONS = 20


def main():
    # Load .env so API keys can be read
    load_dotenv()

    parser = argparse.ArgumentParser(description="Chatbot")
    parser.add_argument("user_prompt", type=str, help="User prompt")
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace directory the agent can use",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument(
        "--verbose-functions",
        action="store_true",
        help="Show function calls and args",
    )
    parser.add_argument(
        "--permission-mode",
        choices=[m.value for m in PermissionMode],
        default=PermissionMode.DEFAULT.value,
        help="Permission mode for tool execution",
    )
    parser.add_argument(
        "--provider",
        default=os.environ.get("WORK_COPILOT_PROVIDER", DEFAULT_PROVIDER),
        choices=["gemini", "openai"],
        help="Model provider to use",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("WORK_COPILOT_MODEL"),
        help="Model name to use. Defaults depend on provider.",
    )
    

    args = parser.parse_args()

    workspace = os.path.abspath(args.workspace)
    if not os.path.isdir(workspace):
        raise ValueError(f"Workspace is not a directory: {args.workspace}")

    # Build the permission context used by tool_dispatch.
    permission_context = PermissionContext(
        mode=PermissionMode(args.permission_mode),
        workspace=workspace,
        rules=load_rules(workspace),
    )

    model = args.model or get_default_model(args.provider)

    # Pick the provider and model based on CLI/env settings.
    provider = create_provider(
        args.provider,
        model=model,
    )

    # Start the agent loop.
    final_text = run_agent(
        provider=provider,
        user_prompt=args.user_prompt,
        workspace=workspace,
        permission_context=permission_context,
        verbose=args.verbose,
        verbose_functions=args.verbose_functions,
        max_iterations=MAX_ITERATIONS,
    )

    if final_text is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
