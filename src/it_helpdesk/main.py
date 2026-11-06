from __future__ import annotations
from .schemas import AssetUpdate
from .service import update_asset, list_asset_events

import sqlite3
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from .database import initialize_database
from .schemas import AssetCreate, CommentCreate, KnowledgeArticleCreate, TicketCreate, TicketUpdate
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


@app.get("/health", tags=["Operations"])
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "it-helpdesk-lab"}


@app.get("/api/v1/dashboard/summary", tags=["Reporting"])
def summary() -> dict[str, int]:
    return dashboard_summary()


@app.post("/api/v1/tickets", status_code=201, tags=["Tickets"])
def submit_ticket(payload: TicketCreate):
    try:
        return create_ticket(payload)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Ticket could not be created due to a data conflict.") from exc


@app.get("/api/v1/tickets", tags=["Tickets"])
def get_tickets(
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None, pattern=r"^P[1-4]$"),
):
    allowed_statuses = {"new", "in_progress", "waiting_on_user", "resolved", "closed", "cancelled"}
    if status and status not in allowed_statuses:
        raise HTTPException(status_code=422, detail="Unsupported ticket status.")
    return list_tickets(status=status, priority=priority)


@app.get("/api/v1/tickets/{ticket_key}", tags=["Tickets"])
def ticket_detail(ticket_key: str):
    ticket = get_ticket(ticket_key)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return ticket


@app.patch("/api/v1/tickets/{ticket_key}", tags=["Tickets"])
def change_ticket(ticket_key: str, payload: TicketUpdate, actor: str = Query(min_length=2, max_length=100)):
    try:
        ticket = update_ticket(ticket_key, payload, actor)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return ticket


@app.post("/api/v1/tickets/{ticket_key}/comments", tags=["Tickets"])
def comment_on_ticket(ticket_key: str, payload: CommentCreate):
    ticket = add_comment(ticket_key, payload.actor, payload.comment)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return {"ticket_key": ticket_key, "status": "comment_added"}


@app.get("/api/v1/tickets/{ticket_key}/events", tags=["Tickets"])
def ticket_history(ticket_key: str):
    events = list_ticket_events(ticket_key)
    if events is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return events


@app.post("/api/v1/assets", status_code=201, tags=["Assets"])
def register_asset(payload: AssetCreate):
    try:
        return create_asset(payload)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Asset tag or hostname already exists.") from exc


@app.get("/api/v1/assets", tags=["Assets"])
def assets():
    return list_assets()


@app.post("/api/v1/knowledge", status_code=201, tags=["Knowledge Base"])
def add_knowledge_article(payload: KnowledgeArticleCreate):
    try:
        return create_knowledge_article(payload)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Knowledge article slug already exists.") from exc


@app.get("/api/v1/knowledge", tags=["Knowledge Base"])
def knowledge_articles(include_unpublished: bool = False):
    return list_knowledge_articles(published_only=not include_unpublished)


@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard_page():
    dashboard_file = Path(__file__).parent / "static" / "dashboard.html"
    return HTMLResponse(dashboard_file.read_text(encoding="utf-8"))


@app.patch("/api/v1/assets/{asset_tag}", tags=["Assets"])
def change_asset(
    asset_tag: str,
    payload: AssetUpdate,
    actor: str = Query(min_length=2, max_length=100),
):
    try:
        asset = update_asset(asset_tag, payload, actor)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found.")

    return asset


@app.get("/api/v1/assets/{asset_tag}/events", tags=["Assets"])
def asset_history(asset_tag: str):
    events = list_asset_events(asset_tag)
    if events is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return events


@app.get("/asset-management", response_class=HTMLResponse, include_in_schema=False)
def asset_management_page():
    asset_file = Path(__file__).parent / "static" / "assets.html"
    return HTMLResponse(asset_file.read_text(encoding="utf-8"))
