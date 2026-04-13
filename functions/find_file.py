import os

from google.genai import types

from constants import SKIP_DIRS


def find_file(working_directory, query):
    matches = []

    for root, dirs, files in os.walk(working_directory):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for name in files:
            if query in name:
                full_path = os.path.join(root, name)
                rel_path = os.path.relpath(full_path, working_directory)
                matches.append(rel_path)

    return "\n".join(matches) if matches else "No matching filenames found"


schema_find_file = types.FunctionDeclaration(
    name="find_file",
    description="Recursively search for filenames inside the working directory for a given text query and return the relative paths of matching files.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "query": types.Schema(
                type=types.Type.STRING,
                description="The exact text to search for in filenames.",
            ),
        },
        required=["query"],
    ),
)
