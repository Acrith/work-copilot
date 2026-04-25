# Work Copilot

Work Copilot is a local terminal-based coding/workspace agent.

It can inspect files, search code, run tests, execute approved shell commands, and make approved file changes inside a selected workspace.

This is a learning and development project. Do not treat it as production-ready automation.

## Current status

Work Copilot currently supports:

- Gemini and OpenAI providers
- provider-neutral runtime and tool calling
- workspace-scoped file and shell tools
- permission-gated write and exec actions
- typed approval requests and responses
- terminal approval flow for write/exec actions
- interactive CLI sessions
- experimental Textual TUI mode
- runtime events
- terminal runtime event rendering
- Textual runtime event rendering
- opt-in JSON run logging
- package script entrypoint with `uv run work-copilot`

Textual mode is experimental. It can run normal model prompts, but full Textual approval UI, async execution, streaming, and rich tool/diff panels are not implemented yet.

## Requirements

- Python 3.13+
- `uv`
- API key for at least one supported provider

Supported providers:

```text
gemini
openai
```

Gemini is the default provider.

## Setup

Clone the repo:

```bash
git clone https://github.com/Acrith/work-copilot.git
cd work-copilot
```

Install dependencies:

```bash
uv sync
```

Create a local `.env` file:

```env
GEMINI_API_KEY="your-gemini-api-key"
OPENAI_API_KEY="your-openai-api-key"
```

The `.env` file should not be committed.

## Running Work Copilot

Preferred package entrypoint:

```bash
uv run work-copilot "List files in the workspace root and stop after listing them."
```

Interactive CLI mode:

```bash
uv run work-copilot --interactive
```

Experimental Textual TUI:

```bash
uv run work-copilot --tui
```

Show resolved config:

```bash
uv run work-copilot --show-config
```

The older development entrypoint still works:

```bash
uv run main.py "Say hello and stop."
```

## Common examples

Run with the default provider:

```bash
uv run work-copilot --workspace . "List files in the workspace root and stop after listing them."
```

Run with Gemini explicitly:

```bash
uv run work-copilot --workspace . --provider gemini "Say hello and stop."
```

Run with OpenAI:

```bash
uv run work-copilot --workspace . --provider openai --model gpt-5.4-mini "Say hello and stop."
```

Cheap OpenAI smoke test:

```bash
uv run work-copilot --provider openai --model gpt-5.4-nano "Say hello and stop."
```

Use verbose output:

```bash
uv run work-copilot --verbose "Say hello and stop."
```

Limit model/tool loop iterations:

```bash
uv run work-copilot --max-iterations 3 "Inspect the project and summarize it."
```

## Provider and model configuration

You can choose provider/model using CLI flags:

```bash
uv run work-copilot --provider openai --model gpt-5.4-mini "Say hello."
```

Or with environment variables:

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

Gemini remains the default provider so OpenAI usage is explicit unless overridden.

## Interactive commands

Interactive CLI mode and Textual mode support:

```text
/help
/status
/clear
/exit
/quit
```

Command behavior:

- `/help` shows available commands.
- `/status` shows current session/provider/workspace state.
- `/clear` resets provider/session context.
- `/exit` exits the current interactive mode.
- `/quit` is an alias for `/exit`.

## Textual mode status

Textual mode is experimental but can run normal model prompts.

Currently supported:

- launches with `uv run work-copilot --tui`
- shows session/config state in the sidebar
- supports `/help`, `/status`, `/clear`, `/exit`, and `/quit`
- renders normal user prompts and model responses in the activity log
- preserves provider session context across turns
- renders runtime events through the Textual activity log
- prevents approval requests from falling back to terminal prompts

Current limitations:

- Textual approval UI is not implemented yet
- write/exec approval requests are denied safely in Textual mode
- model execution currently runs synchronously and may temporarily block the UI
- streaming output is not implemented yet
- rich diff/tool preview panels are not implemented yet
- provider/model selection inside the TUI is not implemented yet

For write/exec tasks, use interactive CLI mode for now:

```bash
uv run work-copilot --interactive
```

## Permission modes

The agent uses a permission layer before write/exec actions.

Current permission mode flag:

```bash
--permission-mode default
```

Available modes are defined by `PermissionMode` in `permissions.py`.

Typical behavior:

- read-only tools are allowed
- write/update tools ask for approval in terminal CLI modes
- bash/exec tools ask for approval in terminal CLI modes
- Textual mode denies approval requests safely until a real TUI approval flow exists
- sensitive/protected paths are denied
- session-level approvals can be granted interactively in terminal CLI mode

## Run logging

Run logging is opt-in because logs may contain prompts, file paths, tool outputs, and code snippets.

Enable JSON run logging:

```bash
uv run work-copilot --log-run "Say hello and stop."
```

Choose a log directory:

```bash
uv run work-copilot --log-run --log-dir .work_copilot/runs "Say hello and stop."
```

Interactive mode groups per-turn logs under an interactive session directory.

## Development

Run tests:

```bash
uv run pytest
```

Run lint:

```bash
uv run ruff check .
```

Format:

```bash
uv run ruff format .
```

Common pre-PR check:

```bash
uv run ruff check .
uv run pytest
```

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the current provider/tool/runtime/Textual structure.

High-level flow:

```text
main.py
  -> cli.py
  -> providers/factory.py
  -> agent_runtime.py
  -> providers/*.py
  -> tool_registry.py
  -> tool_dispatch.py
  -> functions/*.py
```

Interactive and Textual flow:

```text
cli.py
  -> interactive_cli.py or textual_app.py
  -> interactive_commands.py
  -> interactive_session.py
  -> agent_runtime.py
  -> runtime_events.py
  -> terminal_event_sink.py / textual_event_sink.py / run_logging.py
```

## Repository visibility

This project may stay public during early development because it is easier to inspect, discuss, and iterate on.

As the agent becomes more capable, especially if it gains connectors for workplace systems, internal workflows, or company-specific automation, it should likely become private.

Reasons to make it private later:

- prompts and tool behavior may reveal personal workflow patterns
- connector code may reflect internal systems or assumptions
- logs/examples may accidentally include sensitive operational details
- the project may become useful enough that it is no longer just a learning artifact

Keep secrets out of the repository regardless of visibility.

```env
# Never commit real keys
GEMINI_API_KEY="..."
OPENAI_API_KEY="..."
```