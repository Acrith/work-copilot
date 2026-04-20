import os
import subprocess


def git_diff_file(working_directory: str, file_path: str) -> str:
    workspace = os.path.abspath(working_directory)
    target_file = os.path.normpath(os.path.join(workspace, file_path))

    if os.path.commonpath([workspace, target_file]) != workspace:
        return (
            f'Error: Cannot inspect diff for "{file_path}" as it is outside the '
            "permitted working directory"
        )

    try:
        repo_check = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "Error: Git command not found. Is Git installed and in PATH?"
    except Exception as e:
        return f"Error: An unexpected error occurred: {e}"

    if repo_check.returncode != 0:
        return "Error: Not a git repository."

    try:
        process = subprocess.run(
            ["git", "diff", "--", file_path],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "Error: Git command not found. Is Git installed and in PATH?"
    except Exception as e:
        return f"Error: An unexpected error occurred: {e}"

    if process.returncode != 0:
        stderr = process.stderr.strip()
        if "not a git repository" in stderr.lower():
            return "Error: Not a git repository."
        return f"Error: Git command failed: {stderr}"

    output = process.stdout.strip()
    return output if output else f'No diff for "{file_path}".'
