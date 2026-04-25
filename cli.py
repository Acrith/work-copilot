# cli.py

import argparse
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv
from rich.console import Console

from agent_runtime import run_agent
from interactive_cli import run_interactive_session
from interactive_session import build_interactive_session_config
from permissions import PermissionContext, PermissionMode, load_rules
from providers.base import Provider
from providers.factory import DEFAULT_PROVIDER, create_provider, get_default_model
from run_logging import RunLogger
from textual_app import WorkCopilotTextualApp

console = Console()
CliMode = Literal["one-shot", "interactive", "tui"]


@dataclass(frozen=True)
class CliConfig:
    mode: CliMode
    provider_name: str
    model: str
    workspace: str
    permission_mode: str
    verbose: bool
    verbose_functions: bool
    max_iterations: int
    log_run: bool
    log_dir: str
    show_config: bool
    user_prompt: str | None


def build_cli_config(args: argparse.Namespace) -> CliConfig:
    workspace = resolve_workspace(args.workspace)
    model = args.model or get_default_model(args.provider)
    if args.tui:
        mode: CliMode = "tui"
    elif args.interactive:
        mode = "interactive"
    else:
        mode = "one-shot"

    return CliConfig(
        mode=mode,
        provider_name=args.provider,
        model=model,
        workspace=workspace,
        permission_mode=args.permission_mode,
        verbose=args.verbose,
        verbose_functions=args.verbose_functions,
        max_iterations=args.max_iterations,
        log_run=args.log_run,
        log_dir=args.log_dir,
        show_config=args.show_config,
        user_prompt=args.user_prompt,
    )


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

    parser.add_argument(
       "--tui",
        action="store_true",
        help="Start the experimental Textual TUI",
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

    if args.interactive and args.tui:
        parser.error("Use either --interactive or --tui, not both")

    if args.user_prompt and (args.interactive or args.tui):
        parser.error("Use either a session mode or a one-shot user_prompt, not both")

    if (
        not args.interactive
        and not args.tui
        and not args.show_config
        and not args.user_prompt
    ):
        parser.error(
            "user_prompt is required unless --interactive, --tui, or --show-config is used"
        )


def resolve_workspace(workspace_arg: str) -> str:
    workspace = os.path.abspath(workspace_arg)

    if not os.path.isdir(workspace):
        raise ValueError(f"Workspace is not a directory: {workspace_arg}")

    return workspace


def build_permission_context(config: CliConfig) -> PermissionContext:
    return PermissionContext(
        mode=PermissionMode(config.permission_mode),
        workspace=config.workspace,
        rules=load_rules(config.workspace),
    )


def build_provider_factory(config: CliConfig) -> Callable[[], Provider]:
    def provider_factory() -> Provider:
        return create_provider(config.provider_name, model=config.model)

    return provider_factory


def build_one_shot_run_logger(config: CliConfig) -> RunLogger | None:
    if not config.log_run:
        return None

    return RunLogger(
        log_dir=config.log_dir,
        metadata={
            "mode": config.mode,
            "provider": config.provider_name,
            "model": config.model,
            "workspace": config.workspace,
            "permission_mode": config.permission_mode,
            "max_iterations": config.max_iterations,
            "user_prompt": config.user_prompt,
        },
    )


def run_tui(
    *,
    config: CliConfig,
    provider_factory: Callable[[], Provider],
    permission_context: PermissionContext,
) -> int:
    interactive_config = build_interactive_session_config(
        provider_name=config.provider_name,
        model=config.model,
        workspace=config.workspace,
        permission_mode=config.permission_mode,
        verbose=config.verbose,
        verbose_functions=config.verbose_functions,
        max_iterations=config.max_iterations,
        log_run=config.log_run,
        log_dir=config.log_dir,
    )

    app = WorkCopilotTextualApp(
        config=interactive_config,
        provider_factory=provider_factory,
        permission_context=permission_context,
    )
    app.run()

    return 0


def run_one_shot(
    *,
    config: CliConfig,
    provider_factory: Callable[[], Provider],
    permission_context: PermissionContext,
) -> int:
    if config.user_prompt is None:
        raise ValueError("user_prompt is required for one-shot mode")

    run_logger = build_one_shot_run_logger(config)

    final_text = run_agent(
        provider=provider_factory(),
        user_prompt=config.user_prompt,
        workspace=config.workspace,
        permission_context=permission_context,
        verbose=config.verbose,
        verbose_functions=config.verbose_functions,
        max_iterations=config.max_iterations,
        run_logger=run_logger,
    )

    if final_text is None:
        return 1

    return 0


def print_resolved_config(config: CliConfig) -> None:
    logging_status = "enabled" if config.log_run else "disabled"

    console.print("\nResolved Work Copilot config\n", style="bold")
    console.print(f"Mode:            {config.mode}", style="dim")
    console.print(f"Provider:        {config.provider_name}", style="dim")
    console.print(f"Model:           {config.model}", style="dim")
    console.print(f"Workspace:       {config.workspace}", style="dim")
    console.print(f"Permission mode: {config.permission_mode}", style="dim")
    console.print(f"Max iterations:  {config.max_iterations}", style="dim")
    console.print(f"Logging:         {logging_status}", style="dim")
    console.print(f"Log dir:         {config.log_dir}", style="dim")


def run_cli(argv: list[str] | None = None) -> int:
    load_dotenv()

    args = parse_args(argv)
    config = build_cli_config(args)

    if config.show_config:
        print_resolved_config(config)
        return 0

    permission_context = build_permission_context(config)
    provider_factory = build_provider_factory(config)

    if config.mode == "tui":
        return run_tui(
            config=config,
            provider_factory=provider_factory,
            permission_context=permission_context,
        )

    if config.mode == "interactive":
        return run_interactive_session(
            provider_factory=provider_factory,
            provider_name=config.provider_name,
            model=config.model,
            workspace=config.workspace,
            permission_context=permission_context,
            permission_mode=config.permission_mode,
            verbose=config.verbose,
            verbose_functions=config.verbose_functions,
            max_iterations=config.max_iterations,
            log_run=config.log_run,
            log_dir=config.log_dir,
        )

    return run_one_shot(
        config=config,
        provider_factory=provider_factory,
        permission_context=permission_context,
    )