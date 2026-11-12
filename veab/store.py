"""Single-host durable run index. Evidence files are written atomically."""
from __future__ import annotations
import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

class Store:
    def __init__(self, folder: str | Path):
        self.folder = Path(folder).resolve()
        self.folder.mkdir(parents=True,exist_ok=True)
        self.db = self.folder / "veab.sqlite3"
        self._lock = threading.RLock()
        self.live: dict[str,list[dict[str,Any]]] = {}
        with self.conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL, policy TEXT NOT NULL,
                seed INTEGER NOT NULL, shield INTEGER NOT NULL, status TEXT NOT NULL,
                created_at REAL NOT NULL, duration_ms REAL, summary_json TEXT, error TEXT
            )""")

    def conn(self):
        connection = sqlite3.connect(self.db, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def create(self, scenario_id: str, policy: str, seed: int, shield: bool) -> str:
        run_id = uuid.uuid4().hex
        with self.conn() as c:
            c.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (run_id, scenario_id, policy, seed, int(shield), "queued", time.time(),None,None,None))
        with self._lock:
            self.live[run_id] = []
        return run_id

    def set_status(self, run_id: str, status: str, duration_ms: float | None = None,
                   summary: dict | None = None, error: str | None = None):
        with self.conn() as c:
            c.execute("UPDATE runs SET status=?,duration_ms=?,summary_json=?,error=? WHERE id=?",
                      (status,duration_ms,json.dumps(summary) if summary is not None else None,error,run_id))

    def append_live(self, run_id: str, record: dict):
        with self._lock:
            if run_id in self.live:
                self.live[run_id].append(record)
                if len(self.live[run_id]) > 3500:
                    self.live[run_id] = self.live[run_id][-3500:]

    def finish(self, run_id: str, bundle: dict, report: dict, duration_ms: float):
        path = self.bundle_path(run_id)
        tmp = path.with_suffix(".tmp")
        with tmp.open("w",encoding="utf-8") as file:
            json.dump({**bundle,"verification":report}, file, ensure_ascii=False, separators=(",", ":"),allow_nan=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp,path)
        self.set_status(run_id,"completed",duration_ms,report)
        with self._lock:
            self.live.pop(run_id,None)

    def bundle_path(self, run_id: str) -> Path:
        try:
            uuid.UUID(hex=run_id)
        except ValueError:
            raise ValueError("invalid run ID") from None
        return self.folder / f"{run_id}.json"

    def get(self, run_id: str, include_events: bool = True) -> dict | None:
        with self.conn() as c:
            result = c.execute("SELECT * FROM runs WHERE id=?",(run_id,)).fetchone()
        if not result:
            return None
        data = dict(result)
        data["shield"] = bool(data["shield"])
        data["summary"] = json.loads(data.pop("summary_json")) if data.get("summary_json") else None
        if include_events:
            path = self.bundle_path(run_id)
            if path.exists():
                with path.open(encoding="utf-8") as file:
                    bundle = json.load(file)
                data["events"] = bundle["events"]
                data["manifest"] = bundle["manifest"]
            else:
                with self._lock:
                    data["events"] = list(self.live.get(run_id,[]))
        return data

    def recent(self, limit=40) -> list[dict]:
        with self.conn() as c:
            rows = c.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (min(int(limit),200),)).fetchall()
        out = []
        for row in rows:
            rec = dict(row)
            rec["shield"] = bool(rec["shield"])
            rec["summary"] = json.loads(rec.pop("summary_json")) if rec.get("summary_json") else None
            out.append(rec)
        return out
