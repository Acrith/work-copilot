# tool_categories.py

from enum import Enum


class ToolCategory(str, Enum):
    READ = "read"
    WRITE = "write"
    EXEC = "exec"
    CONNECTOR_READ = "connector_read"
    CONNECTOR_WRITE = "connector_write"