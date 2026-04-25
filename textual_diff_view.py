# textual_diff_view.py

from textual.containers import VerticalScroll
from textual.widgets import Static

from textual_diff_renderer import build_approval_preview_rows


class DiffPreview(VerticalScroll):
    DEFAULT_CSS = """
    DiffPreview {
        height: 1fr;
        border: solid #2b3a4a;
        background: #0d1117;
        padding: 1 2;
    }

    DiffPreview .diff-row {
        width: 100%;
        height: 1;
        min-height: 1;
    }

    DiffPreview .diff-row.title {
        color: #88c0d0;
        text-style: bold;
    }

    DiffPreview .diff-row.empty {
        height: 1;
    }

    DiffPreview .diff-row.muted {
        color: #7f8ea3;
    }

    DiffPreview .diff-row.added {
        background: #0f2a18;
        color: #d7ffe0;
    }

    DiffPreview .diff-row.removed {
        background: #2a1414;
        color: #ffd7d7;
    }

    DiffPreview .diff-row.hunk {
        background: #111d2e;
        color: #79c0ff;
        text-style: bold;
    }

    DiffPreview .diff-row.column-header {
        color: #8b949e;
        text-style: bold;
    }

    DiffPreview .diff-row.file-header {
        color: #c9d1d9;
        text-style: bold;
    }

    DiffPreview .diff-row.separator {
        color: #30363d;
    }
    """

    def render_preview(self, *, preview: str | None, preview_path: str | None) -> None:
        self.remove_children()

        for row in build_approval_preview_rows(
            preview=preview,
            preview_path=preview_path,
        ):
            self.mount(
                Static(
                    row.content,
                    classes=f"diff-row {row.css_class}",
                )
            )