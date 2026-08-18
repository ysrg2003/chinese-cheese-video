from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]


def normalize_topic_key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower().strip()
    return " ".join(text.split())[:500]


def candidate_fingerprint(payload: dict[str, Any]) -> str:
    identity = {
        "domainId": payload.get("domainId") or payload.get("domain_id"),
        "contentType": payload.get("contentType") or payload.get("content_type"),
        "language": payload.get("language"),
        "title": normalize_topic_key(payload.get("title")),
        "topic": normalize_topic_key(payload.get("topic")),
        "sourceUrl": payload.get("sourceUrl") or payload.get("source_url"),
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class DurableStateStore:
    """Namespaced, domain-neutral state for variants, lineage, and automation evidence.

    The namespace prevents this reusable capsule from colliding with a host project's
    legacy tables. The host owns its main candidate/publication tables and may compose
    this store through an adapter.
    """

    def __init__(self, db_path: str | Path | None = None, *, namespace: str = "reusable") -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", namespace):
            raise ValueError("namespace must be a SQLite identifier")
        raw = db_path or os.getenv("LOCAL_DB_PATH", "data/chinese_cheese_video.db")
        self.db_path = Path(raw).expanduser()
        if not self.db_path.is_absolute():
            self.db_path = ROOT / self.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.namespace = namespace
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _table(self, suffix: str) -> str:
        return f"{self.namespace}_{suffix}"

    def _init_schema(self) -> None:
        variants = self._table("content_variants")
        lineage = self._table("short_lineage")
        runs = self._table("automation_runs")
        with self._connect() as db:
            db.executescript(
                f"""
                CREATE TABLE IF NOT EXISTS {variants} (
                    fingerprint TEXT PRIMARY KEY,
                    domain_id TEXT NOT NULL,
                    variant_kind TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'generated',
                    signature_json TEXT NOT NULL DEFAULT '{{}}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS {lineage} (
                    short_id TEXT PRIMARY KEY,
                    short_fingerprint TEXT NOT NULL UNIQUE,
                    parent_job_id TEXT NOT NULL,
                    parent_fingerprint TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    source_start_sec REAL NOT NULL,
                    source_end_sec REAL NOT NULL,
                    highlight_reason TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'generated',
                    metadata_json TEXT NOT NULL DEFAULT '{{}}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS {runs} (
                    run_id TEXT PRIMARY KEY,
                    domain_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT NOT NULL DEFAULT '{{}}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)

    def get_variant(self, fingerprint: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(f"SELECT * FROM {self._table('content_variants')} WHERE fingerprint=?", (fingerprint,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["signature"] = json.loads(result.pop("signature_json") or "{}")
        return result

    def record_variant(self, *, fingerprint: str, domain_id: str, variant_kind: str, job_id: str, signature: dict[str, Any], status: str = "generated") -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            db.execute(
                f"""INSERT INTO {self._table('content_variants')}
                    (fingerprint, domain_id, variant_kind, job_id, status, signature_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(fingerprint) DO UPDATE SET
                      domain_id=excluded.domain_id, variant_kind=excluded.variant_kind,
                      job_id=excluded.job_id, status=excluded.status,
                      signature_json=excluded.signature_json, updated_at=excluded.updated_at""",
                (fingerprint, domain_id, variant_kind, job_id, status, self._json(signature), now, now),
            )
        return self.get_variant(fingerprint) or {}

    def record_lineage(self, *, short_id: str, short_fingerprint: str, parent_job_id: str, parent_fingerprint: str, source_kind: str, source_start_sec: float, source_end_sec: float, highlight_reason: str, metadata: dict[str, Any] | None = None, status: str = "generated") -> dict[str, Any]:
        if source_end_sec <= source_start_sec:
            raise ValueError("lineage source_end_sec must be greater than source_start_sec")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            db.execute(
                f"""INSERT INTO {self._table('short_lineage')}
                    (short_id, short_fingerprint, parent_job_id, parent_fingerprint, source_kind,
                     source_start_sec, source_end_sec, highlight_reason, status, metadata_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(short_id) DO UPDATE SET
                      short_fingerprint=excluded.short_fingerprint, parent_job_id=excluded.parent_job_id,
                      parent_fingerprint=excluded.parent_fingerprint, source_kind=excluded.source_kind,
                      source_start_sec=excluded.source_start_sec, source_end_sec=excluded.source_end_sec,
                      highlight_reason=excluded.highlight_reason, status=excluded.status,
                      metadata_json=excluded.metadata_json, updated_at=excluded.updated_at""",
                (short_id, short_fingerprint, parent_job_id, parent_fingerprint, source_kind,
                 float(source_start_sec), float(source_end_sec), highlight_reason, status,
                 self._json(metadata), now, now),
            )
            row = db.execute(f"SELECT * FROM {self._table('short_lineage')} WHERE short_id=?", (short_id,)).fetchone()
        result = dict(row) if row else {}
        if result:
            result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
        return result

    def list_lineage(self, parent_job_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                f"SELECT * FROM {self._table('short_lineage')} WHERE parent_job_id=? ORDER BY source_start_sec ASC LIMIT ?",
                (parent_job_id, int(limit)),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            result.append(item)
        return result

    def record_automation_run(self, *, run_id: str, domain_id: str, status: str, result: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            db.execute(
                f"""INSERT INTO {self._table('automation_runs')}
                    (run_id, domain_id, status, result_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id) DO UPDATE SET domain_id=excluded.domain_id,
                      status=excluded.status, result_json=excluded.result_json, updated_at=excluded.updated_at""",
                (run_id, domain_id, status, self._json(result), now, now),
            )
            row = db.execute(f"SELECT * FROM {self._table('automation_runs')} WHERE run_id=?", (run_id,)).fetchone()
        output = dict(row) if row else {}
        if output:
            output["result"] = json.loads(output.pop("result_json") or "{}")
        return output


__all__ = ["DurableStateStore", "candidate_fingerprint", "normalize_topic_key"]
