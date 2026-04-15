CORE_INTERNAL_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
}

CACHE_DIRS = {
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

LARGE_GENERATED_DIRS = {
    "node_modules",
}

SENSITIVE_FILES = {
    ".env",
    ".work_copilot.json",
}

SKIP_DIRS = CORE_INTERNAL_DIRS | CACHE_DIRS | LARGE_GENERATED_DIRS
PROTECTED_PATHS = CORE_INTERNAL_DIRS | SENSITIVE_FILES