import argparse
import os
import sys

from dotenv import load_dotenv

from agent_runtime import run_agent
from interactive_cli import run_interactive_session
from permissions import PermissionContext, PermissionMode, load_rules
from providers.factory import (
    DEFAULT_PROVIDER,
    create_provider,
    get_default_model,
)
from run_logging import RunLogger


def main():
    # Load .env so API keys can be read
    load_dotenv()

    parser = argparse.ArgumentParser(description="Chatbot")
    parser.add_argument("user_prompt", nargs="?", help="User prompt")
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
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=20,
        help="Maximum number of model/tool loop iterations before stopping",
    )
    parser.add_argument(
        "--log-run",
        action="store_true",
        help="Save this run to a JSON log file",
    )

    parser.add_argument(
        "--log-dir",
        default=".work_copilot/runs",
        help="Directory for run logs when --log-run is enabled",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start an interactive REPL session",
    )

    args = parser.parse_args()
    if args.max_iterations < 1:
        raise ValueError("--max-iterations must be at least 1")

    if args.interactive and args.user_prompt:
        parser.error("Use either --interactive or a one-shot user_prompt, not both")

    if not args.interactive and not args.user_prompt:
        parser.error("user_prompt is required unless --interactive is used")

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

    def provider_factory():
        return create_provider(
            args.provider,
            model=model,
        )


    if args.interactive:
        exit_code = run_interactive_session(
            provider_factory=provider_factory,
            provider_name=args.provider,
            model=model,
            workspace=workspace,
            permission_context=permission_context,
            permission_mode=args.permission_mode,
            verbose=args.verbose,
            verbose_functions=args.verbose_functions,
            max_iterations=args.max_iterations,
            log_run=args.log_run,
            log_dir=args.log_dir,
        )
        sys.exit(exit_code)

    # Create logger if --log-run
    run_logger = None
    if args.log_run:
        run_logger = RunLogger(
            log_dir=args.log_dir,
            metadata={
                "provider": args.provider,
                "model": model,
                "workspace": workspace,
                "permission_mode": args.permission_mode,
                "max_iterations": args.max_iterations,
                "user_prompt": args.user_prompt,
            },
        )

    # Pick the provider and model based on CLI/env settings.
    provider = provider_factory()

    # Start the agent loop.
    final_text = run_agent(
        provider=provider,
        user_prompt=args.user_prompt,
        workspace=workspace,
        permission_context=permission_context,
        verbose=args.verbose,
        verbose_functions=args.verbose_functions,
        max_iterations=args.max_iterations,
        run_logger=run_logger,
    )

    if final_text is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
