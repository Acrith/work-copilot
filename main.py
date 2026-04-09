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

        # Function calling parse if function call is required
        function_results = []
        if response.function_calls:
            if not printed_tool_header:
                print("\n" + "─" * 40)
                print("TOOL CALLS")
                print("─" * 40)
                printed_tool_header = True

            for call in response.function_calls:
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
        # Otherwise just print response
        else:
            print("\n" + "─" * 40)
            print("AGENT RESPONSE")
            print("─" * 40)
            print(response.text)
            print()
            return
        
        # Append function feedback to messages
        messages.append(types.Content(role="user", parts=function_results))
    
    print(f"Max iterations ({MAX_ITERATIONS}) reached.")
    sys.exit(1)

if __name__ == "__main__":
    main()
