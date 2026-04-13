from previews import format_diff_for_terminal, is_unified_diff_preview


class TermStyle:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"


def styled(text: str, *styles: str) -> str:
    if not styles:
        return text
    return f"{''.join(styles)}{text}{TermStyle.RESET}"


def bold(text: str) -> str:
    return styled(text, TermStyle.BOLD)


def dim(text: str) -> str:
    return styled(text, TermStyle.DIM)


def red(text: str) -> str:
    return styled(text, TermStyle.RED)


def green(text: str) -> str:
    return styled(text, TermStyle.GREEN)


def yellow(text: str) -> str:
    return styled(text, TermStyle.YELLOW)


def cyan(text: str) -> str:
    return styled(text, TermStyle.CYAN)


def magenta(text: str) -> str:
    return styled(text, TermStyle.MAGENTA)


def warning(text: str) -> str:
    return styled(text, TermStyle.YELLOW, TermStyle.BOLD)


def approval_prompt(function_name: str, args: dict) -> tuple[str, str | None]:
    print()
    print(warning("Permission required"))
    print(f"{bold('Tool:')} {cyan(function_name)}")

    if function_name in {"write_file", "update"}:
        print(f"{bold('Path:')} {args.get('file_path', '')}")
    else:
        print(f"{bold('Args:')} {dim(str(args))}")

    print(
        f"{green('[y]')} allow once   "
        f"{red('[n]')} deny   "
        f"{magenta('[f]')} deny with feedback   "
        f"{cyan('[s]')} allow tool for session   "
        f"{yellow('[p]')} allow path for session"
    )

    answer = input(bold("> ")).strip().lower()

    if answer == "f":
        feedback = input(bold("Reason: ")).strip()
        return "f", feedback or "No reason provided."

    return answer, None


def print_write_preview(preview: str) -> None:
    print()
    print(bold(cyan("Proposed change preview")))
    print(dim("─" * 40))

    if is_unified_diff_preview(preview):
        print(format_diff_for_terminal(preview[:4000]))
    else:
        print(preview[:4000])

    print(dim("─" * 40))


def format_tool_call(function_call, verbose: bool) -> str:
    bullet = dim("•")
    tool_tag = cyan("[tool]")
    tool_name = bold(cyan(function_call.name))

    if verbose:
        return f"{bullet} {tool_tag} {tool_name} {dim(str(function_call.args))}"

    return f"{bullet} {tool_tag} {tool_name}"


def print_agent_update(text: str) -> None:
    print(f"{dim('•')} {dim(text)}")


def print_final_response(text: str) -> None:
    print()
    print(text)
    print()


def print_verbose_stats(user_prompt: str, response) -> None:
    print(dim(f"User prompt: {user_prompt}"))
    print(dim(f"Prompt tokens: {response.usage_metadata.prompt_token_count}"))
    print(dim(f"Response tokens: {response.usage_metadata.candidates_token_count}"))


def print_error(text: str) -> None:
    print(red(text))