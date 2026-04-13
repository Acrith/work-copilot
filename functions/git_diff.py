import subprocess

from google.genai import types


def git_diff(working_directory: str) -> str:
    try:
        process = subprocess.run(
            ["git", "diff"],
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
        return output if output else "No diff in repository."

    except FileNotFoundError:
        return "Error: Git command not found. Is Git installed and in PATH?"
    except Exception as e:
        return f"Error: An unexpected error occurred: {e}"


schema_git_diff = types.FunctionDeclaration(
    name="git_diff",
    description=(
        "Inspect the local git repository inside the provided workspace and "
        "return the current repository-wide git diff as a string. "
        "If there is no diff, return 'No diff in repository.' "
        "If the workspace is not a git repository, return an error string. "
        "If git is not installed, return an error string."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={},
        required=[],
    ),
)
