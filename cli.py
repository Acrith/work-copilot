# cli.py

import argparse
import os
from collections.abc import Callable

from dotenv import load_dotenv
from rich.console import Console

from agent_runtime import run_agent
from interactive_cli import run_interactive_session
from permissions import PermissionContext, PermissionMode, load_rules
from providers.base import Provider
from providers.factory import DEFAULT_PROVIDER, create_provider, get_default_model
from run_logging import RunLogger

console = Console()

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Work Copilot")

    parser.add_argument("user_prompt", nargs="?", help="User prompt")

    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start an interactive REPL session",
    )

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
        choices=[mode.value for mode in PermissionMode],
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
        "--show-config",
        action="store_true",
        help="Print resolved configuration and exit",
    )

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(args, parser)
    return args


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.max_iterations < 1:
        parser.error("--max-iterations must be at least 1")

    if args.interactive and args.user_prompt:
        parser.error("Use either --interactive or a one-shot user_prompt, not both")

    if not args.interactive and not args.show_config and not args.user_prompt:
        parser.error("user_prompt is required unless --interactive or --show-config is used")


def resolve_workspace(workspace_arg: str) -> str:
    workspace = os.path.abspath(workspace_arg)

    if not os.path.isdir(workspace):
        raise ValueError(f"Workspace is not a directory: {workspace_arg}")

    return workspace


def build_permission_context(
    *,
    workspace: str,
    permission_mode: str,
) -> PermissionContext:
    return PermissionContext(
        mode=PermissionMode(permission_mode),
        workspace=workspace,
        rules=load_rules(workspace),
    )


def build_provider_factory(
    *,
    provider_name: str,
    model: str,
) -> Callable[[], Provider]:
    def provider_factory() -> Provider:
        return create_provider(provider_name, model=model)

    return provider_factory


def build_one_shot_run_logger(
    *,
    enabled: bool,
    log_dir: str,
    provider_name: str,
    model: str,
    workspace: str,
    permission_mode: str,
    max_iterations: int,
    user_prompt: str,
) -> RunLogger | None:
    if not enabled:
        return None

    return RunLogger(
        log_dir=log_dir,
        metadata={
            "mode": "one-shot",
            "provider": provider_name,
            "model": model,
            "workspace": workspace,
            "permission_mode": permission_mode,
            "max_iterations": max_iterations,
            "user_prompt": user_prompt,
        },
    )


def run_one_shot(
    *,
    provider_factory: Callable[[], Provider],
    provider_name: str,
    model: str,
    workspace: str,
    permission_context: PermissionContext,
    permission_mode: str,
    verbose: bool,
    verbose_functions: bool,
    max_iterations: int,
    log_run: bool,
    log_dir: str,
    user_prompt: str,
) -> int:
    run_logger = build_one_shot_run_logger(
        enabled=log_run,
        log_dir=log_dir,
        provider_name=provider_name,
        model=model,
        workspace=workspace,
        permission_mode=permission_mode,
        max_iterations=max_iterations,
        user_prompt=user_prompt,
    )

    final_text = run_agent(
        provider=provider_factory(),
        user_prompt=user_prompt,
        workspace=workspace,
        permission_context=permission_context,
        verbose=verbose,
        verbose_functions=verbose_functions,
        max_iterations=max_iterations,
        run_logger=run_logger,
    )

    if final_text is None:
        return 1

    return 0


def print_resolved_config(
    *,
    mode: str,
    provider_name: str,
    model: str,
    workspace: str,
    permission_mode: str,
    max_iterations: int,
    log_run: bool,
    log_dir: str,
) -> None:
    logging_status = "enabled" if log_run else "disabled"

    console.print("\nResolved Work Copilot config\n", style="bold")
    console.print(f"Mode:            {mode}", style="dim")
    console.print(f"Provider:        {provider_name}", style="dim")
    console.print(f"Model:           {model}", style="dim")
    console.print(f"Workspace:       {workspace}", style="dim")
    console.print(f"Permission mode: {permission_mode}", style="dim")
    console.print(f"Max iterations:  {max_iterations}", style="dim")
    console.print(f"Logging:         {logging_status}", style="dim")
    console.print(f"Log dir:         {log_dir}", style="dim")


def run_cli(argv: list[str] | None = None) -> int:
    load_dotenv()

    args = parse_args(argv)

    workspace = resolve_workspace(args.workspace)
    model = args.model or get_default_model(args.provider)
    mode = "interactive" if args.interactive else "one-shot"

    if args.show_config:
        print_resolved_config(
            mode=mode,
            provider_name=args.provider,
            model=model,
            workspace=workspace,
            permission_mode=args.permission_mode,
            max_iterations=args.max_iterations,
            log_run=args.log_run,
            log_dir=args.log_dir,
        )
        return 0

    permission_context = build_permission_context(
        workspace=workspace,
        permission_mode=args.permission_mode,
    )

    provider_factory = build_provider_factory(
        provider_name=args.provider,
        model=model,
    )

    if args.interactive:
        return run_interactive_session(
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

    return run_one_shot(
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
        user_prompt=args.user_prompt,
    )