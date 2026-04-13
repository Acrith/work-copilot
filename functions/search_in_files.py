import os

from google.genai import types

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


schema_search_in_files = types.FunctionDeclaration(
    name="search_in_files",
    description="Recursively search text files inside the working directory for a given text query and return the relative paths of matching files.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "query": types.Schema(
                type=types.Type.STRING,
                description="The exact text to search for in file contents.",
            ),
        },
        required=["query"],
    ),
)
