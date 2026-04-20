import subprocess


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