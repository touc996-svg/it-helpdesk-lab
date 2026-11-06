# ATLAS IT Support & Identity Operations Lab

An advanced, portfolio-oriented service desk and identity operations lab. The local foundation is a small FastAPI service backed by SQLite, with ticket lifecycle management, priority targets, asset inventory, knowledge articles, and ticket event history. Windows-specific exercises are provided as PowerShell scripts for a later Windows/Active Directory lab environment.

## Architecture

```text
Requester / IT Operator
        |
        v
FastAPI Service  ---- OpenAPI / Swagger UI
        |
        +---- Ticket lifecycle + priority targets
        +---- Ticket event history
        +---- Asset inventory
        +---- Knowledge articles
        |
        v
     SQLite database

Windows endpoint exercises (later lab phase)
        +---- Get-EndpointDiagnostics.ps1
        +---- New-ADUserBatch.ps1 (Windows Server / RSAT only)
```

## Local setup on macOS (Apple Silicon supported)

The local service uses SQLite and does not require Docker, Windows, or a virtual machine. This is intentionally lightweight for an 8 GB Mac.

```bash
cd ~/Projects/it-helpdesk-lab
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
export PYTHONPATH="$PWD/src"
python -m uvicorn it_helpdesk.main:app --reload --host 127.0.0.1 --port 18700
```

Open `http://127.0.0.1:18700/docs` for the interactive API. Health check: `http://127.0.0.1:18700/health`.

Run tests in another terminal:

```bash
cd ~/Projects/it-helpdesk-lab
source .venv/bin/activate
PYTHONPATH=src:. python -m pytest -q
```

Or use `scripts/run_local.sh` and `scripts/run_tests.sh`. To populate synthetic tickets, assets, and one knowledge article, open a second terminal and run `PYTHONPATH=src python scripts/seed_demo_data.py`. The seed script refuses to add demo records when the local database already contains records.

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Local service health |
| GET | `/api/v1/dashboard/summary` | Ticket, SLA, asset, and knowledge counts |
| POST | `/api/v1/tickets` | Create a ticket |
| GET | `/api/v1/tickets` | List and filter tickets |
| GET | `/api/v1/tickets/{ticket_key}` | Retrieve a ticket |
| PATCH | `/api/v1/tickets/{ticket_key}` | Assign, prioritize, or transition a ticket (actor comes from the verified token) |
| POST | `/api/v1/tickets/{ticket_key}/comments` | Add an auditable comment |
| GET | `/api/v1/tickets/{ticket_key}/events` | View ticket history |
| POST / GET | `/api/v1/assets` | Register and list assets |
| POST / GET | `/api/v1/knowledge` | Create and list knowledge articles |

## PowerShell exercises

- `powershell/Get-EndpointDiagnostics.ps1`: Windows endpoint inventory and diagnostics for adapters, DNS, TCP connectivity, system drive, and core services.
- `powershell/New-ADUserBatch.ps1`: CSV-based Active Directory user creation. Requires the ActiveDirectory module on a Windows Server/RSAT host. Supports `-WhatIf`; accounts remain disabled unless `-EnableAccounts` is supplied.
- `powershell/Disable-ADUserSafely.ps1`: controlled account disablement with optional move to a dedicated disabled-users OU; supports `-WhatIf`.

The PowerShell scripts are not executable on macOS. They are included as Windows lab exercises for the later phases. Review them and run first with `-WhatIf` in a disposable test domain.

## Identity, access control, and security boundaries

The API validates Microsoft Entra ID v2 access tokens using the tenant's published signing keys. Validation pins the accepted signing algorithm to RS256 and checks signature, issuer, audience, expiry, tenant ID, and user object ID. API authorization is enforced through Entra application roles:

| Role | Permission |
|---|---|
| `Helpdesk.Requester` | Submit tickets and read published knowledge |
| `Helpdesk.Technician` | Operate tickets, read inventory, and manage knowledge |
| `Asset.Manager` | Register and update assets; review asset audit history |
| `Auditor` | Read operational and audit views |
| `Administrator` | Administrative access across the API |

Audit actors are derived from validated token claims; clients cannot choose an actor name in ticket updates, comments, or asset updates. Configure `HELPDESK_ENTRA_TENANT_ID` and `HELPDESK_ENTRA_API_CLIENT_ID` using environment variables. Do not commit populated environment files or tokens.

The API is protected, but the static dashboard pages do not yet implement browser-side MSAL sign-in/token acquisition. Their API-driven controls will therefore not work with authentication enabled until the browser client is wired to acquire and send an API access token. Swagger/API clients can test the protected endpoints with a valid bearer token. The lab still uses SQLite and is not a production ITSM deployment; keep it bound to `127.0.0.1` and do not use real employee data. SQLite files are not tamper-proof, and SLA windows are elapsed-hour training targets rather than business-hours calculations.

Never store passwords, MFA codes, recovery codes, access tokens, API keys, or production secrets in tickets or sample files.

## Roadmap

See `docs/PROJECT_PLAN.md` and `docs/OPERATIONS_RUNBOOK.md` for the staged enterprise lab plan.


## Microsoft Entra setup (local demo)

The API and its tightly coupled dashboard share one single-tenant app registration for this local portfolio demo. In **Authentication**, add a **Single-page application (SPA)** platform with these exact redirect URIs: `http://localhost:18702/dashboard` and `http://localhost:18702/asset-management`. In **Expose an API**, accept the default Application ID URI (`api://<API client ID>`) and add the delegated scope `access_as_user`. In **App roles**, create the five values documented above and assign the signed-in demo user the roles needed for the pages (`Helpdesk.Technician`, `Helpdesk.Requester`, `Asset.Manager`, and optionally `Auditor` / `Administrator`). In **Token configuration**, add the `email` optional claim to access tokens if the tenant does not already emit an email/UPN claim.

The browser uses the official `@azure/msal-browser` package with authorization code flow and PKCE. Build its bundled asset with `npm install && npm run build`. The API requires the `access_as_user` delegated scope as well as valid signature, issuer, audience, tenant, expiry, user object ID, and application role claims. The `.env` file is local-only and must never be committed.
