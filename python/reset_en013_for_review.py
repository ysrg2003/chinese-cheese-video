"""Quarantine the old en-013 publication and prepare a safe review regeneration.

This changes only the local SQLite catalog. It never calls YouTube and never deletes
anything from the public channel. The old public identity is preserved in an audit
history table so an ordinary scheduled run cannot silently upload a replacement.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JOB_ID = "curriculum-en-013-the-horse-and-blocked-eye-en"
LESSON_KEY = "en-013-the-horse-and-blocked-eye"
EXPECTED_VIDEO_ID = "dw6V8q69hY8"
RESET_GROUP = "en013-grounded-review-regeneration-2026-08-15"
CONFIRMATION = "RESET_EN013_FOR_REVIEW"


class ResetError(RuntimeError):
    pass


def _rows(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(query, params).fetchall()]


def reset_for_review(db_path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        publication = connection.execute(
            "SELECT * FROM youtube_publications WHERE job_id = ? LIMIT 1", (JOB_ID,)
        ).fetchone()
        if publication is None:
            raise ResetError(f"No active publication row found for {JOB_ID}")
        publication = dict(publication)
        if str(publication.get("video_id") or "") != EXPECTED_VIDEO_ID:
            raise ResetError(
                f"Refusing reset: expected public video {EXPECTED_VIDEO_ID}, "
                f"found {publication.get('video_id')!r}"
            )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS publication_reset_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reset_group TEXT NOT NULL,
                job_id TEXT NOT NULL,
                original_video_id TEXT NOT NULL,
                verification_run_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                reset_at TEXT NOT NULL,
                UNIQUE(reset_group, job_id)
            )"""
        )
        existing = connection.execute(
            "SELECT 1 FROM publication_reset_history WHERE reset_group = ? AND job_id = ? LIMIT 1",
            (RESET_GROUP, JOB_ID),
        ).fetchone()
        if existing:
            return {
                "status": "already_reset",
                "reset_group": RESET_GROUP,
                "job_id": JOB_ID,
                "lesson_key": LESSON_KEY,
                "original_video_id": EXPECTED_VIDEO_ID,
                "dry_run": dry_run,
            }
        snapshot = {
            "youtube_publication": publication,
            "youtube_video": _rows(connection, "SELECT * FROM youtube_videos WHERE job_id = ?", (JOB_ID,)),
            "youtube_video_playlists": _rows(connection, "SELECT * FROM youtube_video_playlists WHERE job_id = ?", (JOB_ID,)),
            "video_job": _rows(connection, "SELECT * FROM video_jobs WHERE id = ?", (JOB_ID,)),
            "content_candidates": _rows(connection, "SELECT * FROM content_candidates WHERE published_job_id = ?", (JOB_ID,)),
            "curriculum_episode_plans": _rows(connection, "SELECT * FROM curriculum_episode_plans WHERE lesson_key = ?", (LESSON_KEY,)),
        }
        report = {
            "status": "dry_run" if dry_run else "reset_complete",
            "reset_group": RESET_GROUP,
            "job_id": JOB_ID,
            "lesson_key": LESSON_KEY,
            "original_video_id": EXPECTED_VIDEO_ID,
            "original_video_url": publication.get("video_url"),
            "reason": "replace legacy publication with grounded pre-publication review artifact",
            "reset_at": now,
            "dry_run": dry_run,
        }
        if dry_run:
            return report
        with connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS publication_reset_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reset_group TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    original_video_id TEXT NOT NULL,
                    verification_run_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    reset_at TEXT NOT NULL,
                    UNIQUE(reset_group, job_id)
                )"""
            )
            connection.execute(
                """INSERT INTO publication_reset_history
                    (reset_group, job_id, original_video_id, verification_run_id, reason, snapshot_json, reset_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    RESET_GROUP,
                    JOB_ID,
                    EXPECTED_VIDEO_ID,
                    "manual-user-request",
                    report["reason"],
                    json.dumps(snapshot, ensure_ascii=False),
                    now,
                ),
            )
            # Delete active publication/catalog identity. The public YouTube object is
            # untouched; its ID remains only in publication_reset_history.
            connection.execute("DELETE FROM youtube_video_playlists WHERE job_id = ?", (JOB_ID,))
            connection.execute("DELETE FROM youtube_videos WHERE job_id = ?", (JOB_ID,))
            connection.execute("DELETE FROM youtube_publications WHERE job_id = ?", (JOB_ID,))
            connection.execute(
                """UPDATE video_jobs SET status = 'reset_for_review', output_url = NULL,
                    output_payload_json = '{}', error_message = NULL, updated_at = ? WHERE id = ?""",
                (now, JOB_ID),
            )
            connection.execute(
                """UPDATE content_candidates SET status = 'blocked', published_job_id = NULL,
                    updated_at = ? WHERE published_job_id = ?""",
                (now, JOB_ID),
            )
            connection.execute(
                """UPDATE curriculum_episode_plans SET status = 'retry', candidate_id = NULL,
                    job_id = NULL, attempts = 0, published_at = NULL,
                    error_message = 'Review-only regeneration required; public legacy video is quarantined',
                    updated_at = ? WHERE lesson_key = ? AND language = 'en'""",
                (now, LESSON_KEY),
            )
        return report
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default="data/chinese_cheese_video.db")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirmation", required=True)
    args = parser.parse_args()
    if args.confirmation != CONFIRMATION:
        raise SystemExit("Reset refused: confirmation token does not match")
    print(json.dumps(reset_for_review(Path(args.db_path), dry_run=args.dry_run), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
