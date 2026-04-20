import os


def plan_update(working_directory, file_path, old_text, new_text):
    workspace = os.path.abspath(working_directory)
    target_file = os.path.normpath(os.path.join(workspace, file_path))

    if os.path.commonpath([workspace, target_file]) != workspace:
        return {
            "status": "error",
            "message": (
                f'Cannot update "{file_path}" as it is outside the permitted working directory'
            ),
        }

    if os.path.isdir(target_file):
        return {
            "status": "error",
            "message": f'Cannot update "{file_path}" as it is a directory',
        }

    if not os.path.isfile(target_file):
        return {
            "status": "error",
            "message": (
                f'File not found: "{file_path}". '
                "Use find_file or get_files_info to locate the correct path."
            ),
        }

    if old_text == "":
        return {
            "status": "error",
            "message": "old_text must not be empty",
        }

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            current_content = f.read()
    except Exception as e:
        return {
            "status": "error",
            "message": f'Could not read "{file_path}": {e}',
        }

    occurrences = current_content.count(old_text)

    if occurrences == 0:
        return {
            "status": "error",
            "message": (
                f'Target text not found in "{file_path}". '
                "Read the file first and retry with a more exact old_text."
            ),
        }

    if occurrences > 1:
        return {
            "status": "error",
            "message": (
                f'Found {occurrences} matches for old_text in "{file_path}". '
                "Provide a more specific old_text."
            ),
        }

    updated_content = current_content.replace(old_text, new_text, 1)

    if updated_content == current_content:
        return {
            "status": "no_change",
            "message": f'No changes to apply to "{file_path}"',
            "target_file": target_file,
            "current_content": current_content,
            "updated_content": updated_content,
        }

    return {
        "status": "ready",
        "message": f'Ready to update "{file_path}"',
        "target_file": target_file,
        "current_content": current_content,
        "updated_content": updated_content,
    }


def update_file(working_directory, file_path, old_text, new_text):
    plan = plan_update(working_directory, file_path, old_text, new_text)

    if plan["status"] == "error":
        return f"Error: {plan['message']}"

    if plan["status"] == "no_change":
        return plan["message"]

    try:
        with open(plan["target_file"], "w", encoding="utf-8") as f:
            f.write(plan["updated_content"])
    except Exception as e:
        return f'Error: Could not write "{file_path}": {e}'

    return f'Successfully updated "{file_path}"'
