import argparse
import os
import sys

from dotenv import load_dotenv

from agent_runtime import run_agent
from permissions import PermissionContext, PermissionMode, load_rules
from providers.gemini import GeminiProvider

MAX_ITERATIONS = 20


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Chatbot")
    parser.add_argument("user_prompt", type=str, help="User prompt")
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace directory the agent can use",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument(
        "--verbose-functions",
        action="store_true",
        help="Show function calls and args",
    )
    parser.add_argument(
        "--permission-mode",
        choices=[m.value for m in PermissionMode],
        default=PermissionMode.DEFAULT.value,
        help="Permission mode for tool execution",
    )

    args = parser.parse_args()

    workspace = os.path.abspath(args.workspace)
    if not os.path.isdir(workspace):
        raise ValueError(f"Workspace is not a directory: {args.workspace}")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("No API key found!")

    permission_context = PermissionContext(
        mode=PermissionMode(args.permission_mode),
        workspace=workspace,
        rules=load_rules(workspace),
    )

    provider = GeminiProvider(
        api_key=api_key,
        model="gemini-2.5-flash",
    )

    final_text = run_agent(
        provider=provider,
        user_prompt=args.user_prompt,
        workspace=workspace,
        permission_context=permission_context,
        verbose=args.verbose,
        verbose_functions=args.verbose_functions,
        max_iterations=MAX_ITERATIONS,
    )

    if final_text is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
