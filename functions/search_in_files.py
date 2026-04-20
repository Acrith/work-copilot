import os

from constants import SKIP_DIRS


def search_in_files(working_directory, query):
    matches = []

    for root, dirs, files in os.walk(working_directory):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for name in files:
            full_path = os.path.join(root, name)
            rel_path = os.path.relpath(full_path, working_directory)

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except (UnicodeDecodeError, OSError):
                continue

            if query in content:
                matches.append(rel_path)

    return "\n".join(matches) if matches else "No matches found"