# interactive_session.py

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from agent_runtime import run_agent
from permissions import PermissionContext
from providers.base import Provider
from run_logging import RunLogger
from runtime_events import EventSink


@dataclass(frozen=True)
class InteractiveSessionConfig:
    provider_name: str
    model: str
    workspace: str
    permission_mode: str
    verbose: bool
    verbose_functions: bool
    max_iterations: int
    log_run: bool
    log_dir: str


@dataclass
class InteractiveSessionState:
    provider: Provider
    interactive_session_id: str
    context_index: int = 1
    turn_index: int = 0


def build_interactive_session_config(
    *,
    provider_name: str,
    model: str,
    workspace: str,
    permission_mode: str,
    verbose: bool,
    verbose_functions: bool,
    max_iterations: int,
    log_run: bool,
    log_dir: str,
) -> InteractiveSessionConfig:
    return InteractiveSessionConfig(
        provider_name=provider_name,
        model=model,
        workspace=workspace,
        permission_mode=permission_mode,
        verbose=verbose,
        verbose_functions=verbose_functions,
        max_iterations=max_iterations,
        log_run=log_run,
        log_dir=log_dir,
    )


def create_interactive_session_state(
    provider_factory: Callable[[], Provider],
) -> InteractiveSessionState:
    return InteractiveSessionState(
        provider=provider_factory(),
        interactive_session_id=uuid4().hex[:12],
    )


def reset_interactive_context(
    *,
    state: InteractiveSessionState,
    provider_factory: Callable[[], Provider],
) -> None:
    state.provider = provider_factory()
    state.context_index += 1


    
def build_interactive_log_dir(log_dir: str, interactive_session_id: str) -> Path:
    return Path(log_dir) / "interactive" / interactive_session_id


def build_interactive_run_logger(
    *,
    config: InteractiveSessionConfig,
    state: InteractiveSessionState,
    user_prompt: str,
) -> RunLogger | None:
    if not config.log_run:
        return None

    interactive_log_dir = build_interactive_log_dir(
        config.log_dir,
        state.interactive_session_id,
    )
    interactive_log_dir.mkdir(parents=True, exist_ok=True)

    return RunLogger(
        log_dir=str(interactive_log_dir),
        metadata={
            "mode": "interactive",
            "interactive_session_id": state.interactive_session_id,
            "context_index": state.context_index,
            "provider": config.provider_name,
            "model": config.model,
            "workspace": config.workspace,
            "permission_mode": config.permission_mode,
            "max_iterations": config.max_iterations,
            "turn_index": state.turn_index,
            "user_prompt": user_prompt,
        },
    )


def run_interactive_model_turn(
    *,
    config: InteractiveSessionConfig,
    state: InteractiveSessionState,
    permission_context: PermissionContext,
    user_prompt: str,
    extra_event_sinks: Sequence[EventSink] | None = None,
    terminal_output: bool = True,
) -> str | None:
    state.turn_index += 1

    run_logger = build_interactive_run_logger(
        config=config,
        state=state,
        user_prompt=user_prompt,
    )

    return run_agent(
        provider=state.provider,
        user_prompt=user_prompt,
        workspace=config.workspace,
        permission_context=permission_context,
        verbose=config.verbose,
        verbose_functions=config.verbose_functions,
        max_iterations=config.max_iterations,
        run_logger=run_logger,
        extra_event_sinks=extra_event_sinks,
        terminal_output=terminal_output,
    )