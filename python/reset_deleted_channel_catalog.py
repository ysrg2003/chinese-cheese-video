"""Reset user-deleted channel videos to unpublished, regeneration-ready catalog state.

The reset is deliberately narrow and idempotent. It requires the read-only YouTube
verification workflow to have confirmed absence first, archives the old active state
in a dedicated SQLite history table, then clears active video/publication identifiers.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERIFICATION_RUN_ID = "31767933148"
RESET_GROUP = "user_deleted_channel_catalog_2026-08-14"
CONFIRMATION = "RESET_DELETED_XIANGQI_CATALOG"
TARGET_VIDEO_IDS = (
    "oolASOuPoQc",
    "mQERRtjjgjk",
    "7DEqaNIh3HE",
    "Tg_DcCPxXuo",
    "a8xHxTuBDAM",
    "zq7vLtLHdSM",
    "8KUaj4IiH_8",
)


class CatalogResetError(RuntimeError):
    pass


def _row(connection: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    value = connection.execute(query, params).fetchone()
    return dict(value) if value else None


def _rows(connection: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [dict(value) for value in connection.execute(query, params).fetchall()]


def _minimal_metadata(raw: str | None, *, reset_at: str, old_video_id: str, old_video_url: str | None) -> str:
    try:
        source = json.loads(raw or "{}")
    except json.JSONDecodeError:
        source = {}
    preserved = {key: source[key] for key in ("title", "playlist_key", "content_type", "curriculum_lesson_key") if key in source}
    preserved["catalog_reset"] = {
        "reset_group": RESET_GROUP,
        "verification_run_id": VERIFICATION_RUN_ID,
        "verified_absent": True,
        "original_video_id": old_video_id,
        "original_video_url": old_video_url,
        "reason": "user_deleted_all_channel_videos_for_visual_remediation",
        "reset_at": reset_at,
    }
    return json.dumps(preserved, ensure_ascii=False)


def reset_catalog(db_path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    placeholders = ",".join("?" for _ in TARGET_VIDEO_IDS)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS publication_reset_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reset_group TEXT NOT NULL,
            job_id TEXT NOT NULL,
            original_video_id TEXT NOT NULL,
            verification_run_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            reset_at TEXT NOT NULL,
            UNIQUE(reset_group, job_id)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS publication_reset_history_video_idx ON publication_reset_history(original_video_id)"
    )
    publications = _rows(
        connection,
        f"SELECT * FROM youtube_publications WHERE video_id IN ({placeholders}) ORDER BY job_id",
        TARGET_VIDEO_IDS,
    )
    historical = _rows(
        connection,
        "SELECT job_id, original_video_id FROM publication_reset_history WHERE reset_group = ? ORDER BY job_id",
        (RESET_GROUP,),
    )
    historical_ids = {str(row["original_video_id"]) for row in historical}
    if not publications and historical_ids == set(TARGET_VIDEO_IDS):
        connection.close()
        return {
            "reset_group": RESET_GROUP,
            "verification_run_id": VERIFICATION_RUN_ID,
            "target_video_ids": list(TARGET_VIDEO_IDS),
            "job_ids": [row["job_id"] for row in historical],
            "dry_run": dry_run,
            "status": "already_reset",
        }
    found_ids = {str(row["video_id"]) for row in publications if row.get("video_id")}
    missing = [video_id for video_id in TARGET_VIDEO_IDS if video_id not in found_ids]
    if missing:
        raise CatalogResetError(f"SQLite active publication records missing expected deleted IDs: {missing}")
    if len(publications) != len(TARGET_VIDEO_IDS):
        raise CatalogResetError(f"Expected {len(TARGET_VIDEO_IDS)} publications, found {len(publications)}")

    report: dict[str, Any] = {
        "reset_group": RESET_GROUP,
        "verification_run_id": VERIFICATION_RUN_ID,
        "target_video_ids": list(TARGET_VIDEO_IDS),
        "job_ids": [row["job_id"] for row in publications],
        "dry_run": dry_run,
    }
    if dry_run:
        connection.close()
        return report

    with connection:
        for publication in publications:
            job_id = str(publication["job_id"])
            old_video_id = str(publication["video_id"])
            video = _row(connection, "SELECT * FROM youtube_videos WHERE job_id = ?", (job_id,))
            job = _row(connection, "SELECT * FROM video_jobs WHERE id = ?", (job_id,))
            candidates = _rows(connection, "SELECT * FROM content_candidates WHERE published_job_id = ?", (job_id,))
            episodes = _rows(connection, "SELECT * FROM curriculum_episode_plans WHERE job_id = ?", (job_id,))
            links = _rows(connection, "SELECT * FROM youtube_video_playlists WHERE job_id = ?", (job_id,))
            snapshot = {
                "youtube_publication": publication,
                "youtube_video": video,
                "video_job": job,
                "content_candidates": candidates,
                "curriculum_episode_plans": episodes,
                "youtube_video_playlists": links,
            }
            connection.execute(
                """
                INSERT OR IGNORE INTO publication_reset_history
                    (reset_group, job_id, original_video_id, verification_run_id, reason, snapshot_json, reset_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    RESET_GROUP,
                    job_id,
                    old_video_id,
                    VERIFICATION_RUN_ID,
                    "user_deleted_all_channel_videos_for_visual_remediation",
                    json.dumps(snapshot, ensure_ascii=False),
                    now,
                ),
            )
            metadata = _minimal_metadata(
                publication.get("metadata_json"),
                reset_at=now,
                old_video_id=old_video_id,
                old_video_url=publication.get("video_url"),
            )
            connection.execute(
                """
                UPDATE youtube_publications
                SET status = 'not_started', video_id = NULL, video_url = NULL,
                    playlist_id = NULL, playlist_url = NULL, attempts = 0,
                    error_message = NULL, metadata_json = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (metadata, now, job_id),
            )
            if video:
                video_metadata = _minimal_metadata(
                    video.get("metadata_json"),
                    reset_at=now,
                    old_video_id=old_video_id,
                    old_video_url=video.get("video_url"),
                )
                connection.execute(
                    """
                    UPDATE youtube_videos
                    SET video_id = NULL, video_url = NULL, privacy_status = NULL,
                        published_at = NULL, video_path = NULL, audio_path = NULL,
                        status = 'reset_for_regeneration', error_message = NULL,
                        metadata_json = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (video_metadata, now, job_id),
                )
            connection.execute(
                "DELETE FROM youtube_video_playlists WHERE job_id = ?",
                (job_id,),
            )
            if job:
                connection.execute(
                    """
                    UPDATE video_jobs
                    SET status = 'reset_for_regeneration', output_url = NULL,
                        output_payload_json = '{}', error_message = NULL, updated_at = ?
                    WHERE id = ?
                    """,
                    (now, job_id),
                )
            connection.execute(
                """
                UPDATE content_candidates
                SET status = 'discovered', published_job_id = NULL, updated_at = ?
                WHERE published_job_id = ?
                """,
                (now, job_id),
            )
            connection.execute(
                """
                UPDATE curriculum_episode_plans
                SET status = 'planned', candidate_id = NULL, job_id = NULL,
                    attempts = 0, published_at = NULL, error_message = NULL, updated_at = ?
                WHERE job_id = ?
                """,
                (now, job_id),
            )
    connection.close()
    report["status"] = "reset_complete"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default="data/chinese_cheese_video.db")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirmation", required=True)
    args = parser.parse_args()
    if args.confirmation != CONFIRMATION:
        raise SystemExit("Catalog reset refused: confirmation token does not match")
    result = reset_catalog(Path(args.db_path), dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
