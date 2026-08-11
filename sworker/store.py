"""Local execution store: sqlite for query, append-only JSONL for audit.

Two writes per object on purpose. The sqlite tables are an *index* — they exist
so `worker runs` is fast. The JSONL ledger is the *truth*: append-only, never
edited, never deleted, one line per event, so a Run can be reconstructed even if
the database is deleted. Same discipline as AtlasStore.changelog.

Everything lives under the workspace root. Nothing leaves the machine.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, Iterator, List, Optional

from .models import Record

SCHEMA_VERSION = 1

# table -> extra indexed columns (beyond id + json blob)
TABLES: Dict[str, List[str]] = {
    "tasks": ["worker", "created", "origin", "procedure"],
    "plans": ["run_id", "task_id", "created"],
    "steps": ["run_id", "plan_id", "idx", "status"],
    "runs": ["task_id", "worker", "status", "started", "seq"],
    "actions": ["run_id", "step_id", "tool", "risk", "status", "created"],
    "observations": ["run_id", "action_id", "ok", "created"],
    "evidence": ["run_id", "provenance", "created"],
    "claims": ["run_id", "confidence", "provenance", "created"],
    "verifications": ["run_id", "claim_id", "outcome", "created"],
    "approvals": ["run_id", "action_id", "state", "risk", "created"],
    "artifacts": ["run_id", "kind", "created", "path"],
    "procedures": ["name", "worker", "created"],
    "schedules": ["worker", "procedure", "cron", "enabled", "next_run"],
}

# dataclass field name -> column name, where they differ
COLUMN_ALIASES = {"steps": {"index": "idx"}}


class WorkerStore:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)
        self.db_path = os.path.join(self.root, "worker.db")
        self.audit_path = os.path.join(self.root, "audit.jsonl")
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    # -- schema ------------------------------------------------------------
    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
        for table, cols in TABLES.items():
            coldefs = ", ".join(f"{c} TEXT" for c in cols)
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {table} "
                f"(id TEXT PRIMARY KEY, {coldefs}, json TEXT NOT NULL)"
            )
            for c in cols:
                cur.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_{c} ON {table}({c})")
        cur.execute(
            "INSERT OR REPLACE INTO meta (k, v) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self._conn.commit()

    # -- audit -------------------------------------------------------------
    def audit(self, event: str, table: str, record_id: str, payload: Dict[str, Any]) -> None:
        line = json.dumps(
            {
                "ts": time.time(),
                "event": event,
                "table": table,
                "id": record_id,
                "payload": payload,
            },
            sort_keys=True,
            default=str,
        )
        with open(self.audit_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def iter_audit(self, run_id: str = "") -> Iterator[Dict[str, Any]]:
        if not os.path.exists(self.audit_path):
            return
        with open(self.audit_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if run_id:
                    p = rec.get("payload") or {}
                    if run_id not in (p.get("run_id"), rec.get("id")):
                        continue
                yield rec

    # -- crud --------------------------------------------------------------
    def put(self, table: str, obj: Record | Dict[str, Any], event: str = "put") -> Dict[str, Any]:
        d = obj.to_dict() if isinstance(obj, Record) else dict(obj)
        cols = TABLES[table]
        aliases = COLUMN_ALIASES.get(table, {})
        rev = {v: k for k, v in aliases.items()}
        values = []
        for c in cols:
            src = rev.get(c, c)
            v = d.get(src)
            values.append(None if v is None else str(v))
        placeholders = ", ".join("?" for _ in range(len(cols) + 2))
        with self._lock:
            self._conn.execute(
                f"INSERT OR REPLACE INTO {table} (id, {', '.join(cols)}, json) "
                f"VALUES ({placeholders})",
                [d["id"], *values, json.dumps(d, sort_keys=True, default=str)],
            )
            self._conn.commit()
        self.audit(event, table, d["id"], d)
        return d

    def get(self, table: str, record_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            f"SELECT json FROM {table} WHERE id = ?", (record_id,)
        ).fetchone()
        return json.loads(row["json"]) if row else None

    def find(
        self, table: str, order: str = "created", desc: bool = False, limit: int = 0, **where: Any
    ) -> List[Dict[str, Any]]:
        cols = TABLES[table]
        clauses, params = [], []
        for k, v in where.items():
            col = COLUMN_ALIASES.get(table, {}).get(k, k)
            if col not in cols:
                raise ValueError(f"{table} has no indexed column {col!r}")
            clauses.append(f"{col} = ?")
            params.append(str(v))
        sql = f"SELECT json FROM {table}"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        if order in cols:
            # every indexed column is TEXT; numeric ones must sort numerically
            key = f"CAST({order} AS REAL)" if order in ("created", "started", "seq", "idx", "next_run") else order
            sql += f" ORDER BY {key} {'DESC' if desc else 'ASC'}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [json.loads(r["json"]) for r in self._conn.execute(sql, params)]

    def count(self, table: str, **where: Any) -> int:
        return len(self.find(table, **where))

    def next_seq(self) -> int:
        row = self._conn.execute("SELECT MAX(CAST(seq AS INTEGER)) AS m FROM runs").fetchone()
        return int(row["m"] or 0) + 1

    def close(self) -> None:
        self._conn.close()
