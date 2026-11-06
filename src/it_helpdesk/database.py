from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def database_path() -> Path:
    configured = os.getenv("HELPDESK_DB_PATH", "data/helpdesk.db")
    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_key TEXT UNIQUE,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                requester_name TEXT NOT NULL,
                requester_email TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                assigned_to TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                due_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tickets_status_priority
                ON tickets(status, priority);
            CREATE INDEX IF NOT EXISTS idx_tickets_created_at
                ON tickets(created_at DESC);

            CREATE TABLE IF NOT EXISTS ticket_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ticket_events_ticket_id
                ON ticket_events(ticket_id, created_at);

            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_tag TEXT NOT NULL UNIQUE,
                hostname TEXT NOT NULL UNIQUE,
                device_type TEXT NOT NULL,
                operating_system TEXT NOT NULL,
                assigned_to TEXT,
                location TEXT,
                status TEXT NOT NULL DEFAULT 'in_service',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS asset_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_asset_events_asset_id
                ON asset_events(asset_id, created_at);

            CREATE TABLE IF NOT EXISTS knowledge_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                symptoms TEXT NOT NULL,
                resolution_steps TEXT NOT NULL,
                owner TEXT NOT NULL,
                published INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS lifecycle_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_key TEXT NOT NULL UNIQUE,
                action TEXT NOT NULL CHECK(action IN ('joiner','mover','leaver')),
                employee_name TEXT NOT NULL,
                employee_email TEXT NOT NULL,
                employee_number TEXT,
                current_department TEXT,
                current_job_title TEXT,
                current_manager_email TEXT,
                target_department TEXT,
                target_job_title TEXT,
                target_manager_email TEXT,
                effective_date TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending_approval','approved','rejected','in_progress','completed','cancelled')),
                requested_by_subject TEXT NOT NULL,
                requested_by TEXT NOT NULL,
                approved_by_subject TEXT,
                approved_by TEXT,
                approval_comment TEXT,
                approved_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_lifecycle_requests_status_date
                ON lifecycle_requests(status, effective_date);
            CREATE INDEX IF NOT EXISTS idx_lifecycle_requests_employee
                ON lifecycle_requests(employee_email, created_at DESC);

            CREATE TABLE IF NOT EXISTS lifecycle_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL REFERENCES lifecycle_requests(id) ON DELETE CASCADE,
                task_key TEXT NOT NULL,
                title TEXT NOT NULL,
                task_type TEXT NOT NULL,
                execution_mode TEXT NOT NULL DEFAULT 'simulation' CHECK(execution_mode IN ('simulation','manual')),
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','in_progress','completed','skipped')),
                result TEXT,
                completed_by TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(request_id, task_key)
            );
            CREATE INDEX IF NOT EXISTS idx_lifecycle_tasks_request
                ON lifecycle_tasks(request_id, id);

            CREATE TABLE IF NOT EXISTS lifecycle_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL REFERENCES lifecycle_requests(id) ON DELETE CASCADE,
                actor_subject TEXT NOT NULL,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_lifecycle_events_request
                ON lifecycle_events(request_id, id);
            """
        )
