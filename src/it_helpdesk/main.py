from __future__ import annotations

import sqlite3
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from .auth import Principal, require_roles

from .database import initialize_database
from .schemas import AssetCreate, AssetUpdate, CommentCreate, KnowledgeArticleCreate, TicketCreate, TicketUpdate, LifecycleRequestCreate, LifecycleDecisionCreate, LifecycleTaskUpdate
from .service import (
    add_comment,
    create_asset,
    create_knowledge_article,
    create_ticket,
    dashboard_summary,
    get_ticket,
    list_assets,
    list_knowledge_articles,
    list_ticket_events,
    list_tickets,
    update_ticket,
    update_asset,
    list_asset_events,
    create_lifecycle_request,
    list_lifecycle_requests,
    get_lifecycle_request,
    decide_lifecycle_request,
    update_lifecycle_task,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="ATLAS IT Support & Identity Operations Lab",
    description=(
        "A local, portfolio-grade service desk API with ticket lifecycle management, "
        "SLA targets, asset inventory, knowledge articles, and an auditable event trail."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/v1/auth/config", tags=["Authentication"])
def auth_config() -> dict[str, str | bool]:
    tenant_id = __import__("os").getenv("HELPDESK_ENTRA_TENANT_ID", "").strip()
    api_client_id = __import__("os").getenv("HELPDESK_ENTRA_API_CLIENT_ID", "").strip()
    spa_client_id = __import__("os").getenv("HELPDESK_ENTRA_SPA_CLIENT_ID", api_client_id).strip()
    configured = bool(tenant_id and api_client_id and spa_client_id)
    return {
        "configured": configured,
        "tenantId": tenant_id,
        "clientId": spa_client_id,
        "authority": f"https://login.microsoftonline.com/{tenant_id}" if configured else "",
        "apiScope": f"api://{api_client_id}/access_as_user" if configured else "",
    }


@app.post("/api/v1/lifecycle/requests", status_code=201, tags=["Employee Lifecycle"])
def submit_lifecycle_request(
    payload: LifecycleRequestCreate,
    principal: Principal = Depends(require_roles("Helpdesk.Technician", "Administrator")),
):
    return create_lifecycle_request(payload, principal)


@app.get("/api/v1/lifecycle/requests", tags=["Employee Lifecycle"])
def get_lifecycle_requests(
    status: str | None = Query(default=None, pattern=r"^(pending_approval|approved|rejected|in_progress|completed|cancelled)$"),
    principal: Principal = Depends(require_roles("Helpdesk.Technician", "Administrator", "Auditor")),
):
    return list_lifecycle_requests(status)


@app.get("/api/v1/lifecycle/requests/{request_key}", tags=["Employee Lifecycle"])
def lifecycle_request_detail(
    request_key: str,
    principal: Principal = Depends(require_roles("Helpdesk.Technician", "Administrator", "Auditor")),
):
    request = get_lifecycle_request(request_key)
    if request is None:
        raise HTTPException(status_code=404, detail="Lifecycle request not found.")
    return request


@app.post("/api/v1/lifecycle/requests/{request_key}/approve", tags=["Employee Lifecycle"])
def approve_lifecycle_request(
    request_key: str,
    payload: LifecycleDecisionCreate,
    principal: Principal = Depends(require_roles("Administrator")),
):
    try:
        request = decide_lifecycle_request(request_key, "approved", payload.comment, principal)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if request is None:
        raise HTTPException(status_code=404, detail="Lifecycle request not found.")
    return request


@app.post("/api/v1/lifecycle/requests/{request_key}/reject", tags=["Employee Lifecycle"])
def reject_lifecycle_request(
    request_key: str,
    payload: LifecycleDecisionCreate,
    principal: Principal = Depends(require_roles("Administrator")),
):
    try:
        request = decide_lifecycle_request(request_key, "rejected", payload.comment, principal)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if request is None:
        raise HTTPException(status_code=404, detail="Lifecycle request not found.")
    return request


@app.patch("/api/v1/lifecycle/requests/{request_key}/tasks/{task_id}", tags=["Employee Lifecycle"])
def change_lifecycle_task(
    request_key: str,
    task_id: int,
    payload: LifecycleTaskUpdate,
    principal: Principal = Depends(require_roles("Helpdesk.Technician", "Asset.Manager", "Administrator")),
):
    try:
        request = update_lifecycle_task(request_key, task_id, payload.status, payload.result, principal)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if request is None:
        raise HTTPException(status_code=404, detail="Lifecycle request or task not found.")
    return request


@app.get("/health", tags=["Operations"])
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "it-helpdesk-lab"}


@app.get("/api/v1/dashboard/summary", tags=["Reporting"])
def summary(principal: Principal = Depends(require_roles("Helpdesk.Technician", "Administrator", "Auditor"))) -> dict[str, int]:
    return dashboard_summary()


@app.post("/api/v1/tickets", status_code=201, tags=["Tickets"])
def submit_ticket(
    payload: TicketCreate,
    principal: Principal = Depends(require_roles("Helpdesk.Requester", "Helpdesk.Technician", "Administrator")),
):
    if not principal.email:
        raise HTTPException(403, detail="Your Entra token has no email/UPN claim. Add the email optional claim to access tokens in Entra Token configuration.")
    verified_payload = payload.model_copy(update={
        "requester_name": principal.display_name,
        "requester_email": principal.email,
    })
    try:
        return create_ticket(verified_payload, actor=principal.audit_actor)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Ticket could not be created due to a data conflict.") from exc


@app.get("/api/v1/tickets", tags=["Tickets"])
def get_tickets(
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None, pattern=r"^P[1-4]$"),
    principal: Principal = Depends(require_roles("Helpdesk.Technician", "Administrator", "Auditor")),
):
    allowed_statuses = {"new", "in_progress", "waiting_on_user", "resolved", "closed", "cancelled"}
    if status and status not in allowed_statuses:
        raise HTTPException(status_code=422, detail="Unsupported ticket status.")
    return list_tickets(status=status, priority=priority)


@app.get("/api/v1/tickets/{ticket_key}", tags=["Tickets"])
def ticket_detail(
    ticket_key: str,
    principal: Principal = Depends(require_roles("Helpdesk.Technician", "Administrator", "Auditor")),
):
    ticket = get_ticket(ticket_key)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return ticket


@app.patch("/api/v1/tickets/{ticket_key}", tags=["Tickets"])
def change_ticket(
    ticket_key: str,
    payload: TicketUpdate,
    principal: Principal = Depends(require_roles("Helpdesk.Technician", "Administrator")),
):
    try:
        ticket = update_ticket(ticket_key, payload, principal.audit_actor)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return ticket


@app.post("/api/v1/tickets/{ticket_key}/comments", tags=["Tickets"])
def comment_on_ticket(
    ticket_key: str,
    payload: CommentCreate,
    principal: Principal = Depends(require_roles("Helpdesk.Technician", "Administrator")),
):
    ticket = add_comment(ticket_key, principal.audit_actor, payload.comment)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return {"ticket_key": ticket_key, "status": "comment_added"}


@app.get("/api/v1/tickets/{ticket_key}/events", tags=["Tickets"])
def ticket_history(
    ticket_key: str,
    principal: Principal = Depends(require_roles("Helpdesk.Technician", "Administrator", "Auditor")),
):
    events = list_ticket_events(ticket_key)
    if events is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return events


@app.post("/api/v1/assets", status_code=201, tags=["Assets"])
def register_asset(
    payload: AssetCreate,
    principal: Principal = Depends(require_roles("Asset.Manager", "Administrator")),
):
    try:
        return create_asset(payload, actor=principal.audit_actor)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Asset tag or hostname already exists.") from exc


@app.get("/api/v1/assets", tags=["Assets"])
def assets(
    principal: Principal = Depends(require_roles("Helpdesk.Technician", "Asset.Manager", "Administrator", "Auditor")),
):
    return list_assets()


@app.post("/api/v1/knowledge", status_code=201, tags=["Knowledge Base"])
def add_knowledge_article(
    payload: KnowledgeArticleCreate,
    principal: Principal = Depends(require_roles("Helpdesk.Technician", "Administrator")),
):
    try:
        verified_payload = payload.model_copy(update={"owner": principal.username})
        return create_knowledge_article(verified_payload)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Knowledge article slug already exists.") from exc


@app.get("/api/v1/knowledge", tags=["Knowledge Base"])
def knowledge_articles(
    include_unpublished: bool = False,
    principal: Principal = Depends(require_roles("Helpdesk.Requester", "Helpdesk.Technician", "Administrator", "Auditor")),
):
    if include_unpublished and not principal.roles.intersection({"Helpdesk.Technician", "Administrator", "Auditor"}):
        raise HTTPException(status_code=403, detail="Your role cannot view draft knowledge articles.")
    return list_knowledge_articles(published_only=not include_unpublished)


@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard_page():
    dashboard_file = Path(__file__).parent / "static" / "dashboard.html"
    return HTMLResponse(dashboard_file.read_text(encoding="utf-8"))


@app.patch("/api/v1/assets/{asset_tag}", tags=["Assets"])
def change_asset(
    asset_tag: str,
    payload: AssetUpdate,
    principal: Principal = Depends(require_roles("Asset.Manager", "Administrator")),
):
    try:
        asset = update_asset(asset_tag, payload, principal.audit_actor)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found.")

    return asset


@app.get("/api/v1/assets/{asset_tag}/events", tags=["Assets"])
def asset_history(
    asset_tag: str,
    principal: Principal = Depends(require_roles("Asset.Manager", "Administrator", "Auditor")),
):
    events = list_asset_events(asset_tag)
    if events is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return events


@app.get("/asset-management", response_class=HTMLResponse, include_in_schema=False)
def asset_management_page():
    asset_file = Path(__file__).parent / "static" / "assets.html"
    return HTMLResponse(asset_file.read_text(encoding="utf-8"))
