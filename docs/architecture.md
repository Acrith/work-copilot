# Work Copilot Architecture

This document explains the current structure of Work Copilot after the provider abstraction and OpenAI provider work.

The goal of the architecture is to keep these concerns separated:

- CLI/app startup
- agent loop
- model provider implementation
- provider selection
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
  -> runtime prints usage summary
```

## File responsibilities

### `main.py`

Application entrypoint.

Responsibilities:

- load environment variables
- parse CLI arguments
- validate workspace path
- create permission context
- resolve provider/model settings
- create model provider through `providers/factory.py`
- start the agent runtime

`main.py` should not contain provider SDK code or tool execution logic.

Good:

```python
model = args.model or get_default_model(args.provider)

provider = create_provider(
    args.provider,
    model=model,
)

final_text = run_agent(
    provider=provider,
    user_prompt=args.user_prompt,
    workspace=workspace,
    permission_context=permission_context,
    max_iterations=args.max_iterations,
)
```

Avoid:

```python
from google import genai
from google.genai import types
from openai import OpenAI
```

Provider SDK imports should live inside provider adapters.

---

### `runtime_events.py`

Provider-neutral runtime event definitions.

Responsibilities:

- define structured events emitted by the agent runtime
- define the `EventSink` protocol
- provide helpers for converting runtime events into log payloads

Runtime events are used to decouple the agent loop from consumers such as:

- JSON run logging
- terminal rendering
- future interactive CLI
- future Textual/TUI frontend

Runtime events can currently be consumed by:

- `TerminalEventSink`
- `RunLogEventSink`
- test/custom event sinks

Current event examples:

```text
run_started
model_turn
tool_result
final_response
provider_error
max_iterations_reached
```

---

### `terminal_event_sink.py`

Terminal renderer for runtime events.

Responsibilities:

- consume runtime events
- render model progress updates
- render tool calls
- render final responses
- render provider errors
- render max-iteration messages
- render usage summaries
- show verbose turn/tool details when requested

This keeps terminal rendering separate from the provider-neutral runtime loop.

---

### `run_logging.py`

JSON run logging.

Responsibilities:

- store run metadata
- record runtime events
- save run logs to JSON
- provide `RunLogEventSink` so logging can consume runtime events like any other event sink

Run logging is opt-in because logs may contain prompts, file paths, tool outputs, and code snippets.

---

### `providers/factory.py`

Provider creation and default model resolution.

Responsibilities:

- resolve provider name
- resolve default model for a provider
- read provider-specific API key environment variables
- create and return the correct provider object

Currently supported providers:

```text
gemini
openai
```

Current defaults:

```text
Provider: gemini
Gemini model: gemini-2.5-flash
OpenAI model: gpt-5.4-mini
```

Gemini remains the default provider so OpenAI usage is explicit unless overridden.

Example:

```python
provider = create_provider(
    "openai",
    model="gpt-5.4-mini",
)
```

Later, this file can grow to support providers like:

```text
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

This file also defines:

```python
ProviderError
```

`ProviderError` is used when a provider request fails, such as:

- invalid API key
- invalid model name
- quota or billing issue
- provider-side API failure
- network/API request failure

The runtime catches `ProviderError` and prints a clean error instead of showing a full SDK traceback.

---

### `providers/gemini.py`

Gemini-specific provider adapter.

Responsibilities:

- create the Gemini client
- store Gemini message history
- convert neutral `ToolSpec` objects into Gemini function declarations
- convert Gemini function calls into neutral `ToolCall` objects
- convert neutral `ToolResult` objects into Gemini function responses
- extract usage metadata
- return neutral `ModelTurn` objects to the runtime
- wrap Gemini SDK request failures in `ProviderError`

Gemini SDK objects should stay inside this file.

Good here:

```python
from google import genai
from google.genai import types
```

Bad outside this file:

```python
from google.genai import types
```

---

### `providers/openai.py`

OpenAI-specific provider adapter.

Responsibilities:

- create the OpenAI client
- store OpenAI input/message history
- convert neutral `ToolSpec` objects into OpenAI function tools
- convert OpenAI function calls into neutral `ToolCall` objects
- preserve OpenAI `call_id` values for tool result submission
- convert neutral `ToolResult` objects into OpenAI `function_call_output` items
- extract usage metadata
- return neutral `ModelTurn` objects to the runtime
- wrap OpenAI SDK request failures in `ProviderError`

OpenAI SDK objects should stay inside this file.

Good here:

```python
from openai import OpenAI
```

Bad outside this file:

```python
from openai import OpenAI
```

OpenAI tool calling requires the original provider call ID to be returned with the tool result. This is why neutral tool calls/results support:

```python
call_id: str | None
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
- accumulate token usage across turns
- print the final response
- print final usage summary
- stop when the model gives a final answer
- stop when max iterations are reached
- catch `ProviderError` and return cleanly

This file should not know whether the model is Gemini, OpenAI, or something local.

The runtime works with neutral types:

```python
ModelTurn
ToolCall
ToolResult
ToolSpec
UsageStats
UsageTotals
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
UsageTotals
ModelTurn
```

These types prevent provider-specific objects from spreading through the app.

For example, instead of passing a Gemini or OpenAI function call around the app, the provider converts it into:

```python
ToolCall(
    name="get_file_content",
    args={"file_path": "main.py"},
    call_id=None,
)
```

For OpenAI tool calls, `call_id` is populated because OpenAI requires it when returning tool results.

Example:

```python
ToolCall(
    name="get_file_content",
    args={"file_path": "main.py"},
    call_id="call_123",
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

Example mappings:

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
- preserve provider `call_id` values when returning tool results

This is where a model-requested tool call becomes a real action.

Example flow:

```text
ToolCall(name="bash", args={"command": "echo hello"})
  -> evaluate permission
  -> ask user for approval
  -> execute run_shell_command()
  -> return ToolResult(...)
```

For OpenAI, the returned `ToolResult` preserves the original call ID:

```python
ToolResult(
    name="bash",
    payload={"result": "..."},
    call_id="call_123",
)
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

## Provider environment variables

Gemini:

```env
GEMINI_API_KEY="..."
```

OpenAI:

```env
OPENAI_API_KEY="..."
```

Provider/model defaults can be overridden with:

```env
WORK_COPILOT_PROVIDER="openai"
WORK_COPILOT_MODEL="gpt-5.4-mini"
```

Current defaults:

```text
Provider: gemini
Gemini model: gemini-2.5-flash
OpenAI model: gpt-5.4-mini
```

## CLI options

Common options:

```bash
--workspace .
--provider gemini
--provider openai
--model gpt-5.4-mini
--verbose
--verbose-functions
--max-iterations 20
--permission-mode default
```

Example:

```bash
uv run main.py --workspace . --provider openai --model gpt-5.4-mini "Say hello and stop."
```

Cheap OpenAI smoke test:

```bash
uv run main.py --provider openai --model gpt-5.4-nano "Say hello and stop."
```

## Usage summary

At the end of a run, the runtime prints token usage if the provider returned usage metadata.

Example:

```text
Usage: input=1976 output=8 total=1984 tokens
```

With `--verbose`, per-turn usage is also printed.

Example:

```text
Turn usage: input=1976 output=8 total=1984 tokens
```

Usage is tracked with:

```python
UsageStats
UsageTotals
```

The runtime accumulates usage across all model turns in a run.

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
providers/openai.py converts OpenAI objects into ToolCall / ModelTurn
agent_runtime.py only sees ToolCall / ModelTurn
```

Bad boundary:

```text
agent_runtime.py imports google.genai.types
agent_runtime.py imports OpenAI
tool_dispatch.py receives Gemini FunctionCall objects
tool_dispatch.py receives OpenAI response objects
functions/*.py define provider schemas
```

## Current provider flow

```text
main.py
  parses CLI/env provider settings

providers/factory.py
  creates GeminiProvider or OpenAIProvider

agent_runtime.py
  calls provider.generate(...)

providers/<provider>.py
  talks to the provider SDK
  returns ModelTurn

agent_runtime.py
  executes ToolCall objects through tool_dispatch.py

tool_dispatch.py
  runs handlers from tool_registry.py

functions/*.py
  perform the actual filesystem/git/bash/test actions
```

## Adding another provider

To add another provider later, for example a local model provider:

1. Create `providers/local.py`
2. Implement the provider protocol from `providers/base.py`
3. Convert neutral `ToolSpec` into the provider's tool/function schema
4. Convert provider tool calls into neutral `ToolCall`
5. Convert neutral `ToolResult` into provider tool-result messages
6. Extract provider usage metadata into `UsageStats`
7. Wrap provider request failures in `ProviderError`
8. Add the provider to `providers/factory.py`
9. Add tests
10. Add CLI/docs examples

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

OpenAI SDK imports should only appear in the OpenAI provider:

```bash
rg "from openai|import OpenAI" --glob "*.py" -g "!providers/openai.py"
```

Expected output may include tests, but production code should only import OpenAI from `providers/openai.py`.

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
main.py                = starts the app
runtime_events.py      = structured events emitted by the runtime
terminal_event_sink.py = renders runtime events to terminal
run_logging.py         = JSON logging and run-log event sink
providers/factory.py   = chooses provider and default model
agent_runtime.py       = runs the model/tool loop
providers/gemini.py    = translates Gemini-specific stuff
providers/openai.py    = translates OpenAI-specific stuff
tool_registry.py       = lists available tools
tool_dispatch.py       = safely executes requested tools
functions/*.py         = actual tool implementations
permissions.py         = safety rules
console_ui.py          = terminal output
previews.py            = write/update previews
agent_types.py         = shared provider-neutral data types
prompts.py             = system prompt
```