"""Versioned forward & rollback schema migrations for VEAP v0.7 StudioDB."""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Callable

from .db import StudioDB


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    up_sql: str
    down_sql: str


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        name="baseline_studio_v05",
        up_sql="SELECT 1;",
        down_sql="SELECT 1;",
    ),
    Migration(
        version=2,
        name="durable_job_queue_and_object_refs",
        up_sql="""
        CREATE TABLE IF NOT EXISTS durable_jobs (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL REFERENCES tenants(id),
            kind TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('queued', 'leased', 'completed', 'poison_dlq')),
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            lease_owner TEXT,
            lease_expires_at REAL,
            last_error TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_durable_jobs_status_lease
            ON durable_jobs(status, lease_expires_at);
        CREATE TABLE IF NOT EXISTS tenant_object_refs (
            tenant_id TEXT NOT NULL REFERENCES tenants(id),
            object_key TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            created_at REAL NOT NULL,
            PRIMARY KEY (tenant_id, object_key)
        );
        """,
        down_sql="""
        DROP TABLE IF EXISTS tenant_object_refs;
        DROP INDEX IF EXISTS idx_durable_jobs_status_lease;
        DROP TABLE IF EXISTS durable_jobs;
        """,
    ),
    Migration(
        version=3,
        name="security_audit_events",
        up_sql="""
        CREATE TABLE IF NOT EXISTS security_audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT,
            principal_id TEXT,
            action TEXT NOT NULL,
            outcome TEXT NOT NULL,
            detail TEXT,
            created_at REAL NOT NULL
        );
        """,
        down_sql="""
        DROP TABLE IF EXISTS security_audit_events;
        """,
    ),
)


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at REAL NOT NULL
        )
        """
    )


def current_version(db: StudioDB) -> int:
    with db.conn() as c:
        _ensure_table(c)
        row = c.execute("SELECT COALESCE(MAX(version), 0) AS v FROM schema_migrations").fetchone()
        return int(row["v"])


def apply_migrations(db: StudioDB, *, target_version: int | None = None) -> list[int]:
    """Apply pending migrations up to ``target_version`` (or latest)."""
    applied: list[int] = []
    with db.conn(write=True) as c:
        _ensure_table(c)
        existing = {
            int(r["version"])
            for r in c.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for mig in MIGRATIONS:
            if target_version is not None and mig.version > target_version:
                continue
            if mig.version in existing:
                continue
            c.executescript(mig.up_sql)
            c.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (mig.version, mig.name, time.time()),
            )
            applied.append(mig.version)
    return applied


def rollback_migration(db: StudioDB, *, target_version: int) -> list[int]:
    """Roll back applied migrations strictly above ``target_version`` in reverse order."""
    if target_version < 0:
        raise ValueError("target_version must be non-negative")
    rolled_back: list[int] = []
    with db.conn(write=True) as c:
        _ensure_table(c)
        existing = {
            int(r["version"])
            for r in c.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for mig in reversed(MIGRATIONS):
            if mig.version <= target_version:
                continue
            if mig.version not in existing:
                continue
            c.executescript(mig.down_sql)
            c.execute("DELETE FROM schema_migrations WHERE version = ?", (mig.version,))
            rolled_back.append(mig.version)
    return rolled_back
