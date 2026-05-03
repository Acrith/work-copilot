# Real Active Directory inspector smoke test

This document describes how to safely smoke-test the real, read-only
Active Directory inspector backend. The default Work Copilot configuration
keeps the AD inspectors in mock mode and does not contact Active Directory.
Switching to the real backend is opt-in and must be done deliberately.

The real backend is read-only by design. It exists to gather basic AD
account/group metadata for planning. It must never be used to inspect
passwords, LAPS, BitLocker, raw memberOf, directReports, photos, home
directories, logon scripts, or any other sensitive attribute, and it must
never be used to mutate Active Directory. See
[`active_directory_inspector_client.md`](active_directory_inspector_client.md)
for the broader design and the explicit list of forbidden operations.

## Lessons learned from the first successful smoke test

These are recorded after the first end-to-end successful smoke test
against a real on-prem AD domain. They are practical hints, not new
rules — the safety contract above is unchanged.

- **VPN / domain connectivity matters.** `Import-Module ActiveDirectory`
  can succeed on a workstation that is not currently reachable to a
  domain controller (the module loads from the local RSAT install).
  Cmdlets like `Get-ADUser`, `Get-ADGroup`, and
  `Get-ADPrincipalGroupMembership` will then fail at call time with
  domain-unreachable errors rather than at import time. If the smoke
  test fails after `Import-Module` succeeds, check that the workstation
  has a working domain connection (corporate network, VPN, or
  domain-joined session) before debugging Work Copilot.
- **Use Windows-side `powershell.exe` from WSL by default.** The Linux
  `pwsh` package does not ship the `ActiveDirectory` module and cannot
  satisfy `Import-Module ActiveDirectory`. Work Copilot's default
  `WORK_COPILOT_AD_POWERSHELL_EXECUTABLE=powershell.exe` is correct;
  only override it with a Windows-side path (for example
  `/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe`) when
  WSL interop cannot resolve `powershell.exe` directly.
- **Identity intent differs by system.** Active Directory inspectors
  generally prefer SAM/account-style identifiers (for example
  `name.surname`, distinguished name, or `sAMAccountName`). Exchange /
  mailbox inspectors generally prefer SMTP / email identifiers (for
  example `name.surname@contoso.com`). When the requester email and
  the target are different, only treat the email as the inspection
  target if the request body explicitly says so. Work Copilot's
  skill-plan prompt enforces this, and the AD user/membership clients
  also resolve email/UPN inputs through `Get-ADUser -LDAPFilter "(|(userPrincipalName=...)(mail=...))"`
  rather than passing them as `-Identity` directly.
- **Combined inspection reports are expected when multiple inspectors
  run.** With three AD inspectors selected (user, group,
  group_membership), `/sdp inspection-report <id>` produces one
  combined report containing per-inspector sections plus an overall
  status. Single-inspector runs still produce the familiar
  single-section report.
- **Combined draft notes use nested Markdown bullets.** For combined
  reports, `/sdp draft-note <id>` is expected to render `Findings:`
  with nested groupings:

  ```text
  Findings:
  - User:
    - User exists: yes
    - ...
  - Group:
    - Group exists: yes
    - ...
  - Membership:
    - User identifier: ...
    - Is member: yes
  ```

  This keeps Rich/Textual Markdown rendering clean and avoids the
  "User: Group: Membership:" inline collapsing that flat top-level
  labels produce.
- **Group scope and category render as readable enum names.** Expect
  values like `Global`, `Universal`, `DomainLocal` for `group_scope`
  and `Security`, `Distribution` for `group_category` — not raw
  numeric values like `1` / `2`. The PowerShell projection casts both
  through `.ToString()` before serialization. If you ever see a raw
  number in inspector JSON, treat that as a regression.

### Read-only invariants confirmed by the smoke test

- No `Get-ADGroupMember`. Group member enumeration is intentionally
  out of scope; group_membership is checked one user/group pair at a
  time via `Get-ADPrincipalGroupMembership` against the user.
- No `-Properties *`. The user inspector only requests the explicit
  safe profile/contact field set declared in the script builder.
- No AD writes. The runner allowlist contains only `Get-ADUser`,
  `Get-ADGroup`, and `Get-ADPrincipalGroupMembership`. The forbidden
  prefixes (`Set-`, `New-`, `Remove-`, `Add-`, `Clear-`, `Enable-`,
  `Disable-`, `Unlock-`, `Move-`, `Rename-`, `Reset-`) are rejected
  before any subprocess is started.
- No sensitive attributes. The script builder excludes passwords,
  LAPS, BitLocker, raw `memberOf`, `directReports`, `thumbnailPhoto`,
  `homeDirectory`, `scriptPath`, and similar.
- No raw PowerShell transcripts in inspector JSON, reports, draft
  notes, or TUI summaries. Errors are sanitized before they reach the
  user-facing path.

## Successful smoke path

A successful real-AD smoke run looks like this, given a ServiceDesk
request with one user identifier and one group identifier in the
request body:

```text
/sdp context <request_id>
/sdp skill-plan <request_id>
/sdp inspect-skill <request_id>
/sdp inspection-report <request_id>
/sdp draft-note <request_id>
/sdp save-note <request_id>
```

Each step is local-only until `/sdp save-note`, which is
approval-gated and posts only the `## Note body` section of the
generated draft as an internal ServiceDesk note. Up to and including
`/sdp draft-note`, no ServiceDesk write happens.

`/sdp save-note <request_id>` runs a local draft-note validation
pass before the approval-gated write path. Validation is local-only:
it does not call the model, does not contact AD or Exchange, does
not run inspectors, and does not post anything. It blocks the save
when the draft has no `## Note body`, an empty body, leftover
placeholder text (`TODO`, `TBD`, `<fill in>`, `[fill in>`,
`lorem ipsum`), or explicit first-person write claims such as
`I changed Active Directory`, `I updated Active Directory`,
`I modified the mailbox`, or `I enabled archive` — the AD inspectors
in this smoke flow are read-only, so the draft must not claim
otherwise. When validation passes, the existing approval flow runs
unchanged.

The same flow can also be driven one safe step at a time using the
state-driven workflow commands:

```text
/sdp status <request_id>
/sdp work <request_id>
/sdp work <request_id>
...
/sdp save-note <request_id>
```

`/sdp work` reuses the same per-step commands and the same safety
gates. It advances exactly one step per invocation, never auto-saves
notes, and stops before the ServiceDesk write boundary so the operator
can review the local draft and explicitly run `/sdp save-note
<request_id>`. `/sdp continue <request_id>` is an alias for `/sdp work
<request_id>`.

If `latest_skill_plan.md` is newer than its sidecars (for example,
after a manual edit), `/sdp work <request_id>` will first run a local
sidecar refresh from the existing Markdown. The refresh does not call
the model, does not contact AD or Exchange, and does not run
inspectors; it just rewrites
`latest_skill_plan_validation.json` and `latest_skill_plan.json` from
the current Markdown so the next `/sdp work <request_id>` step sees
consistent structured data.

Explicit `/sdp inspect-skill <request_id>` performs the same local
sidecar refresh first when `latest_skill_plan.json` is missing, stale,
or unreadable, then reloads the structured sidecar. If the reload
produces a usable structured plan, inspection runs on the structured
path; otherwise it falls back to parsing `latest_skill_plan.md`
directly. Validation still runs before any AD inspector executes, and
the refresh itself does not contact AD or Exchange and does not run
any inspector.

Workflow state also tracks freshness of downstream artifacts. If any
saved AD inspector output under `.work_copilot/servicedesk/<request_id>/inspectors/`
is newer than `inspection_report.md`, `/sdp status <request_id>` shows
`- inspection report: yes (stale)` and `/sdp work <request_id>`
recommends `/sdp inspection-report <request_id>` to rebuild the
report. If `inspection_report.md` is newer than `draft_note.md`, the
draft is flagged stale and `/sdp work <request_id>` recommends
`/sdp draft-note <request_id>` to regenerate it. These freshness
checks are local-only timestamp comparisons and never contact AD or
Exchange, never run an inspector, and never write to ServiceDesk.
`/sdp work` still advances one step per invocation, and
`/sdp save-note <request_id>` remains the explicit approval-gated
write boundary.

## Known limitations after smoke test

- **No AD writes.** Real AD inspection is read-only. Mutating skills
  remain draft-only and approval-gated when they exist, and they do
  not run through this inspector path.
- **No `Get-ADGroupMember` enumeration.** Full group rosters are out
  of scope. Use the membership inspector to check one user/group pair
  at a time.
- **`membership_source` is `direct_or_nested_unknown`.** The runner
  uses `Get-ADPrincipalGroupMembership` against the user, which can
  include nested membership. The inspector reports membership as
  effective rather than overclaiming direct membership.
- **No cross-domain / cross-forest support yet.** The runner targets
  the workstation's primary on-prem AD context. Trusts and remote
  forests are not in scope for this phase.
- **Generated local reports contain real account/group metadata.**
  `inspection_report.md`, `draft_note.md`, and the per-inspector JSON
  files live under `.work_copilot/servicedesk/<request_id>/` and must
  not be committed. The repository's `.gitignore` already excludes
  `.work_copilot/`, but double-check `git status` before any commit.

## Audience

This guide is for an operator with:

- a non-production Active Directory test user and test group, or explicit
  authorization to read-inspect specific production accounts
- a Windows workstation joined to the target on-prem AD domain
- Work Copilot running on WSL on that workstation
- the Windows-side `ActiveDirectory` PowerShell module installed (RSAT)
- existing on-prem AD/Kerberos context that already lets the workstation
  user run read-only `Get-AD*` cmdlets through ADUC tooling

If you do not have all of the above, stay in mock mode.

## Prerequisites

### Tools

- Python 3.13+ and `uv` (already required by Work Copilot)
- WSL Linux distribution with Work Copilot installed
- Windows-side `powershell.exe` reachable from WSL via interop
- Windows-side `ActiveDirectory` PowerShell module (part of RSAT)
- A working `git` checkout of this repository

### Windows RSAT / ActiveDirectory module

The on-prem AD cmdlets ship with the Remote Server Administration Tools
(RSAT) "Active Directory module for Windows PowerShell". Confirm it is
installed on the Windows side:

- Windows 10/11: Settings → Apps → Optional features → "RSAT: Active
  Directory Domain Services and Lightweight Directory Services Tools"
- Windows Server: Server Manager → Add Roles and Features → AD DS Tools

You can verify the module is available by running, in a regular Windows
PowerShell window:

```powershell
Get-Module -ListAvailable ActiveDirectory
```

If the module is missing, install RSAT first. Do not attempt to work
around a missing module by routing through a different cmdlet set.

### powershell.exe from WSL

Work Copilot runs in WSL and shells out to Windows-side PowerShell via
WSL/Windows interop. From a WSL terminal, confirm `powershell.exe` is
reachable and the AD module is importable:

```bash
powershell.exe -NoProfile -NonInteractive -Command \
  "Import-Module ActiveDirectory; Get-Command Get-ADUser | Select-Object -First 1"
```

You should see a single `Get-ADUser` command line back. If the command is
not found, find the absolute path to the Windows PowerShell executable
(commonly
`/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe`) and use
that path in the `.env` setting below.

PowerShell 7 (`pwsh.exe`) on the Windows side will also work as long as
the `ActiveDirectory` module is installed for that PowerShell instance.
Stick to Windows PowerShell 5.1 (`powershell.exe`) unless you have a
specific reason to switch — the script builder is already compatible
with 5.1.

### Authentication

Authentication relies on the workstation's existing on-prem AD/Kerberos
context. The inspector does not store, prompt for, or echo credentials.
If `Get-ADUser` runs interactively for you in a Windows PowerShell
window, the inspector will run with the same identity.

## Safe `.env` setup

1. Copy the template if you do not already have a local `.env`:

   ```bash
   cp .env.example .env
   ```

2. Open `.env` and uncomment only the variables you need. The
   repository's `.gitignore` rules ignore `.env` and `.env.*` while
   explicitly allowing `.env.example` to remain tracked.

3. Enable the real AD backend by setting both gating variables:

   ```env
   WORK_COPILOT_AD_INSPECTOR_BACKEND=active_directory_powershell
   WORK_COPILOT_ALLOW_REAL_AD_INSPECTOR=true
   ```

   Both must be set. If only one is set the configuration loader refuses
   to register the real AD inspectors.

4. Tune the runner if needed:

   ```env
   WORK_COPILOT_AD_POWERSHELL_EXECUTABLE=powershell.exe
   WORK_COPILOT_AD_POWERSHELL_TIMEOUT_SECONDS=60
   ```

   On WSL, `powershell.exe` is usually resolvable through Windows
   interop. If it is not, set the absolute path explicitly:

   ```env
   WORK_COPILOT_AD_POWERSHELL_EXECUTABLE=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
   ```

5. AD and Exchange backends are independent. You can keep Exchange in
   mock mode while turning on real AD inspection, or vice versa. There
   is no shared opt-in flag.

The runner deliberately keeps secrets out of inspector output. If you
observe a secret-looking value leaking, stop the smoke test and fix the
leak before continuing.

## Direct PowerShell sanity checks

Before involving Work Copilot, confirm the on-prem AD path works in a
plain `powershell.exe` session. This isolates module/permission/network
problems from Work Copilot integration problems.

Open a new `powershell.exe` from WSL with the same environment your Work
Copilot process will see, then run, substituting your own values:

```powershell
Import-Module ActiveDirectory

# Replace with one known test user and one safe test group only.
$testUser  = 'test.user'
$testGroup = 'Test-Group'

# Read-only sanity calls.
Get-ADUser  -Identity $testUser  -Properties DisplayName, UserPrincipalName, Enabled |
    Format-List DisplayName, UserPrincipalName, Enabled

Get-ADGroup -Identity $testGroup |
    Format-List Name, SamAccountName, GroupScope, GroupCategory, DistinguishedName

Get-ADPrincipalGroupMembership -Identity $testUser |
    Select-Object -First 5 Name, SamAccountName, DistinguishedName
```

Only run read-only `Get-AD*` cmdlets here. Do not run any `Set-`, `New-`,
`Remove-`, `Add-`, `Clear-`, `Enable-`, `Disable-`, `Unlock-`, `Move-`,
`Rename-`, or `Reset-` AD cmdlet against the directory during the smoke
test.

Specifically:

- Do **not** run `Get-ADGroupMember`. The inspector does not enumerate
  group members; it only checks whether one user belongs to one group.
- Do **not** request `-Properties *` or any password/LAPS/BitLocker/
  memberOf/directReports/thumbnailPhoto/homeDirectory/scriptPath
  attribute. The Work Copilot script projects an explicit safe set;
  match that surface in your sanity checks.
- Use one test user and one test group. Do not bulk-inspect.

If these calls succeed and return expected metadata, the workstation,
module, and permissions are good and you can move to the Work Copilot
smoke path. If they fail, fix the underlying issue before involving Work
Copilot, since the inspector will surface the same failure with less
detail.

## Work Copilot smoke flow

Pick a ServiceDesk request whose required user and (optionally) group
are the same test user/group you just verified directly.

1. Start an interactive Work Copilot session with the configured
   environment loaded:

   ```bash
   uv run work-copilot --interactive
   ```

2. Confirm the inspector backends. The startup output should indicate
   that AD is on the real backend and that on-prem AD will be contacted
   via PowerShell. If you see "mock" or "no external systems were
   contacted" wording for AD, the real backend is not active and you
   should stop and re-check `.env` rather than re-running.

3. Save ServiceDesk context locally:

   ```text
   /sdp context <request_id>
   ```

4. Build the read-only skill plan:

   ```text
   /sdp skill-plan <request_id>
   ```

   This step is local and does not call AD. It produces a plan whose
   "Suggested inspector tools" line should reference one of the
   registered AD inspector ids:

   - `active_directory.user.inspect`
   - `active_directory.group.inspect`
   - `active_directory.group_membership.inspect`

5. Run the inspectors from that plan:

   ```text
   /sdp inspect-skill <request_id>
   ```

   With the real AD backend enabled, this issues only the allowlisted
   read-only PowerShell cmdlets (`Get-ADUser`, `Get-ADGroup`,
   `Get-ADPrincipalGroupMembership`) for the user/group named in the
   plan. Watch the activity log for any unexpected command names or
   failure messages.

6. Render the local Markdown inspection report:

   ```text
   /sdp inspection-report <request_id>
   ```

7. Optionally draft an internal technician note:

   ```text
   /sdp draft-note <request_id>
   ```

   Drafts are local-only until you choose to post them.

   Immediately after writing `draft_note.md`, `/sdp draft-note` runs
   the same local draft-note validation pass that `/sdp save-note`
   uses. A clean draft logs `Draft note validation: no issues
   found.`; an invalid draft logs the findings plus `Draft note has
   validation errors. Regenerate or edit the draft before saving.`
   The post-generation validation does not call the model again,
   does not contact AD or Exchange, does not run inspectors, and
   does not save anything to ServiceDesk. Invalid drafts remain
   local — inspect `draft_note.md`, edit it directly, or re-run
   `/sdp draft-note <request_id>`. `/sdp save-note <request_id>`
   remains the explicit approval-gated ServiceDesk write boundary.

## Expected local output

Inspector results are written under the workspace at:

```text
.work_copilot/servicedesk/<request_id>/inspectors/<inspector_id>.json
```

For the AD inspectors:

```text
.work_copilot/servicedesk/<request_id>/inspectors/active_directory.user.inspect.json
.work_copilot/servicedesk/<request_id>/inspectors/active_directory.group.inspect.json
.work_copilot/servicedesk/<request_id>/inspectors/active_directory.group_membership.inspect.json
```

The Markdown report and draft note land at:

```text
.work_copilot/servicedesk/<request_id>/inspection_report.md
.work_copilot/servicedesk/<request_id>/draft_note.md
```

Expected payload characteristics:

- AD user JSON contains `user_exists`, plus optional `display_name`,
  `first_name`, `last_name`, `user_principal_name`, `sam_account_name`,
  `mail`, `enabled`, `distinguished_name`, `department`, `title`,
  `office`, `office_phone`, `mobile_phone`, `manager`.
- AD group JSON contains `group_exists`, plus optional `name`,
  `sam_account_name`, `mail`, `group_scope`, `group_category`,
  `distinguished_name`, `member_count`.
- AD group-membership JSON contains `is_member`,
  `membership_source` (typically `direct_or_nested_unknown`),
  `user_identifier`, `group_identifier`.
- No password attributes, password hashes, LAPS material, BitLocker
  recovery, raw `memberOf`, `directReports`, `thumbnailPhoto`,
  `homeDirectory`, `scriptPath`, Kerberos tickets, or auth/credential
  values appear anywhere.
- No raw `Get-AD*` transcripts.

If you see anything outside that envelope, treat it as a defect and stop.

The `.work_copilot/servicedesk/` directory is git-ignored, but the JSON
files and report contain real account/group metadata. Treat them as
sensitive and delete them when the smoke test is finished.

## Rollback to mock mode

To revert to the safe default at any point, edit `.env` and set:

```env
WORK_COPILOT_AD_INSPECTOR_BACKEND=mock
WORK_COPILOT_ALLOW_REAL_AD_INSPECTOR=false
```

You can also fully disable AD inspection by setting the backend to
`disabled`, in which case `/sdp inspect-skill` will not run any AD
inspectors.

After editing `.env`, restart the Work Copilot session so the new
environment is picked up, and confirm the next run reports mock mode.

## Safety warnings

- Use one known test user and one known test group. Do not point the
  smoke test at arbitrary production accounts.
- The real backend must remain read-only. The runner allowlists only
  `Get-ADUser`, `Get-ADGroup`, and `Get-ADPrincipalGroupMembership`. Do
  not expand this list as part of a smoke test.
- Never inspect passwords, LAPS, BitLocker recovery, raw `memberOf`,
  `directReports`, `thumbnailPhoto`, `homeDirectory`, `scriptPath`, or
  similar sensitive attributes through this path, even if PowerShell
  would technically allow it.
- Never run `Get-ADGroupMember`. Membership is checked one user/group
  pair at a time via `Get-ADPrincipalGroupMembership` against the user.
- Never commit `.env`, exported `.work_copilot/servicedesk/` JSON, or
  generated reports/notes. The `.gitignore` covers them, but
  double-check `git status` before committing.
- Treat any leakage of secret/auth values into logs, previews, or JSON
  output as a stop-the-line defect.
- When the smoke test is finished, roll back to mock mode and clean up
  any local result files that no longer need to exist.

## Troubleshooting

### `Import-Module ActiveDirectory` fails with "module not found"

RSAT is not installed (or not installed for the PowerShell host you are
calling). On Windows 10/11, install the RSAT optional feature
"Active Directory Domain Services and Lightweight Directory Services
Tools". On Windows Server, install the AD DS tools via Server Manager.
Verify with `Get-Module -ListAvailable ActiveDirectory` in a regular
Windows PowerShell window.

### `powershell.exe: command not found` from WSL

Windows interop is not finding `powershell.exe` on `$PATH`. Set an
absolute path in `.env`:

```env
WORK_COPILOT_AD_POWERSHELL_EXECUTABLE=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
```

Confirm the file exists from WSL with `ls` before retrying. If WSL
interop itself is disabled, re-enable it via the WSL configuration on
the Windows host.

### "Cannot find an object with identity" / "not found"

The user or group identifier did not match any AD object. Try the
sAMAccountName, the UserPrincipalName, or the distinguished name. The
inspector reports this as `active_directory_user_not_found` /
`active_directory_group_not_found` rather than a generic error.

### Permission errors / "Access denied"

Your workstation's AD context does not have read access to the requested
object. Confirm read access through ADUC first; the inspector cannot
elevate. The error surfaces as
`active_directory_user_inspection_failed` or the group/membership
variant.

### Long-running command times out

Increase `WORK_COPILOT_AD_POWERSHELL_TIMEOUT_SECONDS` if the directory
is genuinely slow. Do not raise the timeout to mask a different
underlying problem.

### "Invalid JSON output"

The PowerShell process exited cleanly but the stdout was not valid JSON.
This usually means a Windows-side profile or banner is polluting stdout.
Work Copilot already passes `-NoProfile -NonInteractive`, so check
whether RSAT or another module is printing extra messages on import. If
so, fix or suppress the offending import on the Windows side.

### Mismatch between mock and real output

Mock AD output is intentionally placeholder-shaped. If you compare a
real AD result against a mock-mode result, expect mock fields like
`mock_unknown` to be missing in the real result. That is by design.
