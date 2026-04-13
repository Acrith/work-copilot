import argparse
import os
import sys

from dotenv import load_dotenv
from google import genai
from google.genai import types

from console_ui import (
    format_tool_call,
    print_agent_update,
    print_error,
    print_final_response,
    print_verbose_stats,
)
from functions.call_function import available_functions, call_function
from permissions import PermissionContext, PermissionMode, load_rules
from prompts import system_prompt

MAX_ITERATIONS = 20


def extract_text_parts(response) -> list[str]:
    texts = []

    if not response.candidates:
        return texts

    for candidate in response.candidates:
        content = getattr(candidate, "content", None)
        if not content:
            continue

        parts = getattr(content, "parts", None) or []
        for part in parts:
            text = getattr(part, "text", None)
            if not text:
                continue

            stripped = text.strip()
            if stripped:
                texts.append(stripped)

    return texts


def is_meaningful_update(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False

    if stripped.startswith("[tool]"):
        return False

    return True


def main():
    load_dotenv()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("No API key found!")

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

    permission_context = PermissionContext(
        mode=PermissionMode(args.permission_mode),
        workspace=workspace,
        rules=load_rules(workspace),
    )

    client = genai.Client(api_key=api_key)
    messages = [types.Content(role="user", parts=[types.Part(text=args.user_prompt)])]

    for _ in range(MAX_ITERATIONS):
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=messages,
            config=types.GenerateContentConfig(
                tools=[available_functions],
                system_instruction=system_prompt,
            ),
        )

        if response.candidates:
            for candidate in response.candidates:
                messages.append(candidate.content)

        if args.verbose:
            print_verbose_stats(args.user_prompt, response)

        text_parts = extract_text_parts(response)
        function_results = []

        if response.function_calls:
            for text in text_parts:
                if is_meaningful_update(text):
                    print_agent_update(text)

            for call in response.function_calls:
                print(format_tool_call(call, args.verbose_functions))

                function_call_result = call_function(
                    call,
                    workspace,
                    permission_context,
                    args.verbose_functions,
                )
                if not function_call_result.parts:
                    raise Exception("function_call_result has no parts")
                if not function_call_result.parts[0].function_response:
                    raise Exception("function_call_result has no function_response")
                if not function_call_result.parts[0].function_response.response:
                    raise Exception("function_call_result has no response")

                function_results.append(function_call_result.parts[0])

                if args.verbose:
                    print(function_call_result.parts[0].function_response)

            messages.append(types.Content(role="user", parts=function_results))
            continue

        final_text = "\n".join(text_parts).strip()
        if final_text:
            print_final_response(final_text)
            return

    print_error(f"Max iterations ({MAX_ITERATIONS}) reached.")
    sys.exit(1)


if __name__ == "__main__":
    main()