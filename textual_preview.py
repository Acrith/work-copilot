# textual_preview.py

from rich.text import Text


def format_preview_line(line: str) -> Text | str:
    if line.startswith("@@"):
        return Text(line, style="bold #79c0ff")

    if line.startswith("+") and not line.startswith("+++"):
        return Text(line, style="bold #7ee787")

    if line.startswith("-") and not line.startswith("---"):
        return Text(line, style="bold #ff7b72")

    if line.startswith("New file:") or line.startswith("Updated file:"):
        return Text(line, style="bold #f2cc60")

    if line.startswith("Deleted file:"):
        return Text(line, style="bold #ff7b72")

    if line.startswith("+++") or line.startswith("---"):
        return Text(line, style="#8b949e")

    return line