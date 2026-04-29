# Exchange mailbox inspector client design

This document describes the planned real backend for the read-only `exchange.mailbox.inspect` inspector.

The inspector logic already depends on the `ExchangeMailboxInspectorClient` protocol and consumes an `ExchangeMailboxSnapshot`. This design keeps Work Copilot independent from the backend used to collect Exchange mailbox metadata.

## Goal

Implement a future real read-only client that can collect mailbox metadata needed by:

- `exchange.mailbox.inspect`
- `exchange.archive.enable`
- `exchange.archive.enable_auto_expanding`

The client must return only structured metadata needed for planning. It must not inspect mailbox content or modify Exchange Online.

## Non-goals

This client must not:

- enable archive
- enable auto-expanding archive
- change retention policy
- change mailbox permissions
- delete mail
- inspect mail contents
- inspect attachments
- write ServiceDesk notes
- perform any external mutation

## Backend choice

The first real backend should be Exchange Online PowerShell, behind the existing `ExchangeMailboxInspectorClient` protocol.

Reasoning:

- Exchange mailbox size and message-count style statistics are exposed through Exchange Online PowerShell mailbox statistics.
- Mailbox object metadata is exposed through Exchange Online PowerShell mailbox lookup.
- Archive and auto-expanding archive verification are documented around Exchange Online PowerShell.
- Microsoft Graph mailbox settings do not expose all required Exchange admin archive/quota/statistics state.

Graph can still be useful later for user/profile-oriented inspection, but it should be a separate client implementation if needed.

## Stable interface

The rest of Work Copilot should continue to depend only on:

```text
ExchangeMailboxInspectorClient
ExchangeMailboxSnapshot
inspect_exchange_mailbox()
```

The real backend should adapt Exchange Online data into `ExchangeMailboxSnapshot`.

## Planned client

Future class name:

```text
ExchangeOnlinePowerShellMailboxClient
```

Future module:

```text
inspectors/exchange_online_powershell.py
```

The class should implement:

```python
def get_mailbox_snapshot(self, mailbox_address: str) -> ExchangeMailboxSnapshot:
    ...
```

## Read-only data to collect

Initial target fields:

- mailbox address
- display name
- primary SMTP address
- recipient type
- mailbox size
- item count
- archive status
- auto-expanding archive status
- retention policy
- quota warning status, if safely derivable

## Allowed read-only Exchange operations

Future implementation may use read-only Exchange Online PowerShell commands such as:

- mailbox object lookup
- mailbox statistics lookup
- archive status lookup
- retention policy lookup

The exact command list should be allowlisted in code before real execution is enabled.

## Forbidden operations

The real client must never invoke commands or APIs that mutate state, including but not limited to:

- `Enable-Mailbox`
- `Set-Mailbox`
- `Disable-Mailbox`
- `Remove-Mailbox`
- `Add-MailboxPermission`
- `Remove-MailboxPermission`
- `New-*`
- `Set-*`
- `Remove-*`
- any ServiceDesk write operation

## Mailbox creation boundary

In this environment, standard user mailboxes are normally created by provisioning
an Active Directory account and allowing identity synchronization/licensing to
create the Microsoft 365 mailbox. Exchange mailbox creation is not part of the
initial inspector/executor roadmap.

Mailbox creation, if ever needed, must be modeled as a separate high-risk skill
and must not be bundled into mailbox inspection, archive enablement, or shared
mailbox permission workflows.

## Authentication and secrets

The real client must not hardcode secrets.

Future authentication should be explicit and environment/config driven. Secrets must not be written to inspector JSON, run logs, stdout, stderr, or approval previews.

The first real adapter should be disabled by default until configuration and safety checks are in place.

## Runtime safety configuration

Real Exchange inspection must remain disabled unless explicitly configured.

Default behavior:

- backend: `mock`
- real external calls: disabled

Future real Exchange Online PowerShell inspection should require both settings:

- `WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND=exchange_online_powershell`
- `WORK_COPILOT_ALLOW_REAL_EXCHANGE_INSPECTOR=true`

This double opt-in prevents a partial or accidental configuration from enabling real external system calls.

Supported backend modes:

- `mock`
- `disabled`
- `exchange_online_powershell`

The `/sdp inspect-skill` workflow should remain mock-only until the real runner is intentionally wired through this configuration gate.

## Output and logging rules

Inspector output may include mailbox metadata required for planning.

Inspector output must not include:

- authentication secrets
- access tokens
- raw command transcripts containing sensitive environment details
- mailbox content
- message subjects/bodies
- attachment names/content unless a future design explicitly allows metadata-only handling

Errors should be structured and concise.

## Error behavior

The client should map backend failures into existing inspector result behavior:

- mailbox not found → `mailbox_not_found`
- authentication/configuration failure → `exchange_auth_unavailable`
- backend command failure → `exchange_mailbox_inspection_failed`
- incomplete data → `partial` result where useful facts can still be returned

Partial results are preferable when they reduce uncertainty without creating false confidence.

## Testing strategy

Tests must not connect to Exchange Online.

Use mock clients and mocked command runners.

Test cases should cover:

- normal mailbox snapshot
- missing mailbox
- backend failure
- partial data
- no content inspection
- no mutation commands
- no secrets in output

## Future implementation phases

1. Design-only client document
2. Disabled adapter skeleton
3. Command runner abstraction with allowlist tests
4. Mocked Exchange Online PowerShell client tests
5. Real client behind explicit config flag
6. Optional `/sdp inspect-skill` integration switch from mock to real client
7. Later approval-gated executors, separate from inspectors