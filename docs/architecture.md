# Work Copilot Architecture

This document explains the current Work Copilot architecture after the CLI foundation, provider abstraction, runtime event system, approval abstraction, and experimental Textual TUI work.

The main architectural goal is to keep these concerns separated:

- CLI/app startup
- terminal environment setup
- mode dispatch
- interactive session state
- agent runtime loop
- provider implementation
- tool definitions
- permission checks
- approval handling
- terminal rendering
- Textual rendering
- Textual approval/diff rendering
- JSON run logging
- actual tool execution

## High-level flow

One-shot CLI flow:

```text
User prompt
  -> main.py
  -> cli.py
  -> providers/factory.py
  -> agent_runtime.py
  -> provider adapter
  -> tool_registry.py
  -> tool_dispatch.py
  -> functions/*.py
  -> runtime_events.py
  -> terminal_event_sink.py / run_logging.py
```

Interactive CLI flow:

```text
uv run work-copilot --interactive
  -> main.py
  -> cli.py
  -> interactive_cli.py
  -> interactive_commands.py
  -> interactive_session.py
  -> agent_runtime.py
  -> terminal_event_sink.py / run_logging.py
```

Textual TUI flow:

```text
uv run work-copilot --tui
  -> main.py
  -> cli.py
  -> textual_app.py
  -> interactive_commands.py
  -> interactive_session.py
  -> agent_runtime.py
  -> textual_event_sink.py
  -> textual_approval.py
  -> textual_approval_screen.py
  -> textual_diff_view.py
  -> textual_diff_renderer.py
  -> textual_preview.py
```

## Mental model

```text
main.py                    = process entrypoint and terminal environment bootstrap
cli.py                     = CLI parsing, resolved config, mode dispatch
interactive_cli.py         = simple terminal REPL UI
interactive_commands.py    = shared slash command parsing and formatting
interactive_session.py     = provider-backed session state and model-turn execution
textual_app.py             = experimental Textual UI
textual_event_sink.py      = runtime events -> Textual activity log
textual_approval.py        = Textual approval bridge between runtime and TUI
textual_approval_screen.py = full-screen Textual approval review screen
textual_diff_view.py       = Textual diff preview widget and row CSS
textual_diff_renderer.py   = approval preview -> rendered diff rows
textual_preview.py         = diff parsing and structured row text formatting
agent_runtime.py           = provider-neutral model/tool loop
runtime_events.py          = typed runtime events and event sink protocol
terminal_event_sink.py     = runtime events -> terminal
run_logging.py             = runtime events -> JSON logs
approval.py                = typed approval requests/responses and handler protocol
terminal_approval.py       = terminal approval frontend
providers/factory.py       = provider/model selection
providers/base.py          = provider protocol
providers/gemini.py        = Gemini adapter
providers/openai.py        = OpenAI adapter
tool_registry.py           = available tool definitions
tool_dispatch.py           = permissioned tool executor
functions/*.py             = concrete tool implementations
permissions.py             = safety and permission rules
console_ui.py              = terminal preview/approval helpers
previews.py                = write/update preview helpers
agent_types.py             = provider-neutral shared data types
prompts.py                 = provider-neutral system prompt
```

## File responsibilities

### `main.py`

Process entrypoint.

Responsibilities:

- configure safe terminal environment defaults before Rich/Textual are imported
- lazily import `run_cli`
- call it
- exit with its return code

`main.py` sets `COLORTERM=truecolor` with `os.environ.setdefault(...)` so modern terminals are more likely to render Textual colors correctly.

`main.py` should stay small. It should not own argument parsing, provider setup, tool dispatch, approval logic, or runtime logic.

### `cli.py`

CLI orchestration layer.

Responsibilities:

- build and validate CLI arguments
- resolve workspace path
- resolve provider/model settings
- build `CliConfig`
- build `PermissionContext`
- create provider factories
- dispatch to one-shot, interactive CLI, or Textual mode
- print resolved config with `--show-config`

Supported modes:

```text
one-shot
interactive
tui
```

Example commands:

```bash
uv run work-copilot "Say hello and stop."
uv run work-copilot --interactive
uv run work-copilot --tui
uv run work-copilot --show-config
```

### `interactive_cli.py`

Simple terminal REPL UI.

Responsibilities:

- show the interactive CLI prompt
- read user input with `input(...)`
- handle slash commands
- print help/status output
- create/reset interactive session state through `interactive_session.py`
- run interactive model turns through `interactive_session.py`

This file is UI-specific. It should not contain provider-specific SDK code or tool execution logic.

### `interactive_commands.py`

Shared interactive command parsing and formatting.

Responsibilities:

- define interactive command names
- parse slash commands
- format `/help` output
- format `/status` output

Used by:

- `interactive_cli.py`
- `textual_app.py`

This prevents the simple CLI and Textual UI from drifting in command behavior and command text.

Supported commands:

```text
/help
/status
/clear
/exit
/quit
```

### `interactive_session.py`

UI-independent interactive session core.

Responsibilities:

- define `InteractiveSessionConfig`
- define `InteractiveSessionState`
- create session config/state
- reset provider/session context
- build interactive log directories
- build per-turn run loggers
- run one interactive model turn
- pass optional event sinks to `agent_runtime.py`
- pass optional approval handlers to `agent_runtime.py`
- optionally disable terminal runtime output

This file is the bridge between user interfaces and the provider-backed runtime.

Both the simple REPL and Textual UI use this module.

### `textual_app.py`

Experimental Textual TUI.

Responsibilities:

- render the Textual app layout
- show session/config state in a sidebar
- show conversation and runtime output in the activity log
- handle Textual input submissions
- handle slash commands
- run normal prompts through `interactive_session.py`
- refresh visible session state after turns
- pass `TextualEventSink` into runtime execution
- pass `TextualApprovalHandler` into runtime execution
- disable terminal runtime output for TUI turns
- coordinate Textual approval requests and responses

Current Textual status:

- normal model prompts work
- provider session context is preserved across turns
- runtime events render into the activity log
- approval requests are handled inside the TUI
- full-screen approval review is implemented
- structured diff preview is implemented for approval reviews
- streaming output is not implemented yet
- cancellation/interrupt handling is not implemented yet

### `textual_event_sink.py`

Textual renderer for runtime events.

Responsibilities:

- consume runtime events
- render model text into the Textual activity log
- render tool calls
- render tool results
- render provider errors
- render max-iteration warnings

The Textual event sink intentionally keeps the activity log conversation-focused.

It currently hides low-level runtime bookkeeping such as:

- run-start events
- duplicated final-response events
- usage-summary events

Those may later be shown in a status area instead of the main conversation log.

### `textual_approval.py`

Textual approval bridge.

Responsibilities:

- implement the `ApprovalHandler` protocol for Textual mode
- receive `ApprovalRequest` values from tool dispatch
- hand approval requests to the Textual app through callbacks/events
- wait for a Textual approval decision
- return a typed `ApprovalResponse`
- prevent Textual mode from falling back to terminal approval prompts

Current supported Textual approval actions:

```text
y = allow once
n = deny
f = deny with feedback
s = allow tool for session
p = allow path for session, when a path is available
```

### `textual_approval_screen.py`

Full-screen Textual approval review screen.

Responsibilities:

- render the approval-mode layout
- show approval actions in a sidebar
- show request metadata in the header
- host the diff preview widget
- handle keyboard approval actions
- collect denial feedback
- return `ApprovalResponse` values through a completion callback

This file owns the approval interaction UX, but it does not parse or format diffs directly.

### `textual_diff_view.py`

Textual diff preview widget.

Responsibilities:

- provide the scrollable diff preview container
- mount one Textual row widget per rendered diff row
- apply CSS classes for row-level styling
- provide visible row backgrounds for added/removed/hunk rows

This file owns Textual layout/CSS behavior for diff rows.

Full-row backgrounds are implemented here, not inside Rich `Text` strings.

### `textual_diff_renderer.py`

Approval preview renderer.

Responsibilities:

- convert raw approval preview text into `DiffRenderRow` values
- add high-level preview rows such as title, file summary, and separator
- classify rendered diff rows into CSS classes such as:
  - `column-header`
  - `hunk`
  - `added`
  - `removed`
  - `context`
- keep compatibility with older `render_approval_preview(...)` tests/helpers

This module bridges diff formatting and the Textual diff widget.

### `textual_preview.py`

Diff parsing and structured row text formatting.

Responsibilities:

- parse unified diff previews into structured `DiffLine` rows
- track old/new line numbers from hunk metadata
- summarize additions/removals
- format file summary headers
- format old/new/marker/content rows
- format hunk labels
- strip raw diff markers from content
- pair adjacent removed/added rows
- apply intra-line changed-span highlighting with `SequenceMatcher`

This module does not own full-width row backgrounds. Row backgrounds are applied by `textual_diff_view.py` through Textual CSS.

### `runtime_events.py`

Provider-neutral runtime event definitions.

Responsibilities:

- define structured runtime events
- define the `EventSink` protocol
- provide helper for converting events into log payloads

Current event types:

```text
run_started
model_turn
tool_result
final_response
provider_error
max_iterations_reached
usage_summary
```

Runtime events decouple the agent loop from consumers such as:

- terminal rendering
- Textual rendering
- JSON run logging
- tests/custom sinks

### `terminal_event_sink.py`

Terminal renderer for runtime events.

Responsibilities:

- consume runtime events
- render model progress
- render tool calls
- render tool results
- render final responses
- render provider errors
- render max-iteration messages
- render usage summaries
- respect verbose display settings

Used by normal one-shot and interactive CLI modes.

Textual mode disables terminal output for model turns so terminal rendering does not interfere with the TUI.

### `run_logging.py`

JSON run logging.

Responsibilities:

- store run metadata
- record runtime events
- save run logs to JSON
- provide `RunLogEventSink`

Run logging is opt-in because logs may contain prompts, file paths, tool outputs, code snippets, and other sensitive information.

Interactive sessions group per-turn logs under a shared interactive session directory.

### `approval.py`

Approval decision types and interfaces.

Responsibilities:

- define `ApprovalAction`
- define `ApprovalRequest`
- define `ApprovalResponse`
- define the `ApprovalHandler` protocol
- parse raw approval input into typed approval actions

Approval handling is intentionally separate from tool dispatch and UI rendering.

### `terminal_approval.py`

Terminal approval frontend.

Responsibilities:

- consume `ApprovalRequest`
- render previews when available
- prompt the user in the terminal
- return typed `ApprovalResponse`

Used by one-shot and interactive CLI modes.

Textual mode uses `TextualApprovalHandler` instead.

### `agent_runtime.py`

Provider-neutral agent loop.

Responsibilities:

- add the user prompt to provider history
- ask the provider for model turns
- emit structured runtime events
- execute requested tool calls through `tool_dispatch.py`
- send tool results back to the provider
- accumulate token usage
- stop when the model gives a final answer
- stop when max iterations are reached
- catch provider errors and return cleanly
- support optional extra event sinks
- support optional approval handlers
- optionally disable terminal event rendering

This file should not know whether the model is Gemini, OpenAI, local, or something else.

The runtime works with neutral types:

```text
ModelTurn
ToolCall
ToolResult
ToolSpec
UsageStats
UsageTotals
```

### `agent_types.py`

Provider-neutral shared data types.

Important types:

```text
ToolSpec
ToolCall
ToolResult
UsageStats
UsageTotals
ModelTurn
```

Provider adapters convert provider-specific objects into these neutral types before the rest of the app sees them.

For example:

```python
ToolCall(
    name="get_file_content",
    args={"file_path": "main.py"},
    call_id=None,
)
```

For OpenAI tool calls, `call_id` is populated because OpenAI requires it when returning tool results.

### `providers/base.py`

Provider protocol used by the runtime.

A provider must support:

```python
add_user_message(text)
generate(system_prompt, tools)
add_tool_results(results)
```

This lets `agent_runtime.py` talk to any provider without knowing provider SDK details.

This file also defines `ProviderError`, which is used when a provider request fails.

Examples:

- invalid API key
- invalid model name
- quota or billing issue
- provider-side API failure
- network/API failure

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

### `providers/gemini.py`

Gemini-specific provider adapter.

Responsibilities:

- create the Gemini client
- store Gemini message history
- convert neutral `ToolSpec` objects into Gemini function declarations
- convert Gemini function calls into neutral `ToolCall` objects
- convert neutral `ToolResult` objects into Gemini function responses
- extract usage metadata
- return neutral `ModelTurn` objects
- wrap Gemini SDK failures in `ProviderError`

Gemini SDK objects should stay inside this file.

### `providers/openai.py`

OpenAI-specific provider adapter.

Responsibilities:

- create the OpenAI client
- store OpenAI input/message history
- convert neutral `ToolSpec` objects into OpenAI function tools
- convert OpenAI function calls into neutral `ToolCall` objects
- preserve OpenAI `call_id` values
- convert neutral `ToolResult` objects into OpenAI function-call output items
- extract usage metadata
- return neutral `ModelTurn` objects
- wrap OpenAI SDK failures in `ProviderError`

OpenAI SDK objects should stay inside this file.

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

Tool schemas should live here, not inside individual tool files.

### `tool_dispatch.py`

Permissioned tool executor.

Responsibilities:

- receive neutral `ToolCall` objects
- evaluate permission rules
- build write/update previews when needed
- request approval through an `ApprovalHandler`
- execute the actual tool handler
- return neutral `ToolResult`
- preserve provider `call_id` values when returning tool results

Example flow:

```text
ToolCall(name="bash", args={"command": "echo hello"})
  -> evaluate permission
  -> request approval through ApprovalHandler
  -> execute run_shell_command()
  -> return ToolResult(...)
```

### `functions/*.py`

Concrete tool implementations.

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

Tool files should not contain provider-specific SDK code. Tool schemas belong in `tool_registry.py`.

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

### `console_ui.py`

Terminal preview and approval helpers.

Responsibilities:

- render mutation previews
- ask for terminal approval
- format terminal output with Rich

This file should not contain provider logic, runtime logic, or tool execution logic.

### `previews.py`

Diff and mutation preview helpers.

Responsibilities:

- build previews for file writes
- build previews for file updates
- parse unified diffs for terminal display

Used before potentially dangerous mutations so the user can review changes.

### `prompts.py`

Provider-neutral system prompt and model behavior instructions.

Responsibilities:

- define the main system prompt
- describe agent behavior rules
- describe conversational/no-tool behavior
- describe tool usage expectations
- describe safety expectations
- describe denied-tool feedback behavior

This file should stay provider-neutral.

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
--interactive
--tui
--show-config
--log-run
--log-dir .work_copilot/runs
```

Examples:

```bash
uv run work-copilot --workspace . --provider openai --model gpt-5.4-mini "Say hello and stop."
uv run work-copilot --interactive
uv run work-copilot --tui
uv run work-copilot --show-config
```

## Usage summary

The runtime tracks usage when the provider returns usage metadata.

Usage is tracked with:

```text
UsageStats
UsageTotals
```

Terminal modes can render usage summaries.

Textual mode currently hides usage summaries from the main activity log to keep the conversation readable. Usage information may later move into a status/sidebar area.

## Provider-neutral design rule

Provider SDK objects should stay inside provider adapters.

Good boundary:

```text
providers/gemini.py converts Gemini objects into ToolCall / ModelTurn
providers/openai.py converts OpenAI objects into ToolCall / ModelTurn
agent_runtime.py only sees ToolCall / ModelTurn
```

Bad boundary:

```text
agent_runtime.py imports google.genai.types
agent_runtime.py imports OpenAI SDK objects
tool_dispatch.py receives Gemini FunctionCall objects
tool_dispatch.py receives OpenAI response objects
functions/*.py define provider schemas
```

## Adding another provider

To add another provider later, for example a local model provider:

1. Create `providers/local.py`.
2. Implement the provider protocol from `providers/base.py`.
3. Convert neutral `ToolSpec` into the provider's tool/function schema.
4. Convert provider tool calls into neutral `ToolCall`.
5. Convert neutral `ToolResult` into provider tool-result messages.
6. Extract provider usage metadata into `UsageStats`.
7. Wrap provider request failures in `ProviderError`.
8. Add the provider to `providers/factory.py`.
9. Add tests.
10. Add CLI/docs examples.

The goal is that `agent_runtime.py`, `tool_dispatch.py`, and `functions/*.py` do not need major changes.

## Current Textual limitations

Textual mode is functional but still experimental.

Current limitations:

- streaming output is not implemented
- cancellation/interrupt handling is not implemented
- mouse/button approval controls are not implemented
- side-by-side diff view is not implemented
- multi-file diff navigation is not implemented
- provider/model selection inside the TUI is not implemented
- connector tools are not implemented

## Package entrypoint and flat-layout note

The preferred command is:

```bash
uv run work-copilot ...
```

The project currently uses a flat layout with explicit setuptools module/package configuration in `pyproject.toml`.

This is a bridge solution so `uv` can install the package script entrypoint.

A future package-layout migration may move the project to:

```text
src/
  work_copilot/
    __init__.py
    main.py
    cli.py
    ...
```

At that point, the script entrypoint would likely become:

```toml
[project.scripts]
work-copilot = "work_copilot.main:main"
```

## Quick architecture checks

Gemini SDK imports should only appear in the Gemini provider:

```bash
rg "google.genai|from google import genai" --glob "*.py" -g "!providers/gemini.py"
```

OpenAI SDK imports should only appear in the OpenAI provider:

```bash
rg "from openai|import OpenAI" --glob "*.py" -g "!providers/openai.py"
```

Production code should not import provider SDKs outside provider adapters.

Run tests and lint:

```bash
uv run ruff check .
uv run pytest
```