from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
import unicodedata
from pathlib import Path
from typing import Any


DEFAULT_FEN = "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR r"
DEFAULT_YOUTUBE_CHANNEL_ID = "UCM7pTdgZRwDZ2gZDtC6SITg"
DEFAULT_YOUTUBE_CHANNEL_HANDLE = "@XiangqiLab"
DEFAULT_YOUTUBE_CHANNEL_TITLE = "Xiangqi Lab | 中国象棋实验室"


def normalize_topic_key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower().strip()
    text = re.sub(r"^trending xiangqi(?: video)?\s*:\s*", "", text)
    text = re.sub(r"\s+[—–-]\s+series\s+\d+(?:\.\d+)?\s*$", "", text)
    text = re.sub(r"\s+\|\s+[^|]+$", "", text)
    text = re.sub(r"\s+-\s+.*$", "", text)
    text = re.sub(r"[^\w\u3400-\u9fff]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


class LocalStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or os.getenv("LOCAL_DB_PATH", "data/chinese_cheese_video.db"))
        if not self.db_path.is_absolute():
            self.db_path = Path(__file__).resolve().parents[1] / self.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._seed_demo()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS xiangqi_puzzles (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    fen TEXT NOT NULL,
                    moves_json TEXT NOT NULL DEFAULT '[]',
                    language TEXT NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'zh')),
                    theme TEXT NOT NULL DEFAULT 'wood' CHECK (theme IN ('wood', 'paper')),
                    is_active INTEGER NOT NULL DEFAULT 1,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS video_jobs (
                    id TEXT PRIMARY KEY,
                    puzzle_id TEXT,
                    title TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'zh')),
                    status TEXT NOT NULL DEFAULT 'queued',
                    input_payload_json TEXT NOT NULL DEFAULT '{}',
                    output_payload_json TEXT NOT NULL DEFAULT '{}',
                    output_url TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (puzzle_id) REFERENCES xiangqi_puzzles(id) ON DELETE SET NULL
                );
                CREATE TABLE IF NOT EXISTS content_candidates (
                    id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL UNIQUE,
                    content_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'zh')),
                    source_kind TEXT NOT NULL DEFAULT 'generated',
                    source_url TEXT,
                    status TEXT NOT NULL DEFAULT 'discovered',
                    priority_score REAL NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    published_job_id TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS ai_provider_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    slot_id TEXT NOT NULL,
                    project TEXT NOT NULL DEFAULT 'default',
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_class TEXT,
                    error_message TEXT,
                    status_code INTEGER,
                    usage_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS ai_provider_state (
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    slot_id TEXT NOT NULL,
                    project TEXT NOT NULL DEFAULT 'default',
                    consecutive_failures INTEGER NOT NULL DEFAULT 0,
                    total_calls INTEGER NOT NULL DEFAULT 0,
                    total_successes INTEGER NOT NULL DEFAULT 0,
                    cooldown_until TEXT,
                    last_error TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (provider, model, slot_id)
                );
                CREATE TABLE IF NOT EXISTS automation_runs (
                    id TEXT PRIMARY KEY,
                    trigger_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    metrics_json TEXT NOT NULL DEFAULT '{}',
                    error_message TEXT
                );
                CREATE TABLE IF NOT EXISTS youtube_publications (
                    job_id TEXT PRIMARY KEY,
                    language TEXT NOT NULL CHECK (language IN ('en', 'zh')),
                    content_type TEXT NOT NULL DEFAULT 'definition',
                    status TEXT NOT NULL DEFAULT 'not_started',
                    video_id TEXT,
                    video_url TEXT,
                    playlist_id TEXT,
                    playlist_url TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS xiangqi_puzzles_active_created_idx
                    ON xiangqi_puzzles (is_active, created_at DESC);
                CREATE INDEX IF NOT EXISTS video_jobs_status_created_idx
                    ON video_jobs (status, created_at DESC);
                CREATE INDEX IF NOT EXISTS content_candidates_status_score_idx
                    ON content_candidates (status, priority_score DESC, created_at ASC);
                CREATE INDEX IF NOT EXISTS ai_provider_calls_created_idx
                    ON ai_provider_calls (created_at DESC);
                CREATE INDEX IF NOT EXISTS youtube_publications_status_updated_idx
                    ON youtube_publications (status, updated_at DESC);
                CREATE TABLE IF NOT EXISTS youtube_channels (
                    channel_id TEXT PRIMARY KEY,
                    handle TEXT NOT NULL,
                    title TEXT NOT NULL,
                    channel_url TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'configured',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS youtube_playlists (
                    playlist_key TEXT PRIMARY KEY,
                    language TEXT NOT NULL CHECK (language IN ('en', 'zh')),
                    content_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    privacy_status TEXT NOT NULL DEFAULT 'public',
                    youtube_playlist_id TEXT,
                    playlist_url TEXT,
                    status TEXT NOT NULL DEFAULT 'configured',
                    error_message TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS youtube_videos (
                    job_id TEXT PRIMARY KEY,
                    candidate_id TEXT,
                    language TEXT NOT NULL CHECK (language IN ('en', 'zh')),
                    content_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source_kind TEXT,
                    source_url TEXT,
                    duration_seconds REAL,
                    video_id TEXT,
                    video_url TEXT,
                    privacy_status TEXT,
                    playlist_key TEXT,
                    audio_path TEXT,
                    video_path TEXT,
                    captions_source TEXT NOT NULL DEFAULT 'edge_tts_word_boundaries',
                    narration_sha256 TEXT,
                    captions_sha256 TEXT,
                    status TEXT NOT NULL DEFAULT 'rendered',
                    published_at TEXT,
                    error_message TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (playlist_key) REFERENCES youtube_playlists(playlist_key)
                );
                CREATE TABLE IF NOT EXISTS youtube_video_playlists (
                    job_id TEXT NOT NULL,
                    playlist_key TEXT NOT NULL,
                    youtube_playlist_id TEXT,
                    playlist_item_id TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (job_id, playlist_key),
                    FOREIGN KEY (job_id) REFERENCES youtube_videos(job_id) ON DELETE CASCADE,
                    FOREIGN KEY (playlist_key) REFERENCES youtube_playlists(playlist_key)
                );
                CREATE INDEX IF NOT EXISTS youtube_playlists_youtube_id_idx
                    ON youtube_playlists (youtube_playlist_id);
                CREATE INDEX IF NOT EXISTS youtube_videos_status_updated_idx
                    ON youtube_videos (status, updated_at DESC);
                CREATE INDEX IF NOT EXISTS youtube_videos_video_id_idx
                    ON youtube_videos (video_id);
                CREATE INDEX IF NOT EXISTS youtube_video_playlists_playlist_idx
                    ON youtube_video_playlists (playlist_key, status);
                """
            )
        self._seed_youtube_catalog()
        self._backfill_youtube_catalog_from_publications()

    def _seed_youtube_catalog(self) -> None:
        """Seed the configured channel and all playlist definitions idempotently."""
        now = datetime.now(timezone.utc).isoformat()
        channel_id = os.getenv("YOUTUBE_CHANNEL_ID", DEFAULT_YOUTUBE_CHANNEL_ID)
        handle = os.getenv("YOUTUBE_CHANNEL_HANDLE", DEFAULT_YOUTUBE_CHANNEL_HANDLE)
        title = os.getenv("YOUTUBE_CHANNEL_TITLE", DEFAULT_YOUTUBE_CHANNEL_TITLE)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO youtube_channels (channel_id, handle, title, channel_url, status, updated_at)
                VALUES (?, ?, ?, ?, 'configured', ?)
                ON CONFLICT(channel_id) DO UPDATE SET handle=excluded.handle, title=excluded.title,
                    channel_url=excluded.channel_url, updated_at=excluded.updated_at
                """,
                (channel_id, handle, title, f"https://www.youtube.com/channel/{channel_id}", now),
            )
            config_path = Path(__file__).resolve().parents[1] / "config" / "youtube_playlists.json"
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                config = {"playlists": {}}
            for playlist_key, item in (config.get("playlists") or {}).items():
                language = str(item.get("language") or "en")
                if language not in {"en", "zh"}:
                    continue
                connection.execute(
                    """
                    INSERT INTO youtube_playlists
                        (playlist_key, language, content_type, title, description, privacy_status, status, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'configured', ?)
                    ON CONFLICT(playlist_key) DO UPDATE SET language=excluded.language,
                        title=excluded.title, description=excluded.description,
                        privacy_status=excluded.privacy_status, updated_at=excluded.updated_at
                    """,
                    (
                        playlist_key,
                        language,
                        playlist_key.removeprefix(f"{language}-"),
                        str(item.get("title") or playlist_key),
                        str(item.get("description") or ""),
                        str(config.get("privacy_status") or "public"),
                        now,
                    ),
                )

    def _backfill_youtube_catalog_from_publications(self) -> None:
        """Materialize old publication rows into the normalized YouTube catalog."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT job_id, language, content_type, status, video_id, video_url, playlist_id, playlist_url, metadata_json, error_message FROM youtube_publications WHERE video_id IS NOT NULL"
            ).fetchall()
            for row in rows:
                metadata = json.loads(row["metadata_json"] or "{}")
                playlist_key = metadata.get("playlist_key")
                if not playlist_key:
                    suffix = {
                        "definition": "start-here",
                        "rules": "piece-academy",
                        "opening": "openings",
                        "tactics": "tactics",
                        "endgame": "endgames",
                        "full_game": "full-games",
                        "advanced_puzzle": "puzzle-ladder",
                        "comparison": "comparisons",
                        "trend_breakdown": "trending-xiangqi",
                        "skill_match": "skill-matches",
                        "viewer_challenge": "viewer-challenges",
                    }.get(row["content_type"], "start-here")
                    playlist_key = f"{row['language']}-{suffix}"
                connection.execute(
                    "UPDATE youtube_playlists SET youtube_playlist_id = COALESCE(?, youtube_playlist_id), playlist_url = COALESCE(?, playlist_url), status = CASE WHEN ? = 'published' THEN 'published' ELSE status END, updated_at = CURRENT_TIMESTAMP WHERE playlist_key = ?",
                    (row["playlist_id"], row["playlist_url"], row["status"], playlist_key),
                )
                title = str(metadata.get("title") or row["job_id"])
                connection.execute(
                    """
                    INSERT INTO youtube_videos
                        (job_id, language, content_type, title, video_id, video_url, privacy_status,
                         playlist_key, captions_source, status, error_message, metadata_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'edge_tts_word_boundaries', ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(job_id) DO UPDATE SET video_id=COALESCE(excluded.video_id, youtube_videos.video_id),
                        video_url=COALESCE(excluded.video_url, youtube_videos.video_url),
                        playlist_key=COALESCE(excluded.playlist_key, youtube_videos.playlist_key),
                        status=excluded.status, error_message=excluded.error_message,
                        metadata_json=CASE WHEN excluded.metadata_json='{}' THEN youtube_videos.metadata_json ELSE excluded.metadata_json END,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (
                        row["job_id"], row["language"], row["content_type"], title,
                        row["video_id"], row["video_url"], "public", playlist_key,
                        row["status"], row["error_message"], row["metadata_json"] or "{}",
                    ),
                )
                if row["playlist_id"]:
                    connection.execute(
                        """
                        INSERT INTO youtube_video_playlists
                            (job_id, playlist_key, youtube_playlist_id, status, error_message, updated_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(job_id, playlist_key) DO UPDATE SET youtube_playlist_id=excluded.youtube_playlist_id,
                            status=excluded.status, error_message=excluded.error_message, updated_at=CURRENT_TIMESTAMP
                        """,
                        (row["job_id"], playlist_key, row["playlist_id"], row["status"], row["error_message"]),
                    )

    def _seed_demo(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO xiangqi_puzzles
                    (id, title, fen, moves_json, language, theme, metadata_json)
                VALUES (?, ?, ?, ?, 'en', 'wood', ?)
                """,
                (
                    "demo-left-wing",
                    "The Quiet Trap on the Left Wing",
                    DEFAULT_FEN,
                    json.dumps(["0,6-0,5", "0,3-0,4", "1,7-1,4"]),
                    json.dumps({"source": "local-seed"}),
                ),
            )

    def list_puzzles(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, fen, moves_json, language, theme, metadata_json
                FROM xiangqi_puzzles
                WHERE is_active = 1
                ORDER BY created_at DESC
                LIMIT 100
                """
            ).fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "fen": row["fen"],
                "moves": json.loads(row["moves_json"]),
                "language": row["language"],
                "theme": row["theme"],
                **json.loads(row["metadata_json"]),
            }
            for row in rows
        ]

    def create_job(self, job: dict[str, Any], puzzle_id: str | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO video_jobs
                    (id, puzzle_id, title, language, status, input_payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'processing', ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    language = excluded.language,
                    status = excluded.status,
                    input_payload_json = excluded.input_payload_json,
                    updated_at = excluded.updated_at
                """,
                (job["id"], puzzle_id, job["title"], job["language"], json.dumps(job, ensure_ascii=False), now, now),
            )

    def update_job(self, job_id: str, status: str, **fields: Any) -> None:
        now = datetime.now(timezone.utc).isoformat()
        assignments = ["status = ?", "updated_at = ?"]
        values: list[Any] = [status, now]
        if "output_url" in fields:
            assignments.append("output_url = ?")
            values.append(fields["output_url"])
        if "output_payload" in fields:
            assignments.append("output_payload_json = ?")
            values.append(json.dumps(fields["output_payload"], ensure_ascii=False))
        if "error_message" in fields:
            assignments.append("error_message = ?")
            values.append(fields["error_message"])
        values.append(job_id)
        with self._connect() as connection:
            connection.execute(f"UPDATE video_jobs SET {', '.join(assignments)} WHERE id = ?", values)

    def add_candidate(self, candidate: dict[str, Any]) -> bool:
        fingerprint = candidate.get("fingerprint") or self.fingerprint(candidate)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            result = connection.execute(
                """
                INSERT OR IGNORE INTO content_candidates
                    (id, fingerprint, content_type, title, language, source_kind, source_url, status, priority_score, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.get("id") or f"candidate-{fingerprint[:16]}",
                    fingerprint,
                    candidate.get("content_type", "puzzle"),
                    candidate.get("title", "Untitled Xiangqi idea"),
                    candidate.get("language", "en"),
                    candidate.get("source_kind", "generated"),
                    candidate.get("source_url"),
                    candidate.get("status", "discovered"),
                    float(candidate.get("priority_score", 0)),
                    json.dumps(candidate.get("payload", candidate), ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return result.rowcount == 1

    def candidate_exists(self, fingerprint: str) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT 1 FROM content_candidates WHERE fingerprint = ? LIMIT 1", (fingerprint,)).fetchone()
        return row is not None

    def list_candidates(self, status: str = "discovered", limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, fingerprint, content_type, title, language, source_kind, source_url, status, priority_score, payload_json
                FROM content_candidates
                WHERE status = ?
                ORDER BY priority_score DESC, created_at ASC
                LIMIT ?
                """,
                (status, int(limit)),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "fingerprint": row["fingerprint"],
                "content_type": row["content_type"],
                "title": row["title"],
                "language": row["language"],
                "source_kind": row["source_kind"],
                "source_url": row["source_url"],
                "status": row["status"],
                "priority_score": row["priority_score"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def update_candidate(self, candidate_id: str, status: str, published_job_id: str | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                "UPDATE content_candidates SET status = ?, published_job_id = COALESCE(?, published_job_id), updated_at = ? WHERE id = ?",
                (status, published_job_id, now, candidate_id),
            )

    @staticmethod
    def fingerprint(candidate: dict[str, Any]) -> str:
        payload = candidate.get("payload") or {}
        topic_key = candidate.get("topic_key") or payload.get("topic_key") or normalize_topic_key(candidate.get("title", ""))
        stable = {
            "content_type": candidate.get("content_type", "puzzle"),
            "language": candidate.get("language", "en"),
            "topic_key": normalize_topic_key(topic_key),
            "title": "" if topic_key else str(candidate.get("title", "")).strip().lower(),
            "fen": candidate.get("fen") or payload.get("fen", ""),
            "moves": candidate.get("moves") or payload.get("moves", []),
            "pairing": candidate.get("pairing") or payload.get("pairing", {}),
        }
        return hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    def get_published_topic_keys(self, language: str | None = None) -> set[str]:
        query = "SELECT language, payload_json, title FROM content_candidates WHERE status = 'published'"
        params: tuple[Any, ...] = ()
        if language:
            query += " AND language = ?"
            params = (language,)
        keys: set[str] = set()
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        for row in rows:
            try:
                payload = json.loads(row["payload_json"] or "{}")
            except json.JSONDecodeError:
                payload = {}
            key = payload.get("topic_key") or normalize_topic_key(row["title"])
            if key:
                keys.add(normalize_topic_key(key))
        return keys

    def get_recent_content_types(self, language: str = "en", limit: int = 8) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT content_type FROM content_candidates WHERE status = 'published' AND language = ? ORDER BY updated_at DESC LIMIT ?",
                (language, int(limit)),
            ).fetchall()
        return [str(row["content_type"]) for row in rows]

    def get_published_move_signatures(self, language: str = "en", limit: int = 100) -> set[str]:
        """Return signatures of board sequences already rendered/published."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT input_payload_json FROM video_jobs WHERE language = ? AND status IN ('completed', 'processing') ORDER BY updated_at DESC LIMIT ?",
                (language, int(limit)),
            ).fetchall()
        signatures: set[str] = set()
        for row in rows:
            try:
                payload = json.loads(row["input_payload_json"] or "{}")
            except json.JSONDecodeError:
                continue
            signature = json.dumps(
                {"fen": payload.get("fen"), "moves": payload.get("moves") or []},
                ensure_ascii=False,
                sort_keys=True,
            )
            signatures.add(signature)
        return signatures

    def get_provider_state(self, provider: str, model: str, slot_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT provider, model, slot_id, project, consecutive_failures, total_calls, total_successes, cooldown_until, last_error, updated_at FROM ai_provider_state WHERE provider = ? AND model = ? AND slot_id = ?",
                (provider, model, slot_id),
            ).fetchone()
        return dict(row) if row else None

    def record_provider_call(self, *, provider: str, model: str, slot_id: str, project: str, operation: str, status: str, usage: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO ai_provider_calls (provider, model, slot_id, project, operation, status, usage_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (provider, model, slot_id, project, operation, status, json.dumps(usage, ensure_ascii=False), now),
            )
            connection.execute(
                """
                INSERT INTO ai_provider_state (provider, model, slot_id, project, consecutive_failures, total_calls, total_successes, cooldown_until, last_error, updated_at)
                VALUES (?, ?, ?, ?, 0, 1, 1, NULL, NULL, ?)
                ON CONFLICT(provider, model, slot_id) DO UPDATE SET
                    project = excluded.project,
                    consecutive_failures = 0,
                    total_calls = ai_provider_state.total_calls + 1,
                    total_successes = ai_provider_state.total_successes + 1,
                    cooldown_until = NULL,
                    last_error = NULL,
                    updated_at = excluded.updated_at
                """,
                (provider, model, slot_id, project, now),
            )

    def record_provider_failure(self, *, provider: str, model: str, slot_id: str, project: str, operation: str, error_class: str, error_message: str, cooldown_seconds: int, status_code: int | None) -> None:
        now = datetime.now(timezone.utc)
        cooldown_until = (now + timedelta(seconds=cooldown_seconds)).isoformat() if cooldown_seconds else None
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO ai_provider_calls (provider, model, slot_id, project, operation, status, error_class, error_message, status_code, created_at) VALUES (?, ?, ?, ?, ?, 'failed', ?, ?, ?, ?)",
                (provider, model, slot_id, project, operation, error_class, error_message[:2000], status_code, now.isoformat()),
            )
            connection.execute(
                """
                INSERT INTO ai_provider_state (provider, model, slot_id, project, consecutive_failures, total_calls, total_successes, cooldown_until, last_error, updated_at)
                VALUES (?, ?, ?, ?, 1, 1, 0, ?, ?, ?)
                ON CONFLICT(provider, model, slot_id) DO UPDATE SET
                    project = excluded.project,
                    consecutive_failures = ai_provider_state.consecutive_failures + 1,
                    total_calls = ai_provider_state.total_calls + 1,
                    cooldown_until = excluded.cooldown_until,
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at
                """,
                (provider, model, slot_id, project, cooldown_until, error_message[:2000], now.isoformat()),
            )

    def start_run(self, run_id: str, trigger_name: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO automation_runs (id, trigger_name, status, started_at) VALUES (?, ?, 'running', ?)",
                (run_id, trigger_name, datetime.now(timezone.utc).isoformat()),
            )

    def finish_run(self, run_id: str, status: str, metrics: dict[str, Any] | None = None, error_message: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE automation_runs SET status = ?, finished_at = ?, metrics_json = ?, error_message = ? WHERE id = ?",
                (status, datetime.now(timezone.utc).isoformat(), json.dumps(metrics or {}, ensure_ascii=False), error_message, run_id),
            )

    def upsert_youtube_catalog(
        self,
        job: dict[str, Any],
        publication: dict[str, Any] | None = None,
        *,
        candidate_id: str | None = None,
        audio_path: str | Path | None = None,
        video_path: str | Path | None = None,
    ) -> None:
        """Persist normalized channel, playlist, video, and association state."""
        publication = publication or {}
        language = str(job.get("language") or "en")
        language = "zh" if language in {"zh", "cn", "chinese"} else "en"
        content_type = str(job.get("content_type") or "definition")
        metadata = publication.get("metadata") or {}
        playlist_key = str(metadata.get("playlist_key") or "").strip()
        if not playlist_key:
            suffix = {
                "definition": "start-here", "rules": "piece-academy", "opening": "openings",
                "tactics": "tactics", "endgame": "endgames", "full_game": "full-games",
                "advanced_puzzle": "puzzle-ladder", "comparison": "comparisons",
                "trend_breakdown": "trending-xiangqi", "skill_match": "skill-matches",
                "viewer_challenge": "viewer-challenges",
            }.get(content_type, "start-here")
            playlist_key = f"{language}-{suffix}"
        status = str(publication.get("status") or "rendered")
        now = datetime.now(timezone.utc).isoformat()
        narration_hash = hashlib.sha256(str(job.get("narration") or "").encode("utf-8")).hexdigest()
        captions_hash = hashlib.sha256(json.dumps(job.get("captions") or [], ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        playlist_id = str(publication.get("playlist_id") or "").strip() or None
        playlist_url = str(publication.get("playlist_url") or "").strip() or None
        playlist_item_id = str((publication.get("playlist_item") or {}).get("id") or "").strip() or None
        video_id = str(publication.get("video_id") or "").strip() or None
        video_url = str(publication.get("video_url") or "").strip() or None
        error_message = publication.get("error_message")
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE youtube_playlists SET youtube_playlist_id=COALESCE(?, youtube_playlist_id),
                    playlist_url=COALESCE(?, playlist_url), status=CASE WHEN ?='published' THEN 'published' ELSE status END,
                    error_message=?, updated_at=? WHERE playlist_key=?
                """,
                (playlist_id, playlist_url, status, error_message, now, playlist_key),
            )
            connection.execute(
                """
                INSERT INTO youtube_videos
                    (job_id, candidate_id, language, content_type, title, source_kind, source_url,
                     duration_seconds, video_id, video_url, privacy_status, playlist_key, audio_path,
                     video_path, captions_source, narration_sha256, captions_sha256, status, published_at,
                     error_message, metadata_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'edge_tts_word_boundaries', ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET candidate_id=COALESCE(excluded.candidate_id, youtube_videos.candidate_id),
                    title=excluded.title, source_kind=excluded.source_kind, source_url=excluded.source_url,
                    duration_seconds=excluded.duration_seconds, video_id=COALESCE(excluded.video_id, youtube_videos.video_id),
                    video_url=COALESCE(excluded.video_url, youtube_videos.video_url), privacy_status=excluded.privacy_status,
                    playlist_key=COALESCE(excluded.playlist_key, youtube_videos.playlist_key), audio_path=COALESCE(excluded.audio_path, youtube_videos.audio_path),
                    video_path=COALESCE(excluded.video_path, youtube_videos.video_path), captions_source=excluded.captions_source,
                    narration_sha256=excluded.narration_sha256, captions_sha256=excluded.captions_sha256,
                    status=excluded.status, published_at=COALESCE(excluded.published_at, youtube_videos.published_at),
                    error_message=excluded.error_message, metadata_json=CASE WHEN excluded.metadata_json='{}' THEN youtube_videos.metadata_json ELSE excluded.metadata_json END,
                    updated_at=excluded.updated_at
                """,
                (
                    str(job.get("id") or ""), candidate_id, language, content_type, str(job.get("title") or "Untitled"),
                    job.get("source_kind"), job.get("source_url"), float(job.get("durationInSeconds") or 0),
                    video_id, video_url, str(metadata.get("privacyStatus") or os.getenv("YOUTUBE_PUBLISH_MODE", "public")),
                    playlist_key, str(audio_path) if audio_path else None, str(video_path) if video_path else None,
                    narration_hash, captions_hash, status, now if status == "published" else None,
                    error_message, json.dumps(metadata, ensure_ascii=False), now,
                ),
            )
            if playlist_id:
                connection.execute(
                    """
                    INSERT INTO youtube_video_playlists
                        (job_id, playlist_key, youtube_playlist_id, playlist_item_id, status, error_message, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(job_id, playlist_key) DO UPDATE SET youtube_playlist_id=excluded.youtube_playlist_id,
                        playlist_item_id=COALESCE(excluded.playlist_item_id, youtube_video_playlists.playlist_item_id),
                        status=excluded.status, error_message=excluded.error_message, updated_at=excluded.updated_at
                    """,
                    (str(job.get("id") or ""), playlist_key, playlist_id, playlist_item_id, status, error_message, now),
                )

    def get_youtube_catalog(self, limit: int = 100) -> dict[str, list[dict[str, Any]]]:
        with self._connect() as connection:
            channel_rows = connection.execute("SELECT channel_id, handle, title, channel_url, status FROM youtube_channels LIMIT 10").fetchall()
            playlist_rows = connection.execute("SELECT playlist_key, language, content_type, title, youtube_playlist_id, playlist_url, status FROM youtube_playlists ORDER BY language, playlist_key LIMIT ?", (int(limit),)).fetchall()
            video_rows = connection.execute("SELECT job_id, language, content_type, title, video_id, video_url, playlist_key, status, captions_source, narration_sha256, captions_sha256 FROM youtube_videos ORDER BY updated_at DESC LIMIT ?", (int(limit),)).fetchall()
            association_rows = connection.execute("SELECT job_id, playlist_key, youtube_playlist_id, playlist_item_id, status FROM youtube_video_playlists ORDER BY updated_at DESC LIMIT ?", (int(limit),)).fetchall()
        return {
            "channels": [dict(row) for row in channel_rows],
            "playlists": [dict(row) for row in playlist_rows],
            "videos": [dict(row) for row in video_rows],
            "video_playlists": [dict(row) for row in association_rows],
        }

    def get_youtube_publication(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT job_id, language, content_type, status, video_id, video_url, playlist_id, playlist_url, metadata_json, attempts, error_message, created_at, updated_at FROM youtube_publications WHERE job_id = ? LIMIT 1",
                (job_id,),
            ).fetchone()
        if not row:
            return None
        value = dict(row)
        value["metadata"] = json.loads(value.pop("metadata_json") or "{}")
        return value

    def upsert_youtube_publication(self, job_id: str, language: str, content_type: str, status: str, **fields: Any) -> None:
        now = datetime.now(timezone.utc).isoformat()
        metadata = fields.get("metadata", {})
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO youtube_publications
                    (job_id, language, content_type, status, video_id, video_url, playlist_id, playlist_url, metadata_json, attempts, error_message, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    language = excluded.language,
                    content_type = excluded.content_type,
                    status = excluded.status,
                    video_id = COALESCE(excluded.video_id, youtube_publications.video_id),
                    video_url = COALESCE(excluded.video_url, youtube_publications.video_url),
                    playlist_id = CASE WHEN excluded.playlist_id IS NULL AND excluded.status IN ('failed', 'uploaded_playlist_pending') THEN NULL ELSE COALESCE(excluded.playlist_id, youtube_publications.playlist_id) END,
                    playlist_url = CASE WHEN excluded.playlist_url IS NULL AND excluded.status IN ('failed', 'uploaded_playlist_pending') THEN NULL ELSE COALESCE(excluded.playlist_url, youtube_publications.playlist_url) END,
                    metadata_json = CASE WHEN excluded.metadata_json = '{}' THEN youtube_publications.metadata_json ELSE excluded.metadata_json END,
                    attempts = youtube_publications.attempts + 1,
                    error_message = excluded.error_message,
                    updated_at = excluded.updated_at
                """,
                (
                    job_id,
                    language,
                    content_type,
                    status,
                    fields.get("video_id"),
                    fields.get("video_url"),
                    fields.get("playlist_id"),
                    fields.get("playlist_url"),
                    json.dumps(metadata, ensure_ascii=False),
                    fields.get("error_message"),
                    now,
                    now,
                ),
            )

    def upload(self, bucket: str, object_path: str, file_path: str | Path, content_type: str) -> str:
        destination = self.db_path.parent / "local_storage" / bucket / object_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(Path(file_path).read_bytes())
        return f"local://{bucket}/{object_path}"

    def checkpoint(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def health(self) -> dict[str, Any]:
        with self._connect() as connection:
            candidates = connection.execute("SELECT COUNT(*) FROM content_candidates").fetchone()[0]
            calls = connection.execute("SELECT COUNT(*) FROM ai_provider_calls").fetchone()[0]
            runs = connection.execute("SELECT COUNT(*) FROM automation_runs").fetchone()[0]
        return {
            "backend": "sqlite",
            "db_path": str(self.db_path),
            "puzzles": len(self.list_puzzles()),
            "candidates": candidates,
            "ai_provider_calls": calls,
            "automation_runs": runs,
        }
