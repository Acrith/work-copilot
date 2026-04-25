# main.py

import os


def configure_terminal_environment() -> None:
    """Set terminal defaults before Rich/Textual are imported."""
    os.environ.setdefault("COLORTERM", "truecolor")


def main() -> None:
    configure_terminal_environment()

    from cli import run_cli

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()