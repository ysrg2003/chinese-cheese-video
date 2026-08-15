#!/usr/bin/env python3
"""Reset all local YouTube publication state after a verified full-channel deletion."""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESET_GROUP = "full_channel_restart_2026-08-15"
VERIFICATION_RUN_ID = "full-channel-deletion-workflow"
REASON = "user_confirmed_full_channel_restart_after_system_grounding_upgrade"


def rows(connection: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(sql, params).fetchall()]


def row(connection: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    value = connection.execute(sql, params).fetchone()
    return dict(value) if value else None


def minimal_metadata(raw: str | None, *, reset_at: str, old_video_id: str | None, old_video_url: str | None) -> str:
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
        "reason": REASON,
        "reset_at": reset_at,
    }
    return json.dumps(preserved, ensure_ascii=False)


def reset_catalog(db_path: Path, manifest_path: Path, report_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    deleted_ids = {str(item.get("video_id")) for item in manifest.get("videos", []) if item.get("video_id")}
    if manifest.get("video_count") != len(deleted_ids):
        raise RuntimeError("Deletion manifest is missing video IDs or has duplicate IDs")
    now = datetime.now(timezone.utc).isoformat()
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS publication_reset_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reset_group TEXT NOT NULL,
            job_id TEXT NOT NULL,
            original_video_id TEXT,
            verification_run_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            reset_at TEXT NOT NULL,
            UNIQUE(reset_group, job_id)
        )
    """)
    connection.execute("CREATE INDEX IF NOT EXISTS publication_reset_history_video_idx ON publication_reset_history(original_video_id)")
    active_publications = rows(connection, "SELECT * FROM youtube_publications WHERE video_id IS NOT NULL")
    active_videos = rows(connection, "SELECT * FROM youtube_videos WHERE video_id IS NOT NULL")
    target_jobs = sorted({str(item.get("job_id")) for item in active_publications + active_videos if item.get("job_id")})
    unknown_ids = {str(item.get("video_id")) for item in active_publications + active_videos if item.get("video_id")} - deleted_ids
    if unknown_ids:
        raise RuntimeError(f"Local active video IDs were not in the verified full-channel deletion manifest: {sorted(unknown_ids)}")
    report = {
        "contract": "full_channel_catalog_reset_v1",
        "reset_group": RESET_GROUP,
        "verification_run_id": VERIFICATION_RUN_ID,
        "reason": REASON,
        "reset_at": now,
        "manifest_video_count": len(deleted_ids),
        "active_local_job_count": len(target_jobs),
        "job_ids": target_jobs,
        "reset_count": 0,
    }
    with connection:
        for job_id in target_jobs:
            publication = row(connection, "SELECT * FROM youtube_publications WHERE job_id = ?", (job_id,))
            video = row(connection, "SELECT * FROM youtube_videos WHERE job_id = ?", (job_id,))
            job = row(connection, "SELECT * FROM video_jobs WHERE id = ?", (job_id,))
            candidates = rows(connection, "SELECT * FROM content_candidates WHERE published_job_id = ?", (job_id,))
            episodes = rows(connection, "SELECT * FROM curriculum_episode_plans WHERE job_id = ?", (job_id,))
            links = rows(connection, "SELECT * FROM youtube_video_playlists WHERE job_id = ?", (job_id,))
            old_video_id = (publication or {}).get("video_id") or (video or {}).get("video_id")
            old_video_url = (publication or {}).get("video_url") or (video or {}).get("video_url")
            snapshot = {
                "youtube_publication": publication,
                "youtube_video": video,
                "video_job": job,
                "content_candidates": candidates,
                "curriculum_episode_plans": episodes,
                "youtube_video_playlists": links,
            }
            connection.execute(
                """INSERT OR IGNORE INTO publication_reset_history
                   (reset_group,job_id,original_video_id,verification_run_id,reason,snapshot_json,reset_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (RESET_GROUP, job_id, old_video_id, VERIFICATION_RUN_ID, REASON, json.dumps(snapshot, ensure_ascii=False), now),
            )
            if publication:
                connection.execute(
                    """UPDATE youtube_publications SET status='not_started',video_id=NULL,video_url=NULL,
                       playlist_id=NULL,playlist_url=NULL,attempts=0,error_message=NULL,metadata_json=?,updated_at=?
                       WHERE job_id=?""",
                    (minimal_metadata(publication.get("metadata_json"), reset_at=now, old_video_id=old_video_id, old_video_url=old_video_url), now, job_id),
                )
            if video:
                connection.execute(
                    """UPDATE youtube_videos SET video_id=NULL,video_url=NULL,privacy_status=NULL,published_at=NULL,
                       video_path=NULL,audio_path=NULL,status='reset_for_regeneration',error_message=NULL,metadata_json=?,updated_at=?
                       WHERE job_id=?""",
                    (minimal_metadata(video.get("metadata_json"), reset_at=now, old_video_id=old_video_id, old_video_url=old_video_url), now, job_id),
                )
            connection.execute("DELETE FROM youtube_video_playlists WHERE job_id = ?", (job_id,))
            if job:
                connection.execute("UPDATE video_jobs SET status='reset_for_regeneration',output_url=NULL,output_payload_json='{}',error_message=NULL,updated_at=? WHERE id=?", (now, job_id))
            connection.execute("UPDATE content_candidates SET status='discovered',published_job_id=NULL,updated_at=? WHERE published_job_id=?", (now, job_id))
            connection.execute("UPDATE curriculum_episode_plans SET status='planned',candidate_id=NULL,job_id=NULL,attempts=0,published_at=NULL,error_message=NULL,updated_at=? WHERE job_id=?", (now, job_id))
            report["reset_count"] += 1
    connection.close()
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default="data/chinese_cheese_video.db")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--report", default="full-channel-catalog-reset.json")
    args = parser.parse_args()
    report = reset_catalog(Path(args.db_path), Path(args.manifest), Path(args.report))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
