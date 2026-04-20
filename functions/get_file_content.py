import os


def get_file_content(working_directory, file_path):
    try:
        working_file_abs = os.path.abspath(working_directory)
        target_file = os.path.normpath(os.path.join(working_file_abs, file_path))
        valid_target_file = os.path.commonpath([working_file_abs, target_file]) == working_file_abs

        if valid_target_file is False:
            return (
                f'Error: Cannot read "{file_path}" as it is outside the permitted working directory'
            )

        if os.path.isfile(target_file) is False:
            return f'Error: File not found or is not a regular file: "{file_path}"'

        MAX_CHARS = 10000

        with open(target_file, "r") as f:
            file_content_string = f.read(MAX_CHARS)
            if f.read(1):
                file_content_string += (
                    f'\n\n[...File "{file_path}" truncated at {MAX_CHARS} characters]'
                )
            return file_content_string
    except Exception as e:
        return f"Error: {e}"