from __future__ import annotations
from .schemas import AssetUpdate

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from .database import connect
from .schemas import AssetCreate, KnowledgeArticleCreate, TicketCreate, TicketUpdate

SLA_HOURS = {"P1": 4, "P2": 8, "P3": 24, "P4": 72}
TRANSITIONS = {
    "new": {"in_progress", "cancelled"},
    "in_progress": {"waiting_on_user", "resolved", "cancelled"},
    "waiting_on_user": {"in_progress", "resolved", "cancelled"},
    "resolved": {"closed", "in_progress"},
    "closed": {"in_progress"},
    "cancelled": set(),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def get_ticket(ticket_key: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM tickets WHERE ticket_key = ?", (ticket_key,)).fetchone()
    return parse_row(row)


def list_tickets(status: str | None = None, priority: str | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM tickets WHERE 1=1"
    params: list[str] = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    query += " ORDER BY CASE priority WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END, created_at DESC"
    with connect() as db:
        rows = db.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def _event(db: sqlite3.Connection, ticket_id: int, actor: str, event_type: str, details: str) -> None:
    db.execute(
        "INSERT INTO ticket_events(ticket_id, actor, event_type, details, created_at) VALUES (?, ?, ?, ?, ?)",
        (ticket_id, actor, event_type, details, utc_now()),
    )


def create_ticket(data: TicketCreate, actor: str | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    created_at = now.isoformat(timespec="seconds")
    due_at = (now + timedelta(hours=SLA_HOURS[data.priority])).isoformat(timespec="seconds")
    with connect() as db:
        cursor = db.execute(
            """INSERT INTO tickets(
                title, description, requester_name, requester_email, category,
                priority, status, assigned_to, created_at, updated_at, due_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'new', NULL, ?, ?, ?)""",
            (
                data.title, data.description, data.requester_name, data.requester_email,
                data.category, data.priority, created_at, created_at, due_at,
            ),
        )
        ticket_id = int(cursor.lastrowid)
        ticket_key = f"HD-{ticket_id:06d}"
        db.execute("UPDATE tickets SET ticket_key = ? WHERE id = ?", (ticket_key, ticket_id))
        _event(db, ticket_id, actor or data.requester_name, "ticket_created", f"Ticket {ticket_key} created; priority={data.priority}; category={data.category}.")
        row = db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return dict(row)


def update_ticket(ticket_key: str, data: TicketUpdate, actor: str) -> dict[str, Any] | None:
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return get_ticket(ticket_key)

    with connect() as db:
        current = db.execute("SELECT * FROM tickets WHERE ticket_key = ?", (ticket_key,)).fetchone()
        if current is None:
            return None
        current_dict = dict(current)

        if "status" in changes and changes["status"] is not None:
            requested = changes["status"]
            if requested != current_dict["status"] and requested not in TRANSITIONS[current_dict["status"]]:
                raise ValueError(f"Invalid status transition: {current_dict['status']} -> {requested}.")
        if "priority" in changes and changes["priority"] is not None and changes["priority"] != current_dict["priority"]:
            deadline = datetime.now(timezone.utc) + timedelta(hours=SLA_HOURS[changes["priority"]])
            changes["due_at"] = deadline.isoformat(timespec="seconds")

        assignments: list[str] = []
        values: list[Any] = []
        for field, value in changes.items():
            if value is not None or field == "assigned_to":
                assignments.append(f"{field} = ?")
                values.append(value)
        assignments.append("updated_at = ?")
        values.append(utc_now())
        values.append(ticket_key)
        db.execute(f"UPDATE tickets SET {', '.join(assignments)} WHERE ticket_key = ?", values)

        for field, value in changes.items():
            if value != current_dict.get(field):
                _event(db, current_dict["id"], actor, f"{field}_updated", f"{field}: {current_dict.get(field)} -> {value}")

        row = db.execute("SELECT * FROM tickets WHERE ticket_key = ?", (ticket_key,)).fetchone()
    return dict(row)


def add_comment(ticket_key: str, data_actor: str, comment: str) -> dict[str, Any] | None:
    with connect() as db:
        ticket = db.execute("SELECT id FROM tickets WHERE ticket_key = ?", (ticket_key,)).fetchone()
        if ticket is None:
            return None
        _event(db, int(ticket["id"]), data_actor, "comment", comment)
        db.execute("UPDATE tickets SET updated_at = ? WHERE id = ?", (utc_now(), int(ticket["id"])))
    return get_ticket(ticket_key)


def list_ticket_events(ticket_key: str) -> list[dict[str, Any]] | None:
    with connect() as db:
        ticket = db.execute("SELECT id FROM tickets WHERE ticket_key = ?", (ticket_key,)).fetchone()
        if ticket is None:
            return None
        rows = db.execute(
            "SELECT actor, event_type, details, created_at FROM ticket_events WHERE ticket_id = ? ORDER BY id",
            (ticket["id"],),
        ).fetchall()
    return [dict(row) for row in rows]


def create_asset(data: AssetCreate, actor: str = "system") -> dict[str, Any]:
    now = utc_now()
    with connect() as db:
        cursor = db.execute(
            """INSERT INTO assets(asset_tag, hostname, device_type, operating_system,
               assigned_to, location, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data.asset_tag, data.hostname, data.device_type, data.operating_system,
             data.assigned_to, data.location, data.status, now, now),
        )
        db.execute(
            """INSERT INTO asset_events(asset_id, actor, event_type, details, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (cursor.lastrowid, actor, "asset_created", f"Asset {data.asset_tag} registered.", now),
        )
        row = db.execute("SELECT * FROM assets WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def list_assets() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("SELECT * FROM assets ORDER BY asset_tag").fetchall()
    return [dict(row) for row in rows]


def create_knowledge_article(data: KnowledgeArticleCreate) -> dict[str, Any]:
    now = utc_now()
    with connect() as db:
        cursor = db.execute(
            """INSERT INTO knowledge_articles(slug, title, category, symptoms,
               resolution_steps, owner, published, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data.slug, data.title, data.category, data.symptoms, data.resolution_steps,
             data.owner, int(data.published), now, now),
        )
        row = db.execute("SELECT * FROM knowledge_articles WHERE id = ?", (cursor.lastrowid,)).fetchone()
    result = dict(row)
    result["published"] = bool(result["published"])
    return result


def list_knowledge_articles(published_only: bool = True) -> list[dict[str, Any]]:
    query = "SELECT * FROM knowledge_articles"
    if published_only:
        query += " WHERE published = 1"
    query += " ORDER BY category, title"
    with connect() as db:
        rows = db.execute(query).fetchall()
    results = [dict(row) for row in rows]
    for item in results:
        item["published"] = bool(item["published"])
    return results


def dashboard_summary() -> dict[str, int]:
    with connect() as db:
        total = db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        open_count = db.execute("SELECT COUNT(*) FROM tickets WHERE status NOT IN ('resolved','closed','cancelled')").fetchone()[0]
        overdue = db.execute("SELECT COUNT(*) FROM tickets WHERE status NOT IN ('resolved','closed','cancelled') AND due_at < ?", (utc_now(),)).fetchone()[0]
        critical = db.execute("SELECT COUNT(*) FROM tickets WHERE priority = 'P1' AND status NOT IN ('resolved','closed','cancelled')").fetchone()[0]
        assets = db.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        articles = db.execute("SELECT COUNT(*) FROM knowledge_articles WHERE published = 1").fetchone()[0]
    return {"total_tickets": total, "open_tickets": open_count, "overdue_tickets": overdue,
            "open_p1_tickets": critical, "tracked_assets": assets, "published_articles": articles}


ASSET_TRANSITIONS = {
    "in_service": {"in_repair", "retired", "lost"},
    "in_repair": {"in_service", "retired", "lost"},
    "lost": {"in_service", "retired"},
    "retired": set(),
}


def update_asset(asset_tag: str, data: AssetUpdate, actor: str) -> dict[str, Any] | None:
    changes = data.model_dump(exclude_unset=True)

    with connect() as db:
        current = db.execute(
            "SELECT * FROM assets WHERE asset_tag = ?", (asset_tag,)
        ).fetchone()

        if current is None:
            return None

        old = dict(current)

        if not changes:
            return old

        requested_status = changes.get("status")
        if requested_status and requested_status != old["status"]:
            allowed = ASSET_TRANSITIONS.get(old["status"], set())
            if requested_status not in allowed:
                raise ValueError(
                    f"Invalid asset status transition: {old['status']} -> {requested_status}"
                )

        assignments = []
        values = []
        for field, value in changes.items():
            if field not in {"assigned_to", "location", "status"}:
                continue
            assignments.append(f"{field} = ?")
            values.append(value)

        if not assignments:
            return old

        assignments.append("updated_at = ?")
        values.append(utc_now())
        values.append(asset_tag)

        db.execute(
            f"UPDATE assets SET {', '.join(assignments)} WHERE asset_tag = ?",
            values,
        )

        for field, value in changes.items():
            if field in old and value != old[field]:
                db.execute(
                    """INSERT INTO asset_events
                       (asset_id, actor, event_type, details, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        old["id"],
                        actor,
                        f"{field}_updated",
                        f"{field}: {old[field]} -> {value}",
                        utc_now(),
                    ),
                )

        row = db.execute(
            "SELECT * FROM assets WHERE asset_tag = ?", (asset_tag,)
        ).fetchone()

    return dict(row)


def list_asset_events(asset_tag: str) -> list[dict[str, Any]] | None:
    with connect() as db:
        asset = db.execute(
            "SELECT id FROM assets WHERE asset_tag = ?", (asset_tag,)
        ).fetchone()

        if asset is None:
            return None

        rows = db.execute(
            """SELECT actor, event_type, details, created_at
               FROM asset_events WHERE asset_id = ?
               ORDER BY id""",
            (asset["id"],),
        ).fetchall()

    return [dict(row) for row in rows]
