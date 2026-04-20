import os

from constants import SKIP_DIRS


def find_file(working_directory, query):
    matches = []

    for root, dirs, files in os.walk(working_directory):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for name in files:
            if query.lower() in name.lower():
                full_path = os.path.join(root, name)
                rel_path = os.path.relpath(full_path, working_directory)
                matches.append(rel_path)

    return "\n".join(matches) if matches else "No matching filenames found"
