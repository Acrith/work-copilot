import os
import subprocess
from google.genai import types

def run_python_file(working_directory, file_path, args=None):
    try:
        working_file_abs = os.path.abspath(working_directory)
        target_file = os.path.normpath(os.path.join(working_file_abs, file_path))
        valid_target_file = os.path.commonpath([working_file_abs, target_file]) == working_file_abs
    
        if not valid_target_file:
            return (f"Error: Cannot execute \"{file_path}\" as it is outside the permitted working directory")

        if os.path.isfile(target_file) is False:
            return (f"Error: \"{file_path}\" does not exist or is not a regular file")

        if not target_file.endswith('.py'):
            return (f"Error: \"{file_path}\" is not a Python file")

        command = ["python", target_file]
        if args:
            command.extend(args)
        result = subprocess.run(command, cwd=working_file_abs, capture_output=True, timeout=30, text=True)

        output = []
        if result.returncode != 0:
            output.append(f"Process exited with code {result.returncode}")
        if not result.stdout and not result.stderr:
            output.append(f"No output produced")
        if result.stdout:
            output.append(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            output.append(f"STDERR:\n{result.stderr}")
        return "\n".join(output)

    except Exception as e:
        return f"Error: executing Python file: {e}"

schema_run_python_file = types.FunctionDeclaration(
    name="run_python_file",
    description="Executes a Python file in a specified file path relative to the working directory with optional arguments",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="File path to access file from, relative to the working directory",
            ),
            "args": types.Schema(
                type=types.Type.ARRAY,
                description="List of arguments to run Python file with",
                items=types.Schema(
                    type=types.Type.STRING,
                ),
            )
        },
        required=["file_path"],
    ),
)