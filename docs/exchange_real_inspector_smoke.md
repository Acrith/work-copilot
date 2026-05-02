# Real Exchange mailbox inspector smoke test

This document describes how to safely smoke-test the real, read-only
Exchange mailbox inspector backend. The default Work Copilot configuration
keeps the inspector in mock mode and does not contact Exchange Online.
Switching to the real backend is opt-in and must be done deliberately.

The real backend is read-only by design. It exists to gather mailbox
metadata for planning. It must never be used to inspect mailbox content,
attachments, message bodies, or to perform permission, archive, retention,
or any other mutating change. See
[`exchange_mailbox_inspector_client.md`](exchange_mailbox_inspector_client.md)
for the broader design and the explicit list of forbidden operations.

## Audience

This guide is for an operator with:

- a non-production Microsoft 365 tenant (or an isolated test mailbox)
- consent to run read-only Exchange Online discovery against that tenant
- an Azure AD application registered for app-only Exchange Online
  PowerShell access

If you do not have all three, stay in mock mode.

## Prerequisites

### Tools

- Python 3.13+ and `uv` (already required by Work Copilot)
- PowerShell 7 (`pwsh`) on the host where Work Copilot runs
- The `ExchangeOnlineManagement` PowerShell module installed for the user
  that will run `pwsh`
- A working `git` checkout of this repository

On WSL/Linux, install PowerShell 7 from Microsoft's official packages, then
install the Exchange module from a `pwsh` prompt:

```powershell
Install-Module ExchangeOnlineManagement -Scope CurrentUser
```

### Azure AD application

Create or reuse an Azure AD app registration with the minimum permissions
needed for Exchange Online PowerShell read access (typically
`Exchange.ManageAsApp` and an Exchange administrator role assignment in
the target tenant). Generate or import a certificate for the app and
record:

- the application (client) ID
- the tenant primary domain (e.g. `contoso.onmicrosoft.com`)
- the certificate, either as a thumbprint installed in a local certificate
  store (Windows only) or as a `.pfx` file plus a password (preferred on
  WSL/Linux)

Do not paste any of these values into the repository. They belong only in
your local `.env` file or, for the certificate password, in a separate
shell-exported environment variable.

## Safe `.env` setup

1. Copy the template:

   ```bash
   cp .env.example .env
   ```

2. Open `.env` and uncomment only the variables you actually need. Keep
   the file out of git. The repository's `.gitignore` rules ignore `.env`
   and `.env.*` while explicitly allowing `.env.example` to remain
   tracked.

3. Enable the real backend by setting both gating variables:

   ```env
   WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND=exchange_online_powershell
   WORK_COPILOT_ALLOW_REAL_EXCHANGE_INSPECTOR=true
   ```

   Both must be set. If only one is set the configuration loader refuses
   to register the real inspector.

4. On WSL/Linux, prefer the certificate-file auth mode:

   ```env
   WORK_COPILOT_EXCHANGE_AUTH_MODE=app_certificate_file
   WORK_COPILOT_EXCHANGE_APP_ID=<azure-ad-app-client-id>
   WORK_COPILOT_EXCHANGE_ORGANIZATION=<tenant>.onmicrosoft.com
   WORK_COPILOT_EXCHANGE_CERTIFICATE_PATH=/absolute/path/to/cert.pfx
   WORK_COPILOT_EXCHANGE_CERTIFICATE_PASSWORD_ENV_VAR=WORK_COPILOT_EXCHANGE_CERTIFICATE_PASSWORD
   ```

   Export the actual certificate password separately in the shell that starts
   Work Copilot:

   ```bash
   export WORK_COPILOT_EXCHANGE_CERTIFICATE_PASSWORD="<certificate-password>"
   ```

   On Windows hosts where the certificate is installed in the local
   certificate store, use `app_certificate_thumbprint` instead and set
   `WORK_COPILOT_EXCHANGE_CERTIFICATE_THUMBPRINT`.

5. Optionally tune the runner:

   ```env
   WORK_COPILOT_EXCHANGE_POWERSHELL_EXECUTABLE=pwsh
   WORK_COPILOT_EXCHANGE_POWERSHELL_TIMEOUT_SECONDS=60
   ```

Auth values must not be echoed to logs, stdout, approval previews, or
ServiceDesk notes. The runner deliberately keeps secrets out of inspector
output. If you observe a secret leaking, stop the smoke test and fix the
leak before continuing.

## Direct PowerShell sanity checks

Before involving Work Copilot, confirm that the credentials and module
work in a plain `pwsh` session. This isolates auth/network problems from
Work Copilot integration problems.

Open a new `pwsh` shell with the same environment your Work Copilot
process will see (sourcing `.env` if necessary), then run, substituting
your own values:

```powershell
Import-Module ExchangeOnlineManagement

# Certificate-file auth (preferred on WSL/Linux)
$certPassword = ConvertTo-SecureString `
  -String $env:WORK_COPILOT_EXCHANGE_CERTIFICATE_PASSWORD `
  -AsPlainText -Force

Connect-ExchangeOnline `
  -AppId $env:WORK_COPILOT_EXCHANGE_APP_ID `
  -Organization $env:WORK_COPILOT_EXCHANGE_ORGANIZATION `
  -CertificateFilePath $env:WORK_COPILOT_EXCHANGE_CERTIFICATE_PATH `
  -CertificatePassword $certPassword `
  -ShowBanner:$false

# Read-only sanity calls against a known test mailbox.
Get-EXOMailbox -Identity 'test.user@contoso.onmicrosoft.com'
Get-EXOMailboxStatistics -Identity 'test.user@contoso.onmicrosoft.com'

Disconnect-ExchangeOnline -Confirm:$false
```

Only run read-only `Get-*` cmdlets here. Do not run any `New-*`, `Set-*`,
`Enable-*`, `Disable-*`, `Add-*`, or `Remove-*` cmdlet against the
tenant during the smoke test. If a command other than the allowlisted
read-only set is needed, stop and revisit the design.

If these calls succeed and return expected metadata, the credentials and
network path are good and you can move to the Work Copilot smoke path. If
they fail, fix the underlying issue (consent, role assignment,
certificate, network) before involving Work Copilot, since the inspector
will surface the same failure with less detail.

## Work Copilot smoke path

The smoke path uses the existing `/sdp` workflow with a real
ServiceDesk Plus request that targets a single test mailbox. Pick a
ServiceDesk request whose required mailbox is the same test mailbox you
just verified directly.

1. Start an interactive Work Copilot session with the configured
   environment loaded:

   ```bash
   uv run work-copilot --interactive
   ```

2. Confirm the inspector backend by checking the session banner or
   resolved configuration. The startup output should indicate that the
   real Exchange backend is selected and that external Exchange Online
   will be contacted. If you see "mock" or "no external systems were
   contacted" wording, the real backend is not active and you should
   stop and re-check `.env` rather than re-running.

3. Build the read-only skill plan:

   ```text
   /sdp skill-plan <request_id>
   ```

   This step is local and does not call Exchange. It produces a plan
   that lists the mailbox(es) the inspector will look up.

4. Run the inspector(s) from that plan:

   ```text
   /sdp inspect-skill <request_id>
   ```

   With the real backend enabled, this issues only the allowlisted
   read-only Exchange Online PowerShell commands (mailbox lookup and
   mailbox statistics) for the mailbox(es) named in the plan. Watch the
   activity log for any unexpected command names or failure messages.

## Expected JSON output

Inspector results are written under the workspace at:

```text
.work_copilot/servicedesk/<request_id>/inspectors/<inspector_id>.json
```

For the mailbox inspector the inspector id is `exchange.mailbox.inspect`,
so the file is:

```text
.work_copilot/servicedesk/<request_id>/inspectors/exchange.mailbox.inspect.json
```

Expected payload characteristics:

- mailbox metadata fields (address, display name, primary SMTP, recipient
  type, size, item count, archive status, retention policy, etc.)
- no message subjects, bodies, or attachment data
- no app id, tenant, certificate path, thumbprint, or password values
- no full PowerShell command transcripts

If you see anything outside that envelope, treat it as a defect and stop.

The `.work_copilot/servicedesk/` directory is git-ignored, but the JSON
files may still contain mailbox metadata for a real user. Treat them as
sensitive and delete them when the smoke test is finished.

## Rollback to mock mode

To revert to the safe default at any point, edit `.env` and set:

```env
WORK_COPILOT_EXCHANGE_INSPECTOR_BACKEND=mock
WORK_COPILOT_ALLOW_REAL_EXCHANGE_INSPECTOR=false
```

You can also fully disable the inspector by setting the backend to
`disabled`, in which case `/sdp inspect-skill` will run with no Exchange
inspector registered.

You do not need to remove the auth variables to roll back, but clearing
`WORK_COPILOT_EXCHANGE_AUTH_MODE` (or setting it to `disabled`) is a good
extra precaution while not actively smoke-testing. After editing `.env`,
restart the Work Copilot session so the new environment is picked up,
and confirm the next run reports mock mode.

## Safety warnings

- Use a non-production tenant or an explicitly authorized test mailbox.
  Do not point the smoke test at arbitrary user mailboxes.
- The real backend must remain read-only. The runner allowlists only
  `Get-EXOMailbox`, `Get-EXOMailboxStatistics`, and `Get-Mailbox`. Do not
  expand this list as part of a smoke test.
- Never inspect mailbox content, message subjects/bodies, or attachments
  through this path, even if PowerShell would technically allow it.
- Never commit `.env`, certificate files, or inspector JSON output. The
  `.gitignore` rules cover `.env*` (except `.env.example`) and
  `.work_copilot/`, but double-check `git status` before committing.
- Treat any leakage of auth values into logs, previews, or JSON output as
  a stop-the-line defect.
- When the smoke test is finished, roll back to mock mode and remove or
  rotate any test credentials that no longer need to exist.
