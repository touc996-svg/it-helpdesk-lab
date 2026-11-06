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


# Employee Joiner-Mover-Leaver workflow engine. All generated actions are simulation-only.
from uuid import uuid4
from .schemas import LifecycleRequestCreate

LIFECYCLE_TASK_TEMPLATES = {
    "joiner": [
        ("identity_provision", "Prepare Entra ID account (simulation)", "identity"),
        ("baseline_access", "Prepare baseline groups and application roles (simulation)", "access"),
        ("device_assignment", "Assign and verify an onboarding device", "asset"),
        ("onboarding_handoff", "Confirm manager handoff and onboarding evidence", "handoff"),
    ],
    "mover": [
        ("profile_update", "Prepare employee department and title update (simulation)", "identity"),
        ("access_review", "Review current groups and application roles", "access_review"),
        ("remove_old_access", "Prepare removal of obsolete access (simulation)", "access"),
        ("grant_new_access", "Prepare target role and group access (simulation)", "access"),
        ("asset_reassignment", "Review device ownership and assignment", "asset"),
    ],
    "leaver": [
        ("session_revocation", "Prepare session revocation (simulation)", "identity"),
        ("identity_disable", "Prepare Entra ID account disablement (simulation)", "identity"),
        ("access_removal", "Prepare group and application access removal (simulation)", "access"),
        ("asset_recovery", "Recover and reconcile assigned equipment", "asset"),
        ("ticket_handoff", "Review open tickets and transfer ownership", "handoff"),
    ],
}


def _lifecycle_event(db, request_id: int, principal, event_type: str, details: str) -> None:
    db.execute(
        "INSERT INTO lifecycle_events(request_id, actor_subject, actor, event_type, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (request_id, principal.subject, principal.audit_actor, event_type, details, utc_now()),
    )


def _lifecycle_detail(db, row) -> dict[str, Any]:
    result = dict(row)
    result["tasks"] = [dict(item) for item in db.execute(
        "SELECT * FROM lifecycle_tasks WHERE request_id = ? ORDER BY id", (row["id"],)
    ).fetchall()]
    result["events"] = [dict(item) for item in db.execute(
        "SELECT actor_subject, actor, event_type, details, created_at FROM lifecycle_events WHERE request_id = ? ORDER BY id",
        (row["id"],),
    ).fetchall()]
    return result


def create_lifecycle_request(data: LifecycleRequestCreate, principal) -> dict[str, Any]:
    now = utc_now()
    with connect() as db:
        cursor = db.execute(
            """INSERT INTO lifecycle_requests(
                request_key, action, employee_name, employee_email, employee_number,
                current_department, current_job_title, current_manager_email,
                target_department, target_job_title, target_manager_email,
                effective_date, reason, status, requested_by_subject, requested_by,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_approval', ?, ?, ?, ?)""",
            (
                f"TMP-{uuid4().hex}", data.action, data.employee_name, data.employee_email, data.employee_number,
                data.current_department, data.current_job_title, data.current_manager_email,
                data.target_department, data.target_job_title, data.target_manager_email,
                data.effective_date, data.reason, principal.subject, principal.audit_actor,
                now, now,
            ),
        )
        request_id = int(cursor.lastrowid)
        request_key = f"JML-{request_id:06d}"
        db.execute("UPDATE lifecycle_requests SET request_key = ? WHERE id = ?", (request_key, request_id))
        _lifecycle_event(db, request_id, principal, "request_created", f"{data.action} request created for {data.employee_email}; approval required.")
        row = db.execute("SELECT * FROM lifecycle_requests WHERE id = ?", (request_id,)).fetchone()
        return _lifecycle_detail(db, row)


def list_lifecycle_requests(status: str | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM lifecycle_requests"
    values: tuple = ()
    if status:
        query += " WHERE status = ?"
        values = (status,)
    query += " ORDER BY created_at DESC, id DESC"
    with connect() as db:
        rows = db.execute(query, values).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["task_count"] = db.execute("SELECT COUNT(*) FROM lifecycle_tasks WHERE request_id = ?", (row["id"],)).fetchone()[0]
            item["completed_task_count"] = db.execute("SELECT COUNT(*) FROM lifecycle_tasks WHERE request_id = ? AND status IN ('completed','skipped')", (row["id"],)).fetchone()[0]
            results.append(item)
        return results


def get_lifecycle_request(request_key: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM lifecycle_requests WHERE request_key = ?", (request_key,)).fetchone()
        return _lifecycle_detail(db, row) if row else None


def decide_lifecycle_request(request_key: str, decision: str, comment: str, principal) -> dict[str, Any] | None:
    if decision not in {"approved", "rejected"}:
        raise ValueError("Unsupported lifecycle decision.")
    with connect() as db:
        row = db.execute("SELECT * FROM lifecycle_requests WHERE request_key = ?", (request_key,)).fetchone()
        if row is None:
            return None
        if row["status"] != "pending_approval":
            raise ValueError(f"Request cannot be decided from status {row['status']}.")
        if row["requested_by_subject"] == principal.subject:
            raise PermissionError("A request creator cannot approve or reject their own request.")
        now = utc_now()
        db.execute(
            """UPDATE lifecycle_requests
               SET status = ?, approved_by_subject = ?, approved_by = ?, approval_comment = ?, approved_at = ?, updated_at = ?
               WHERE id = ?""",
            (decision, principal.subject, principal.audit_actor, comment, now, now, row["id"]),
        )
        if decision == "approved":
            for task_key, title, task_type in LIFECYCLE_TASK_TEMPLATES[row["action"]]:
                db.execute(
                    """INSERT INTO lifecycle_tasks(request_id, task_key, title, task_type, execution_mode, status, created_at)
                       VALUES (?, ?, ?, ?, 'simulation', 'pending', ?)""",
                    (row["id"], task_key, title, task_type, now),
                )
        _lifecycle_event(db, row["id"], principal, decision, comment)
        refreshed = db.execute("SELECT * FROM lifecycle_requests WHERE id = ?", (row["id"],)).fetchone()
        return _lifecycle_detail(db, refreshed)


def update_lifecycle_task(request_key: str, task_id: int, status: str, result: str, principal) -> dict[str, Any] | None:
    if status not in {"in_progress", "completed", "skipped"}:
        raise ValueError("Unsupported task status.")
    with connect() as db:
        request = db.execute("SELECT * FROM lifecycle_requests WHERE request_key = ?", (request_key,)).fetchone()
        if request is None:
            return None
        if request["status"] not in {"approved", "in_progress"}:
            raise ValueError("Tasks can only be updated after approval.")
        task = db.execute("SELECT * FROM lifecycle_tasks WHERE id = ? AND request_id = ?", (task_id, request["id"])).fetchone()
        if task is None:
            return None
        if task["status"] in {"completed", "skipped"}:
            raise ValueError("A completed or skipped task cannot be changed.")
        completed_at = utc_now() if status in {"completed", "skipped"} else None
        db.execute(
            "UPDATE lifecycle_tasks SET status = ?, result = ?, completed_by = ?, completed_at = ? WHERE id = ?",
            (status, result, principal.audit_actor, completed_at, task_id),
        )
        parent_status = "in_progress" if status == "in_progress" else request["status"]
        counts = db.execute(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN status IN ('completed','skipped') THEN 1 ELSE 0 END) AS done FROM lifecycle_tasks WHERE request_id = ?",
            (request["id"],),
        ).fetchone()
        if counts["total"] and counts["done"] == counts["total"]:
            parent_status = "completed"
        elif status in {"completed", "skipped"} and parent_status == "approved":
            parent_status = "in_progress"
        db.execute("UPDATE lifecycle_requests SET status = ?, updated_at = ? WHERE id = ?", (parent_status, utc_now(), request["id"]))
        _lifecycle_event(db, request["id"], principal, "task_updated", f"{task['task_key']} => {status}: {result}")
        refreshed = db.execute("SELECT * FROM lifecycle_requests WHERE id = ?", (request["id"],)).fetchone()
        return _lifecycle_detail(db, refreshed)
