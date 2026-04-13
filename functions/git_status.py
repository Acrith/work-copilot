import subprocess

from google.genai import types


def git_status(working_directory: str) -> str:
    try:
        process = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=working_directory,
            capture_output=True,
            text=True,
            check=False,
        )

        if process.returncode != 0:
            stderr = process.stderr.strip()

            if "not a git repository" in stderr.lower():
                return "Error: Not a git repository."

            return f"Error: Git command failed: {stderr}"

        output = process.stdout.strip()
        return output if output else "Git repository is clean."

    except FileNotFoundError:
        return "Error: Git command not found. Is Git installed and in PATH?"
    except Exception as e:
        return f"Error: An unexpected error occurred: {e}"


schema_git_status = types.FunctionDeclaration(
    name="git_status",
    description=(
        "Inspect the git repository in the workspace and return a compact "
        "human-readable summary of repository status."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={},
        required=[],
    ),
)