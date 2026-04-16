import os
import shlex
import subprocess

from google.genai import types

from permissions import is_protected_path
from previews import normalize_tool_path


def run_shell_command(
    working_directory: str,
    command: str,
    cwd: str | None = None,
    timeout_seconds: int = 30,
) -> str:
    target_cwd = cwd or "."
    workspace, resolved_cwd = normalize_tool_path(working_directory, target_cwd)

    if timeout_seconds is None:
        timeout_seconds = 30

    if timeout_seconds <= 0:
        return "Bash error: timeout_seconds must be greater than 0."

    if os.path.commonpath([workspace, resolved_cwd]) != workspace:
        return f'Bash denied: cwd "{target_cwd}" is outside the workspace.'

    relative_cwd = os.path.relpath(resolved_cwd, workspace).replace("\\", "/")
    if relative_cwd == ".":
        relative_cwd = "."

    if is_protected_path(relative_cwd):
        return f'Bash denied: cwd "{target_cwd}" is a protected path.'

    try:
        argv = shlex.split(command)
    except ValueError as e:
        return f"Bash error: invalid command syntax: {e}"

    if not argv:
        return "Bash error: command cannot be empty."

    try:
        result = subprocess.run(
            argv,
            cwd=resolved_cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        stdout = (e.stdout or "")[:4000]
        stderr = (e.stderr or "")[:4000]
        return (
            f"Bash timed out after {timeout_seconds}s\n"
            f"Command: {command}\n"
            f"Cwd: {relative_cwd}\n"
            f"--- stdout ---\n{stdout or '(empty)'}\n"
            f"--- stderr ---\n{stderr or '(empty)'}"
        )
    except Exception as e:
        return f"Bash error: failed to run command: {e}"

    stdout = (result.stdout or "")[:4000]
    stderr = (result.stderr or "")[:4000]

    return (
        f"Bash command: {command}\n"
        f"Cwd: {relative_cwd}\n"
        f"Exit code: {result.returncode}\n"
        f"--- stdout ---\n{stdout or '(empty)'}\n"
        f"--- stderr ---\n{stderr or '(empty)'}"
    )

schema_run_shell_command = types.FunctionDeclaration(
    name="bash",
    description="Executes a shell command.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "command": types.Schema(
                type=types.Type.STRING,
                description="The shell command to execute.",
            ),
            "cwd": types.Schema(
                type=types.Type.STRING,
                description="The current working directory for the command. Defaults to the workspace root.",
                nullable=True,
            ),
            "timeout_seconds": types.Schema(
                type=types.Type.INTEGER,
                description="The maximum time in seconds to wait for the command to complete. Defaults to 30 seconds.",
                nullable=True,
            ),
        },
        required=["command"],
    ),
)