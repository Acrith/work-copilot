# Work Copilot

Personal AI agent development project.

Work Copilot is a local terminal-based coding/workspace agent. It can inspect files, search code, run tests, execute approved shell commands, and make approved file changes inside a selected workspace.

This is a learning/development project. Do not treat it as production-ready automation.

## Current capabilities

- Gemini and OpenAI provider support
- Provider-neutral agent runtime
- Provider-neutral tool registry and tool dispatch
- Permission-gated write and exec actions
- Rich terminal output
- File read/search/list tools
- File write/update tools with previews
- Bash tool with approval flow
- Git inspection tools
- Test runner tool
- Token usage summary
- Configurable max agent iterations

## Requirements

- Python
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

## Basic usage

Run with the default provider:

```bash
uv run main.py --workspace . "List files in the workspace root and stop after listing them."
```

Run with Gemini explicitly:

```bash
uv run main.py --workspace . --provider gemini "Say hello and stop."
```

Run with OpenAI:

```bash
uv run main.py --workspace . --provider openai --model gpt-5.4-mini "Say hello and stop."
```

Cheap OpenAI smoke test:

```bash
uv run main.py --provider openai --model gpt-5.4-nano "Say hello and stop."
```

## Provider and model configuration

You can choose provider/model using CLI flags:

```bash
uv run main.py --provider openai --model gpt-5.4-mini "Say hello."
```

Or with environment variables:

```env
WORK_COPILOT_PROVIDER="openai"
WORK_COPILOT_MODEL="gpt-5.4-mini"
```

Defaults:

```text
Provider: gemini
Gemini model: gemini-2.5-flash
OpenAI model: gpt-5.4-mini
```

Gemini remains the default provider so OpenAI usage is explicit unless overridden.

## Useful commands

List files:

```bash
uv run main.py --workspace . "List files in the workspace root and stop after listing them."
```

Run tests through the agent:

```bash
uv run main.py --workspace . "Run the test suite."
```

Run a bash command with approval:

```bash
uv run main.py --workspace . "Run bash command echo hello"
```

Use verbose mode:

```bash
uv run main.py --workspace . --verbose "Say hello and stop."
```

Limit model/tool loop iterations:

```bash
uv run main.py --workspace . --max-iterations 3 "Inspect the project and summarize it."
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
- write/update tools ask for approval
- bash/exec tools ask for approval
- sensitive/protected paths are denied
- session-level approvals can be granted interactively

## Usage summary

At the end of a run, the agent prints token usage when the provider returns usage metadata:

```text
Usage: input=1976 output=8 total=1984 tokens
```

With `--verbose`, per-turn usage is also printed.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the current provider/tool/runtime structure.

High-level flow:

```text
main.py
  -> providers/factory.py
  -> agent_runtime.py
  -> providers/<provider>.py
  -> tool_registry.py
  -> tool_dispatch.py
  -> functions/*.py
```

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
uv run pytest
uv run ruff check .
```

## Notes

This project is intentionally evolving step by step.

Recent milestones:

- provider-neutral tool registry and dispatch
- Gemini provider extraction
- OpenAI provider implementation
- OpenAI tool calling support
- provider selection through CLI/factory
- usage summary and max iteration controls
- provider error handling

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