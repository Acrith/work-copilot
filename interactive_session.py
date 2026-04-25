# interactive_session.py

from dataclasses import dataclass
from pathlib import Path

from agent_runtime import run_agent
from permissions import PermissionContext
from providers.base import Provider
from run_logging import RunLogger


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
    )