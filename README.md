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
- real read-only Active Directory inspectors (user, group, group
  membership), opt-in behind explicit double opt-in and documented in
  [`docs/active_directory_real_inspector_smoke.md`](docs/active_directory_real_inspector_smoke.md)

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

## ServiceDesk workflow

Work Copilot has a state-driven ServiceDesk workflow that prepares an
internal technician note for a ServiceDesk request without writing to
ServiceDesk, Active Directory, or Exchange until the operator explicitly
approves the final write.

The recommended workflow per request is:

```text
/sdp status <id>
/sdp work <id>
/sdp work <id>
...
/sdp save-note <id>
```

`/sdp work` advances exactly one safe next step per invocation. It can
walk through:

- context summary
- skill plan
- skill-plan validation and repair
- read-only inspection
- inspection report
- draft note

It stops before the ServiceDesk write boundary and tells the operator to
review the local draft and explicitly run `/sdp save-note <id>` if
approved.

### Recommended commands

- `/sdp status <id>`
  - Shows local workflow state and the suggested next command.
  - Local/read-only state display only.
  - Does not contact ServiceDesk, Active Directory, or Exchange.
  - Does not run the model or any inspectors.
- `/sdp work <id>`
  - Advances the request by exactly one safe next workflow step.
  - Uses local workflow state to decide the next action.
  - Reuses the existing per-step command handlers and safety gates.
  - May perform local, model, or read-only inspector work depending on
    the next step.
  - Does not run the whole pipeline in one invocation.
  - Never auto-saves notes to ServiceDesk.
  - At the ready-to-save stage, prints guidance to review the local
    draft and explicitly run `/sdp save-note <id>`.
- `/sdp continue <id>`
  - Alias for `/sdp work <id>`.
- `/sdp save-note <id>`
  - Explicit approval-gated ServiceDesk write boundary.
  - Posts the prepared internal note as a ServiceDesk note only when
    the operator intentionally runs this command and approves the
    write.

### Lower-level commands

The per-step commands still exist for advanced, manual, or debugging
use, and `/sdp work` reuses them internally:

- `/sdp context <id>`
- `/sdp skill-plan <id>`
- `/sdp repair-skill-plan <id>`
- `/sdp inspect-skill <id>`
- `/sdp inspection-report <id>`
- `/sdp draft-note <id>`

### Local state on disk

Per-request workflow artifacts live under the workspace at:

```text
.work_copilot/servicedesk/<request_id>/
```

Key artifacts:

- `latest_context.md` — saved ServiceDesk context summary.
- `latest_skill_plan.md` — human-readable skill plan. Editable by the
  operator.
- `latest_skill_plan_validation.json` — validation state (findings and
  `has_errors`) for the current skill plan.
- `latest_skill_plan.json` — structured parsed skill-plan data,
  generated by code from `latest_skill_plan.md`. The model is not
  asked to produce this file directly.
- `inspectors/<inspector_id>.json` — saved inspector outputs.
- `inspection_report.md` — local Markdown report rendered from the
  saved inspector outputs.
- `draft_note.md` — local internal technician note draft.

These files are local-only. Up to and including `/sdp draft-note`, no
ServiceDesk, Active Directory, or Exchange write happens.

### Skill-plan sidecars and local refresh

`latest_skill_plan.md` is the source of truth for the plan. The two
sidecars next to it (`latest_skill_plan_validation.json` and
`latest_skill_plan.json`) are derived from the Markdown by code; they
are not produced by the model and they should not be edited by hand.

`/sdp skill-plan <id>` and `/sdp repair-skill-plan <id>` rewrite both
sidecars whenever the Markdown plan changes.

If the Markdown is newer than either sidecar (for example, after the
operator manually edited `latest_skill_plan.md`), workflow state treats
the affected sidecar as untrusted. In that case `/sdp status <id>` and
`/sdp work <id>` recommend a local sidecar refresh from the existing
Markdown:

- `/sdp work <id>` re-parses `latest_skill_plan.md` from disk and
  rewrites both sidecars.
- The refresh runs locally only.
- The refresh does not call the model.
- The refresh does not contact ServiceDesk, Active Directory, or
  Exchange.
- The refresh does not run any inspectors.
- The refresh preserves manual edits to `latest_skill_plan.md`.

After the refresh, the next `/sdp work <id>` invocation continues with
the next safe step.

### Skill-plan sidecars and inspection

`/sdp inspect-skill <id>` prefers a fresh, readable
`latest_skill_plan.json` for validation, inspector selection, and
inspector request building. When the structured sidecar is missing,
stale, or unreadable, `/sdp inspect-skill` first attempts a local
sidecar refresh from `latest_skill_plan.md` and reloads
`latest_skill_plan.json`:

- the refresh runs locally only
- the refresh does not call the model
- the refresh does not contact ServiceDesk, Active Directory, or
  Exchange
- the refresh does not run any inspectors

If the reload now produces a usable structured plan,
`/sdp inspect-skill` continues on the structured path. If the
structured sidecar still cannot be used (for example, the Markdown is
unparseable), `/sdp inspect-skill` falls back to parsing
`latest_skill_plan.md` directly so the explicit command still works.

In both paths, validation runs before any inspector executes, and
inspector execution remains read-only.

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
- [`docs/active_directory_inspector_client.md`](docs/active_directory_inspector_client.md) — planned read-only Active Directory inspector backend design.
- [`docs/active_directory_real_inspector_smoke.md`](docs/active_directory_real_inspector_smoke.md) — opt-in smoke test for the real read-only Active Directory backend.

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