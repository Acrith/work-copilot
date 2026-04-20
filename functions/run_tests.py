import os
import shutil
import subprocess


def run_tests(
    working_directory: str,
    test_path: str | None = None,
    keyword: str | None = None,
    max_failures: int | None = 1,
    quiet: bool = False,
):
    try:
        workspace = os.path.abspath(working_directory)

        cmd = ["python", "-m", "pytest"]
        if shutil.which("uv"):
            cmd = ["uv", "run"] + cmd

        if quiet:
            cmd.append("-q")

        if max_failures is not None:
            cmd.append(f"--maxfail={max_failures}")

        if keyword:
            cmd.extend(["-k", keyword])

        if test_path:
            target = os.path.normpath(os.path.join(workspace, test_path))
            if os.path.commonpath([workspace, target]) != workspace:
                return f'Error: Cannot run tests for "{test_path}" outside the permitted working directory'
            rel_target = os.path.relpath(target, workspace)
            cmd.append(rel_target)

        result = subprocess.run(cmd, cwd=workspace, capture_output=True, text=True, timeout=60)

        output = []
        output.append(f"Command: {' '.join(cmd)}")
        output.append(f"Exit code: {result.returncode}")

        if result.stdout:
            output.append(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            output.append(f"STDERR:\n{result.stderr}")
        if not result.stdout and not result.stderr:
            output.append("No output produced")

        return "\n".join(output)

    except subprocess.TimeoutExpired:
        return "Error: test run timed out after 60 seconds"
    except Exception as e:
        return f"Error: running tests: {e}"
