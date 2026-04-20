# Work Copilot Architecture

This document explains the current structure of Work Copilot after the provider abstraction refactor.

The goal of the architecture is to keep these concerns separated:

- CLI/app startup
- agent loop
- model provider implementation
- tool definitions
- permission checks
- actual tool execution
- terminal UI rendering

## High-level flow

```text
main.py
  -> providers/factory.py
  -> agent_runtime.py
  -> providers/<provider>.py
  -> tool_registry.py
  -> tool_dispatch.py
  -> functions/*.py
```

A typical request flows like this:

```text
User prompt
  -> main.py parses CLI args
  -> provider is created by providers/factory.py
  -> agent_runtime.py starts the loop
  -> provider sends prompt/tools to the model
  -> model responds with text and/or tool calls
  -> tool_dispatch.py executes approved tool calls
  -> tool results are sent back to the provider
  -> model returns final answer
```

## File responsibilities

### `main.py`

Application entrypoint.

Responsibilities:

- load environment variables
- parse CLI arguments
- validate workspace path
- create permission context
- create model provider through `providers/factory.py`
- start the agent runtime

`main.py` should not contain provider SDK code or tool execution logic.

Good:

```python
provider = create_provider(args.provider, model=model)

final_text = run_agent(
    provider=provider,
    user_prompt=args.user_prompt,
    workspace=workspace,
    permission_context=permission_context,
)
```

Avoid:

```python
from google import genai
from google.genai import types
```

Provider SDK imports should live inside provider adapters.

---

### `providers/factory.py`

Provider creation and default model resolution.

Responsibilities:

- resolve provider name
- resolve default model for a provider
- read provider-specific API key environment variables
- create and return the correct provider object

Example:

```python
provider = create_provider(
    "gemini",
    model="gemini-2.5-flash",
)
```

Currently supported providers:

```text
gemini
```

Later, this file can grow to support providers like:

```text
openai
local
```

---

### `providers/base.py`

Defines the provider protocol used by the runtime.

A provider must support:

```python
add_user_message(text)
generate(system_prompt, tools)
add_tool_results(results)
```

This lets `agent_runtime.py` talk to any provider without knowing the provider SDK details.

---

### `providers/gemini.py`

Gemini-specific provider adapter.

Responsibilities:

- create the Gemini client
- store Gemini message history
- convert neutral `ToolSpec` objects into Gemini function declarations
- convert Gemini function calls into neutral `ToolCall` objects
- convert neutral `ToolResult` objects into Gemini function responses
- return neutral `ModelTurn` objects to the runtime

Gemini SDK objects should stay inside this file.

Good:

```python
from google import genai
from google.genai import types
```

Bad outside this file:

```python
from google.genai import types
```

---

### `agent_runtime.py`

Provider-neutral agent loop.

Responsibilities:

- add the user prompt to provider history
- request a model turn from the provider
- print meaningful model progress updates
- execute requested tool calls
- send tool results back to the provider
- print the final response
- stop when the model gives a final answer
- stop when max iterations are reached

This file should not know whether the model is Gemini, OpenAI, or something local.

The runtime works with neutral types:

```python
ModelTurn
ToolCall
ToolResult
ToolSpec
```

---

### `agent_types.py`

Provider-neutral data types.

Defines shared types used between providers, runtime, registry, and dispatch.

Important types:

```python
ToolSpec
ToolCall
ToolResult
UsageStats
ModelTurn
```

These types prevent provider-specific objects from spreading through the app.

For example, instead of passing a Gemini function call around the app, the Gemini provider converts it into:

```python
ToolCall(
    name="get_file_content",
    args={"file_path": "main.py"},
)
```

---

### `tool_registry.py`

Single source of truth for available tools.

Responsibilities:

- define tool names
- define tool descriptions
- define provider-neutral parameter schemas
- map tool names to Python handler functions

This file answers:

```text
What tools exist?
What arguments do they accept?
Which Python function handles each tool?
```

Example responsibilities:

```text
get_file_content -> functions/get_file_content.py
write_file       -> functions/write_file.py
bash             -> functions/run_shell_command.py
```

Tool schemas should live here, not inside individual tool files.

---

### `tool_dispatch.py`

Permissioned tool executor.

Responsibilities:

- receive neutral `ToolCall` objects
- evaluate permission rules
- show write/update previews
- ask for approval when needed
- execute the actual tool handler
- return a neutral `ToolResult`

This is where a model-requested tool call becomes a real action.

Example flow:

```text
ToolCall(name="bash", args={"command": "echo hello"})
  -> evaluate permission
  -> ask user for approval
  -> execute run_shell_command()
  -> return ToolResult(...)
```

---

### `functions/*.py`

Actual tool implementations.

Examples:

```text
functions/get_file_content.py
functions/write_file.py
functions/update_file.py
functions/run_shell_command.py
functions/run_tests.py
functions/git_status.py
```

Responsibilities:

- perform one concrete action
- validate local inputs where appropriate
- return readable results or errors

Tool files should not contain provider-specific SDK code.

Good:

```python
def get_file_content(file_path: str, working_directory: str) -> str:
    ...
```

Avoid:

```python
schema_get_file_content = types.FunctionDeclaration(...)
```

Tool schemas belong in `tool_registry.py`.

---

### `permissions.py`

Permission and safety policy.

Responsibilities:

- classify tools as read/write/exec
- protect sensitive paths
- deny unsafe reads/writes/execs
- load workspace rule config
- manage session-level allowances
- decide whether a tool call is allowed, denied, or requires approval

This file does not execute tools directly. It only decides whether execution is safe.

---

### `console_ui.py`

Terminal rendering and prompts.

Responsibilities:

- print tool calls
- print agent updates
- print final responses
- render mutation previews
- ask for approval
- format terminal output with Rich

This file should not contain business logic for providers or tools.

---

### `previews.py`

Diff and mutation preview helpers.

Responsibilities:

- build previews for file writes
- build previews for file updates
- parse unified diffs for terminal display

Used before potentially dangerous mutations so the user can review changes.

---

### `prompts.py`

System prompt and model behavior instructions.

Responsibilities:

- define the main system prompt
- describe the agent behavior rules
- describe tool usage expectations
- describe safety expectations

This file should stay provider-neutral.

---

## Provider-neutral design rule

Provider SDK objects should stay inside provider adapters.

For example:

```text
Gemini SDK objects -> providers/gemini.py
OpenAI SDK objects -> providers/openai.py
```

The rest of the app should use neutral types from `agent_types.py`.

Good boundary:

```text
providers/gemini.py converts Gemini objects into ToolCall / ModelTurn
agent_runtime.py only sees ToolCall / ModelTurn
```

Bad boundary:

```text
agent_runtime.py imports google.genai.types
tool_dispatch.py receives Gemini FunctionCall objects
functions/*.py define Gemini schemas
```

## Current provider flow

```text
main.py
  creates provider through providers/factory.py

providers/factory.py
  creates GeminiProvider

agent_runtime.py
  calls provider.generate(...)

providers/gemini.py
  talks to Gemini
  returns ModelTurn

agent_runtime.py
  executes ToolCall objects through tool_dispatch.py

tool_dispatch.py
  runs handlers from tool_registry.py

functions/*.py
  perform the actual filesystem/git/bash/test actions
```

## Adding a new provider

To add a new provider later, for example OpenAI:

1. Create `providers/openai.py`
2. Implement the provider protocol from `providers/base.py`
3. Convert `ToolSpec` into the provider's tool/function schema
4. Convert provider tool calls into neutral `ToolCall`
5. Convert neutral `ToolResult` into provider tool-result messages
6. Add the provider to `providers/factory.py`
7. Add tests

The goal is that `agent_runtime.py`, `tool_dispatch.py`, and `functions/*.py` do not need major changes.

## Quick architecture checks

Gemini SDK imports should only appear in the Gemini provider:

```bash
rg "google.genai|from google import genai" --glob "*.py" -g "!providers/gemini.py"
```

Expected output:

```text
# no output
```

The old `call_function` shim should not exist anymore:

```bash
rg "call_function|available_functions"
```

Expected output:

```text
# no output
```

Run tests and lint:

```bash
uv run pytest
uv run ruff check .
```

## Mental model

```text
main.py              = starts the app
providers/factory.py = chooses provider
agent_runtime.py     = runs the loop
providers/gemini.py  = translates Gemini-specific stuff
tool_registry.py     = lists available tools
tool_dispatch.py     = safely executes requested tools
functions/*.py       = actual tool implementations
permissions.py       = safety rules
console_ui.py        = terminal output
```