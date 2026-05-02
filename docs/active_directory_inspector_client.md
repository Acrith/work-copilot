# Active Directory inspector client design

This document describes the planned real backend for the read-only
`active_directory.user.inspect`, `active_directory.group.inspect`, and
`active_directory.group_membership.inspect` inspectors.

The inspector logic already depends on read-only client protocols
(`ActiveDirectoryUserInspectorClient`, `ActiveDirectoryGroupInspectorClient`,
`ActiveDirectoryGroupMembershipInspectorClient`) and consumes structured
snapshots. This design keeps Work Copilot independent from the backend used
to collect AD metadata.

## Goal

Implement a future real read-only client that can collect AD metadata needed
by:

- `active_directory.user.inspect`
- `active_directory.group.inspect`
- `active_directory.group_membership.inspect`

The client must return only structured metadata needed for planning. It must
not modify Active Directory and must not inspect passwords, password hashes,
LAPS material, BitLocker recovery keys, replication metadata, or other
sensitive attributes.

## Non-goals

This client must not:

- create, modify, or delete users or groups
- enable, disable, or unlock accounts
- add, remove, or modify group memberships
- reset passwords or change credentials
- move or rename objects
- modify retention, GPO links, OU structure, ACLs, or schema
- write ServiceDesk notes
- perform any external mutation

## Environment

This Work Copilot deployment runs on WSL on a workstation that is joined to
an on-prem Active Directory domain. The environment is hybrid:

- on-prem AD is the source of truth for users, groups, and memberships
- Microsoft 365 / Entra is identity-synced from on-prem AD
- manual changes are normally performed through ADUC against the on-prem
  domain controller

Because on-prem is the source of truth, the first real AD inspector backend
should target on-prem AD directly via the Windows PowerShell ActiveDirectory
module rather than starting with Microsoft Graph. Graph can be added later
as a separate client implementation if Entra-only attributes become
necessary.

## Backend choice

The first real backend should be the Windows PowerShell ActiveDirectory
module, behind the existing inspector client protocols.

Reasoning:

- on-prem AD is the source of truth in this environment
- the ActiveDirectory PowerShell module already exposes read-only `Get-AD*`
  cmdlets that match the metadata the inspectors need
- the same module is what technicians use today through ADUC's underlying
  tooling, so the inspector observes the same picture
- Microsoft Graph mailbox/user metadata does not cleanly cover all on-prem
  AD attributes (for example, `distinguishedName` in the on-prem domain,
  `sAMAccountName`, on-prem `manager`)

## Runtime topology

```
WSL Python (Work Copilot)
  -> subprocess: powershell.exe (Windows PowerShell 5.1) or pwsh (PS 7+)
     started via the WSL/Windows interop boundary
  -> Import-Module ActiveDirectory
  -> read-only Get-AD* cmdlets
  -> JSON via ConvertTo-Json
  -> Python parses JSON into structured snapshots
```

Notes:

- The ActiveDirectory module is a Windows module. It runs on the Windows
  side of WSL interop, not inside WSL Linux. Work Copilot launches it via
  `powershell.exe` (or `pwsh` from Windows) using the same kind of bounded
  subprocess pattern the Exchange inspector already uses.
- Domain authentication uses the workstation's existing Kerberos/AD
  context. The inspector does not store, prompt for, or echo credentials.
- No additional Windows-side service or scheduled task is required for
  read-only inspection.

## Stable interface

The rest of Work Copilot should continue to depend only on:

```text
ActiveDirectoryUserInspectorClient
ActiveDirectoryUserSnapshot
inspect_active_directory_user()

ActiveDirectoryGroupInspectorClient
ActiveDirectoryGroupSnapshot
inspect_active_directory_group()

ActiveDirectoryGroupMembershipInspectorClient
ActiveDirectoryGroupMembershipSnapshot
inspect_active_directory_group_membership()
```

The real backend should adapt on-prem AD data into these snapshot shapes.

## Planned client

Future class names (placeholder):

```text
ActiveDirectoryPowerShellUserClient
ActiveDirectoryPowerShellGroupClient
ActiveDirectoryPowerShellGroupMembershipClient
```

Future module:

```text
inspectors/active_directory_powershell.py
```

Each client implements the existing inspector client protocol. They share a
single `ActiveDirectoryCommandRunner` so command validation, subprocess
boundary, JSON parsing, and timeout handling live in one place.

## Read-only data to collect

Initial target fields:

User snapshot:

- user_identifier (UPN, sAMAccountName, or DN as resolved)
- display_name
- user_principal_name
- sam_account_name
- mail
- enabled
- distinguished_name
- department
- title
- manager (DN of the manager object, not nested user content)

Group snapshot:

- group_identifier (group name, sAMAccountName, or DN as resolved)
- name
- sam_account_name
- mail
- group_scope
- group_category
- distinguished_name
- member_count

Group-membership snapshot:

- user_identifier
- group_identifier
- is_member
- membership_source (for example, `direct` vs `inherited` when reliably
  derivable; otherwise omit)

This list deliberately stays close to existing snapshot fields. New fields
should be added behind a follow-up design change so the real backend cannot
silently widen the data surface.

## Allowed read-only Active Directory commands

Future implementation may use only the allowlisted read-only ActiveDirectory
PowerShell cmdlets:

- `Get-ADUser`
- `Get-ADGroup`
- `Get-ADPrincipalGroupMembership`

`Get-ADGroupMember` is intentionally **not** allowlisted in this phase. Full
group-member enumeration is broader than the membership inspector promises
(it claims `is_member` for one user/group pair, not full group rosters), and
on large groups it can be slow and noisy. If a future workflow genuinely
needs member listing, it should be added via a separate inspector and
allowlist change with explicit justification, not silently implied by the
membership inspector.

The runner must validate each command name before invoking any subprocess.
Any command not on the allowlist must be rejected before execution.

## Forbidden mutation prefixes

The runner must reject any command whose name starts with any of these
prefixes, regardless of whether the rest of the name happens to match an AD
cmdlet that exists today:

```text
Set-, New-, Remove-, Add-, Clear-, Enable-, Disable-, Unlock-, Move-,
Rename-, Reset-
```

This catches both AD-specific mutations (`Set-ADUser`, `New-ADGroup`,
`Remove-ADUser`, `Add-ADGroupMember`, `Enable-ADAccount`,
`Disable-ADAccount`, `Unlock-ADAccount`, `Set-ADAccountPassword`,
`Reset-ADServiceAccountPassword`) and generic-shaped commands that could
slip in via aliases.

The forbidden-prefix check runs *before* the allowlist check so even a
command like `Set-Get-ADUser` (defensive against weird names or typos)
fails fast.

## Authentication and secrets

The real client must not hardcode secrets and must not prompt for
credentials.

Authentication relies on the workstation's existing on-prem AD/Kerberos
context. The inspector:

- never reads or stores user passwords
- never inspects password attributes (`pwdLastSet`, `lockoutTime` only if
  added behind a separate design change; password hashes never)
- never echoes credentials to inspector JSON, run logs, stdout, stderr,
  approval previews, or ServiceDesk
- never inspects LAPS, BitLocker recovery, or replication metadata

Errors caused by missing AD permissions must be surfaced as a clear
`active_directory_user_inspection_failed` /
`active_directory_group_inspection_failed` error code without leaking
ticket context, account names, or environment details beyond the inspected
target.

## Runtime safety configuration

Real AD inspection must remain disabled unless explicitly configured.

Default behavior:

- backend: `mock`
- real external calls: disabled

Future real Active Directory PowerShell inspection requires both settings
to be explicitly enabled:

- `WORK_COPILOT_AD_INSPECTOR_BACKEND=active_directory_powershell`
- `WORK_COPILOT_ALLOW_REAL_AD_INSPECTOR=true`

This double opt-in prevents a partial or accidental configuration from
enabling real AD calls.

Supported backend modes:

- `mock`
- `disabled`
- `active_directory_powershell`

The `/sdp inspect-skill` workflow remains mock-only for AD until the real
runner is intentionally wired through this configuration gate.

## Inspector registry backend selection

The configured inspector registry follows the same pattern as Exchange:

- `mock`: registers mock AD inspectors (current behavior)
- `disabled`: registers no AD inspectors
- `active_directory_powershell`: registers the real read-only AD inspectors
  only when `WORK_COPILOT_ALLOW_REAL_AD_INSPECTOR=true`

Real AD mode must visibly log that on-prem Active Directory will be
contacted via PowerShell. Mock mode must visibly log that no external
systems were contacted.

The Exchange backend and the AD backend are independent: a deployment can
keep Exchange in mock mode while turning on real AD inspection, or vice
versa.

## Output and logging rules

Inspector output may include account/group metadata required for planning.

Inspector output must not include:

- passwords or password hashes
- LAPS material
- BitLocker recovery keys
- raw command transcripts
- raw `Get-AD*` output beyond the projected snapshot fields
- Kerberos tickets or other authentication tokens
- environment variables, credential paths, or secret-shaped values

Errors should be structured and concise.

## Error behavior

The client should map backend failures into existing inspector result
behavior:

- user not found → `active_directory_user_not_found`
- group not found → `active_directory_group_not_found`
- authentication/permission failure → `active_directory_user_inspection_failed`
  (or the corresponding group/membership variant)
- backend command failure → same generic `*_inspection_failed` codes
- incomplete data → partial result where useful facts can still be
  returned, never a full fabricated snapshot

Partial results are preferable when they reduce uncertainty without
creating false confidence.

## Testing strategy

Tests must not connect to Active Directory.

Use mock clients and mocked command runners. Test cases should cover:

- normal user/group/membership snapshots
- missing user, missing group, missing inputs
- backend command failures
- partial data
- no sensitive attributes in output
- no mutation commands accepted by the runner
- no secrets in output

## Future implementation phases

1. Design-only document (this document) and config/runner seams
2. Disabled adapter skeleton
3. Command runner implementation against `powershell.exe` / `pwsh`
4. Mocked PowerShell client tests
5. Real client behind explicit `active_directory_powershell` + double
   opt-in flags
6. Optional `/sdp inspect-skill` integration switch from mock to real
   client
7. Later approval-gated executors, separate from inspectors

## Out of scope for this phase

- Microsoft Graph or Entra-direct AD inspection
- Group member enumeration via `Get-ADGroupMember`
- Schema, GPO, replication, or topology inspection
- Any AD write or mutating cmdlet
- Cross-domain or cross-forest inspection
- Bulk inspection across many users in one call
