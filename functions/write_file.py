import os
from google.genai import types

def write_file(working_directory, file_path, content):
    try:
        working_file_abs = os.path.abspath(working_directory)
        target_file = os.path.normpath(os.path.join(working_file_abs, file_path))
        valid_target_file = os.path.commonpath([working_file_abs, target_file]) == working_file_abs
    
        if not valid_target_file:
            return (f"Error: Cannot write to \"{file_path}\" as it is outside the permitted working directory")

        if os.path.isdir(target_file) is True:
            return (f"Error: Cannot write to \"{file_path}\" as it is a directory")

        parent_dir = os.path.dirname(target_file)
        os.makedirs(parent_dir, exist_ok=True)

        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        return f'Successfully wrote to "{file_path}" ({len(content)} characters written)'

    except Exception as e:
        return f"Error: {e}"

schema_write_file = types.FunctionDeclaration(
    name="write_file",
    description="Write or overwrite content of a file in a specified file path relative to the working directory",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "file_path": types.Schema(
                type=types.Type.STRING,
                description="File path to access file from, relative to the working directory",
            ),
            "content": types.Schema(
                type=types.Type.STRING,
                description="File content to write or overwrite into a file"
            ),
        },
        required=["file_path", "content"],
    ),
)