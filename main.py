import os
import sys
import argparse
from dotenv import load_dotenv
from google import genai
from google.genai import types

#LocalFiles
from prompts import system_prompt
from functions.call_function import available_functions, call_function
from permissions import PermissionMode, PermissionContext, load_rules

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

    # Avoid showing fake "updates" that are really just tool-like noise
    if stripped.startswith("[tool]"):
        return False

    return True


def format_tool_call(function_call, verbose: bool) -> str:
    if verbose:
        return f"• [tool] {function_call.name}({function_call.args})"
    return f"• [tool] {function_call.name}"


def print_update_line(text: str):
    print(f"• {text}")


def print_final_response(text: str):
    print()
    print(text)
    print()

def main():
    load_dotenv()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("No API key found!")
    
    parser = argparse.ArgumentParser(description="Chatbot")
    parser.add_argument("user_prompt", type=str, help="User prompt")
    parser.add_argument("--workspace", default=".", help="Workspace directory the agent can use")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--verbose-functions", action="store_true", help="Show function calls and args")
    parser.add_argument("--permission-mode", choices=[m.value for m in PermissionMode], default=PermissionMode.DEFAULT.value, help="Permission mode for tool execution")
    args = parser.parse_args()

    # Resolve Workspace
    workspace = os.path.abspath(args.workspace)
    if not os.path.isdir(workspace):
        raise ValueError(f"Workspace is not a directory: {args.workspace}")

    # Resolve Permission Context
    permission_context = PermissionContext(
        mode=PermissionMode(args.permission_mode),
        workspace=workspace,
        rules=load_rules(workspace),
    )

    client = genai.Client(api_key=api_key)
    messages = [types.Content(role="user", parts=[types.Part(text=args.user_prompt)])]
    printed_tool_header = False

    for _ in range(MAX_ITERATIONS):
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=messages,
            config=types.GenerateContentConfig(
                tools=[available_functions],
                system_instruction=system_prompt
            ),
        )

        if response.candidates:
            for candidate in response.candidates:
                messages.append(candidate.content)

        if args.verbose is True:
            print(f"User prompt: {args.user_prompt}")
            print(f"Prompt tokens: {response.usage_metadata.prompt_token_count}")
            print(f"Response tokens: {response.usage_metadata.candidates_token_count}")

        text_parts = extract_text_parts(response)
        function_results = []

        if response.function_calls:
            for text in text_parts:
                if is_meaningful_update(text):
                    print_update_line(text)

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
                if args.verbose is True:
                    print(function_call_result.parts[0].function_response)
        
            # Append function feedback to messages
            messages.append(types.Content(role="user", parts=function_results))
            continue
        
        final_text = "\n".join(text_parts).strip()
        if final_text:
            print_final_response(final_text)
            return
    
    print(f"Max iterations ({MAX_ITERATIONS}) reached.")
    sys.exit(1)

if __name__ == "__main__":
    main()
