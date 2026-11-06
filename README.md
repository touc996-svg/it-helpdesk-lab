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
| PATCH | `/api/v1/tickets/{ticket_key}?actor=...` | Assign, prioritize, or transition a ticket |
| POST | `/api/v1/tickets/{ticket_key}/comments` | Add an auditable comment |
| GET | `/api/v1/tickets/{ticket_key}/events` | View ticket history |
| POST / GET | `/api/v1/assets` | Register and list assets |
| POST / GET | `/api/v1/knowledge` | Create and list knowledge articles |

## PowerShell exercises

- `powershell/Get-EndpointDiagnostics.ps1`: Windows endpoint inventory and diagnostics for adapters, DNS, TCP connectivity, system drive, and core services.
- `powershell/New-ADUserBatch.ps1`: CSV-based Active Directory user creation. Requires the ActiveDirectory module on a Windows Server/RSAT host. Supports `-WhatIf`; accounts remain disabled unless `-EnableAccounts` is supplied.
- `powershell/Disable-ADUserSafely.ps1`: controlled account disablement with optional move to a dedicated disabled-users OU; supports `-WhatIf`.

The PowerShell scripts are not executable on macOS. They are included as Windows lab exercises for the later phases. Review them and run first with `-WhatIf` in a disposable test domain.

## Security and limitations

This is a local training project, not a production ITSM platform. It currently has no authentication, authorization, CSRF controls, secrets management, or multi-user tenancy. Keep it bound to `127.0.0.1`; do not expose it to the internet or use real employee data. Ticket events are append-only through the application, but the SQLite file itself is not tamper-proof. Priority windows are simple elapsed-hour training targets, not business-hours SLA calculations.

Never store passwords, MFA codes, recovery codes, API keys, or production secrets in tickets or sample files.

## Roadmap

See `docs/PROJECT_PLAN.md` and `docs/OPERATIONS_RUNBOOK.md` for the staged enterprise lab plan.
