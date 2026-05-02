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
- full-screen Textual approval screen
- structured Textual diff previews for approval reviews
- opt-in JSON run logging
- package script entrypoint with `uv run work-copilot`
- terminal truecolor startup hint for improved Textual colors

Textual mode is experimental, but it can now run normal model prompts and handle write/exec approval requests inside the TUI.

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

Textual mode is experimental but functional for normal prompt turns and approval-gated write/exec actions.

Currently supported:

- launches with `uv run work-copilot --tui`
- shows session/config state in the sidebar
- supports `/help`, `/status`, `/clear`, `/exit`, and `/quit`
- renders user prompts and model responses in the activity log
- preserves provider session context across turns
- renders runtime events through the Textual activity log
- prevents approval requests from falling back to terminal prompts
- shows a full-screen approval screen for write/exec approval requests
- supports Textual approval actions:
  - `y` allow once
  - `n` deny
  - `f` deny with feedback
  - `s` allow this tool for the session
  - `p` allow this path for the session, when a path is available
- renders structured approval diff previews with:
  - file/change summary header
  - old/new/marker/content columns
  - added and removed row backgrounds
  - marker column rendering
  - intra-line changed-span highlighting
- sets a terminal truecolor hint at startup so Textual colors render more consistently on modern terminals

Current limitations:

- streaming output is not implemented yet
- cancellation/interrupt handling is not implemented yet
- mouse/button approval controls are not implemented yet
- side-by-side diff view is not implemented yet
- multi-file diff navigation is not implemented yet
- provider/model selection inside the TUI is not implemented yet
- connector tools are not implemented yet

## Permission modes

The agent uses a permission layer before write/exec actions.

Current permission mode flag:

```bash
--permission-mode default
```

Available modes are defined by `PermissionMode` in `permissions.py`.

Typical behavior:

- read-only tools are allowed
- write/update tools ask for approval
- bash/exec tools ask for approval
- sensitive/protected paths are denied
- session-level tool approvals can be granted interactively
- session-level path approvals can be granted when a path is available
- terminal CLI modes use terminal approval prompts
- Textual mode uses the full-screen Textual approval screen

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

Related docs:

- [`docs/inspectors.md`](docs/inspectors.md) — read-only inspector architecture.
- [`docs/exchange_mailbox_inspector_client.md`](docs/exchange_mailbox_inspector_client.md) — Exchange mailbox inspector design.
- [`docs/exchange_real_inspector_smoke.md`](docs/exchange_real_inspector_smoke.md) — opt-in smoke test for the real read-only Exchange backend.

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

Textual approval/diff flow:

```text
textual_app.py
  -> textual_approval.py
  -> textual_approval_screen.py
  -> textual_diff_view.py
  -> textual_diff_renderer.py
  -> textual_preview.py
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