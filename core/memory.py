"""Append-only SQLite event/memory ledger."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def content_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ticks (
    tick_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    signature TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    tick_id TEXT,
    kind TEXT NOT NULL,
    category TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    FOREIGN KEY(tick_id) REFERENCES ticks(tick_id)
);

CREATE TABLE IF NOT EXISTS public_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tick_id TEXT,
    timestamp TEXT NOT NULL,
    narration TEXT NOT NULL,
    content_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS personality_traits (
    trait TEXT PRIMARY KEY,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    first_observed TEXT NOT NULL,
    last_reviewed TEXT NOT NULL,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS personality_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trait TEXT NOT NULL,
    event_id TEXT NOT NULL,
    polarity TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(trait) REFERENCES personality_traits(trait)
);

CREATE TABLE IF NOT EXISTS self_model_revisions (
    revision INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    summary TEXT NOT NULL,
    content_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quota_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    requests_today INTEGER NOT NULL DEFAULT 0,
    quiet_mode INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blocked_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tick_id TEXT,
    timestamp TEXT NOT NULL,
    rule_id TEXT,
    reason TEXT NOT NULL,
    action_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS help_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    category TEXT NOT NULL,
    summary TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS brain_revisions (
    revision INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    summary TEXT NOT NULL
);
"""


@dataclass
class MemoryStore:
    db_path: Path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            row = conn.execute("SELECT 1 FROM quota_state WHERE id = 1").fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO quota_state (id, requests_today, quiet_mode, last_error, updated_at) VALUES (1, 0, 0, '', ?)",
                    (utc_now(),),
                )
            conn.commit()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            conn.commit()

    def next_tick_number(self) -> int:
        raw = self.get_meta("tick_counter", "0") or "0"
        return int(raw) + 1

    def allocate_tick_id(self, conn: sqlite3.Connection) -> str:
        row = conn.execute("SELECT value FROM meta WHERE key = 'tick_counter'").fetchone()
        current = int(row["value"]) if row else 0
        nxt = current + 1
        conn.execute(
            "INSERT INTO meta(key, value) VALUES('tick_counter', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(nxt),),
        )
        return f"tick_{nxt:09d}"

    def append_event(
        self,
        conn: sqlite3.Connection,
        *,
        event_id: str,
        tick_id: str | None,
        kind: str,
        category: str,
        payload: dict[str, Any],
        timestamp: str | None = None,
    ) -> str:
        ts = timestamp or utc_now()
        digest = content_hash(payload)
        conn.execute(
            """
            INSERT INTO events(event_id, tick_id, kind, category, timestamp, payload_json, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event_id, tick_id, kind, category, ts, json.dumps(payload, default=str), digest),
        )
        return digest

    def commit_tick(
        self,
        conn: sqlite3.Connection,
        *,
        tick_id: str,
        timestamp: str,
        payload: dict[str, Any],
        signature: str,
        public_narration: str | None,
        memory_event: dict[str, Any] | None = None,
    ) -> None:
        digest = content_hash(payload)
        conn.execute(
            """
            INSERT INTO ticks(tick_id, timestamp, payload_json, content_hash, signature)
            VALUES (?, ?, ?, ?, ?)
            """,
            (tick_id, timestamp, json.dumps(payload, default=str), digest, signature),
        )
        if memory_event is not None:
            self.append_event(
                conn,
                event_id=memory_event["event_id"],
                tick_id=tick_id,
                kind=memory_event.get("kind", "memory"),
                category=memory_event.get("category", "tick"),
                payload=memory_event.get("payload", {}),
                timestamp=timestamp,
            )
        if public_narration:
            conn.execute(
                """
                INSERT INTO public_events(tick_id, timestamp, narration, content_hash)
                VALUES (?, ?, ?, ?)
                """,
                (tick_id, timestamp, public_narration, content_hash(public_narration)),
            )

    def record_blocked(
        self,
        conn: sqlite3.Connection,
        *,
        tick_id: str,
        rule_id: str | None,
        reason: str,
        action: dict[str, Any],
    ) -> None:
        conn.execute(
            """
            INSERT INTO blocked_actions(tick_id, timestamp, rule_id, reason, action_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (tick_id, utc_now(), rule_id, reason, json.dumps(action, default=str)),
        )

    def known_memory_ids(self) -> set[str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT event_id FROM events WHERE kind = 'memory'").fetchall()
            return {r["event_id"] for r in rows}

    def recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT event_id, tick_id, kind, category, timestamp, payload_json FROM events ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            out: list[dict[str, Any]] = []
            for r in rows:
                out.append(
                    {
                        "event_id": r["event_id"],
                        "tick_id": r["tick_id"],
                        "kind": r["kind"],
                        "category": r["category"],
                        "timestamp": r["timestamp"],
                        "payload": json.loads(r["payload_json"]),
                    }
                )
            return out

    def recent_public_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT tick_id, timestamp, narration FROM public_events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows][::-1]

    def tick_count(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM ticks").fetchone()
            return int(row["c"])

    def latest_tick(self) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT tick_id, timestamp, payload_json, signature FROM ticks ORDER BY tick_id DESC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            return {
                "tick_id": row["tick_id"],
                "timestamp": row["timestamp"],
                "payload": json.loads(row["payload_json"]),
                "signature": row["signature"],
            }

    def get_quota(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM quota_state WHERE id = 1").fetchone()
            return dict(row) if row else {}

    def set_quota(self, *, requests_today: int | None = None, quiet_mode: bool | None = None, last_error: str | None = None) -> None:
        with self.connect() as conn:
            current = conn.execute("SELECT * FROM quota_state WHERE id = 1").fetchone()
            req = requests_today if requests_today is not None else current["requests_today"]
            quiet = int(quiet_mode) if quiet_mode is not None else current["quiet_mode"]
            err = last_error if last_error is not None else current["last_error"]
            conn.execute(
                "UPDATE quota_state SET requests_today = ?, quiet_mode = ?, last_error = ?, updated_at = ? WHERE id = 1",
                (req, quiet, err, utc_now()),
            )
            conn.commit()

    def list_traits(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT trait, confidence, status, first_observed, last_reviewed, evidence_count, summary FROM personality_traits ORDER BY confidence DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def upsert_trait(self, trait: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO personality_traits(trait, confidence, status, first_observed, last_reviewed, evidence_count, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trait) DO UPDATE SET
                    confidence = excluded.confidence,
                    status = excluded.status,
                    last_reviewed = excluded.last_reviewed,
                    evidence_count = excluded.evidence_count,
                    summary = excluded.summary
                """,
                (
                    trait["trait"],
                    trait["confidence"],
                    trait["status"],
                    trait["first_observed"],
                    trait["last_reviewed"],
                    trait["evidence_count"],
                    trait.get("summary", ""),
                ),
            )
            conn.commit()

    def add_trait_evidence(self, trait: str, event_id: str, polarity: str, note: str = "") -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO personality_evidence(trait, event_id, polarity, note) VALUES (?, ?, ?, ?)",
                (trait, event_id, polarity, note),
            )
            conn.commit()

    def trait_evidence(self, trait: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT event_id, polarity, note FROM personality_evidence WHERE trait = ?",
                (trait,),
            ).fetchall()
            return [dict(r) for r in rows]

    def open_help_requests(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, created_at, category, summary, status FROM help_requests WHERE status = 'open' ORDER BY id DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def latest_brain_revision(self) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT revision, timestamp, content_hash, summary FROM brain_revisions ORDER BY revision DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    def record_brain_revision(self, content_hash_value: str, summary: str) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COALESCE(MAX(revision), 0) AS m FROM brain_revisions").fetchone()
            rev = int(row["m"]) + 1
            conn.execute(
                "INSERT INTO brain_revisions(revision, timestamp, content_hash, summary) VALUES (?, ?, ?, ?)",
                (rev, utc_now(), content_hash_value, summary),
            )
            conn.commit()
            return rev

    def record_self_model_revision(self, summary: str, body_hash: str) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COALESCE(MAX(revision), 0) AS m FROM self_model_revisions").fetchone()
            rev = int(row["m"]) + 1
            conn.execute(
                "INSERT INTO self_model_revisions(revision, timestamp, summary, content_hash) VALUES (?, ?, ?, ?)",
                (rev, utc_now(), summary, body_hash),
            )
            conn.commit()
            return rev

    def action_counts(self, limit_ticks: int = 100) -> dict[str, int]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM ticks ORDER BY tick_id DESC LIMIT ?",
                (limit_ticks,),
            ).fetchall()
        counts: dict[str, int] = {}
        for row in rows:
            payload = json.loads(row["payload_json"])
            action = (payload.get("proposed_action") or {}).get("action_type")
            if action:
                counts[action] = counts.get(action, 0) + 1
        return counts
