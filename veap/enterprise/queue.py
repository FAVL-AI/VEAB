"""Durable leased job queue and poison-message dead-letter handling (v0.7)."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from .db import StudioDB, canonical, new_id
from .migrations import apply_migrations


@dataclass(frozen=True)
class LeasedJob:
    id: str
    tenant_id: str
    kind: str
    payload: dict[str, Any]
    attempt_count: int
    max_attempts: int
    lease_owner: str
    lease_expires_at: float


class DurableJobQueue:
    """SQLite-backed durable worker queue with leases and poison-message DLQ."""

    def __init__(self, db: StudioDB) -> None:
        self.db = db
        apply_migrations(db)

    def enqueue(
        self,
        tenant_id: str,
        kind: str,
        payload: dict[str, Any],
        *,
        max_attempts: int = 3,
        now: float | None = None,
    ) -> str:
        if not isinstance(max_attempts, int) or not 1 <= max_attempts <= 20:
            raise ValueError("max_attempts must be between 1 and 20")
        ts = time.time() if now is None else float(now)
        job_id = new_id()
        with self.db.conn(write=True) as c:
            c.execute(
                """
                INSERT INTO durable_jobs(
                    id, tenant_id, kind, payload_json, status,
                    attempt_count, max_attempts, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'queued', 0, ?, ?, ?)
                """,
                (job_id, tenant_id, kind, canonical(payload), max_attempts, ts, ts),
            )
        return job_id

    def reclaim_expired_leases(self, *, now: float | None = None) -> dict[str, int]:
        """Re-queue or dead-letter jobs whose worker leases have expired."""
        ts = time.time() if now is None else float(now)
        requeued = 0
        dead_lettered = 0
        with self.db.conn(write=True) as c:
            expired = c.execute(
                "SELECT id, attempt_count, max_attempts FROM durable_jobs "
                "WHERE status = 'leased' AND lease_expires_at <= ?",
                (ts,),
            ).fetchall()
            for row in expired:
                if int(row["attempt_count"]) >= int(row["max_attempts"]):
                    c.execute(
                        "UPDATE durable_jobs SET status='poison_dlq', lease_owner=NULL, "
                        "lease_expires_at=NULL, last_error='lease_expired_max_attempts', updated_at=? WHERE id=?",
                        (ts, row["id"]),
                    )
                    dead_lettered += 1
                else:
                    c.execute(
                        "UPDATE durable_jobs SET status='queued', lease_owner=NULL, "
                        "lease_expires_at=NULL, last_error='lease_expired', updated_at=? WHERE id=?",
                        (ts, row["id"]),
                    )
                    requeued += 1
        return {"requeued": requeued, "dead_lettered": dead_lettered}

    def lease_next(
        self,
        worker_id: str,
        *,
        lease_seconds: float = 30.0,
        now: float | None = None,
    ) -> LeasedJob | None:
        if not worker_id:
            raise ValueError("worker_id required")
        ts = time.time() if now is None else float(now)
        self.reclaim_expired_leases(now=ts)
        with self.db.conn(write=True) as c:
            row = c.execute(
                "SELECT * FROM durable_jobs WHERE status='queued' ORDER BY created_at ASC, id ASC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            new_attempts = int(row["attempt_count"]) + 1
            expires = ts + float(lease_seconds)
            c.execute(
                "UPDATE durable_jobs SET status='leased', attempt_count=?, lease_owner=?, "
                "lease_expires_at=?, updated_at=? WHERE id=? AND status='queued'",
                (new_attempts, worker_id, expires, ts, row["id"]),
            )
            return LeasedJob(
                id=row["id"],
                tenant_id=row["tenant_id"],
                kind=row["kind"],
                payload=json.loads(row["payload_json"]),
                attempt_count=new_attempts,
                max_attempts=int(row["max_attempts"]),
                lease_owner=worker_id,
                lease_expires_at=expires,
            )

    def heartbeat(
        self,
        job_id: str,
        worker_id: str,
        *,
        lease_seconds: float = 30.0,
        now: float | None = None,
    ) -> bool:
        ts = time.time() if now is None else float(now)
        with self.db.conn(write=True) as c:
            cur = c.execute(
                "UPDATE durable_jobs SET lease_expires_at=?, updated_at=? "
                "WHERE id=? AND status='leased' AND lease_owner=?",
                (ts + float(lease_seconds), ts, job_id, worker_id),
            )
            return cur.rowcount == 1

    def ack_complete(self, job_id: str, worker_id: str, *, now: float | None = None) -> bool:
        ts = time.time() if now is None else float(now)
        with self.db.conn(write=True) as c:
            cur = c.execute(
                "UPDATE durable_jobs SET status='completed', lease_owner=NULL, "
                "lease_expires_at=NULL, updated_at=? "
                "WHERE id=? AND status='leased' AND lease_owner=?",
                (ts, job_id, worker_id),
            )
            return cur.rowcount == 1

    def nack(
        self,
        job_id: str,
        worker_id: str,
        error: str,
        *,
        now: float | None = None,
    ) -> str:
        ts = time.time() if now is None else float(now)
        with self.db.conn(write=True) as c:
            row = c.execute(
                "SELECT attempt_count, max_attempts FROM durable_jobs "
                "WHERE id=? AND status='leased' AND lease_owner=?",
                (job_id, worker_id),
            ).fetchone()
            if row is None:
                raise ValueError("job not currently leased by worker")
            next_status = "poison_dlq" if int(row["attempt_count"]) >= int(row["max_attempts"]) else "queued"
            c.execute(
                "UPDATE durable_jobs SET status=?, lease_owner=NULL, lease_expires_at=NULL, "
                "last_error=?, updated_at=? WHERE id=?",
                (next_status, error[:500], ts, job_id),
            )
            return next_status

    def get_job(self, job_id: str, *, tenant_id: str | None = None) -> dict[str, Any] | None:
        with self.db.conn() as c:
            if tenant_id is None:
                row = c.execute("SELECT * FROM durable_jobs WHERE id=?", (job_id,)).fetchone()
            else:
                row = c.execute(
                    "SELECT * FROM durable_jobs WHERE id=? AND tenant_id=?",
                    (job_id, tenant_id),
                ).fetchone()
            return dict(row) if row is not None else None
