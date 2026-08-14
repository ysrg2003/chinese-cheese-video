#!/usr/bin/env python3
"""Quarantine the audited invalid publications after YouTube deletion.

The YouTube deletion is performed separately. This script only updates the local
SQLite catalog, preserves historical video identifiers in metadata, and returns
affected source candidates to the autonomous discovery queue.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/chinese_cheese_video.db")
CONFIRMATION = "QUARANTINE_INVALID_XIANGQI_PUBLICATIONS"

TARGETS = {
    "news-chinese-chess-grandmaster-lei-tingjie-believes-ai--en": {
        "video_id": "wmJ5-34N6z8",
        "reason": "ply 3: declared piece pawn does not match actual cannon",
    },
    "news-chinese-chess-grandmaster-lei-tingjie-believes-ai--zh": {
        "video_id": "KkaGX4ujyfI",
        "reason": "ply 3: declared piece pawn does not match actual cannon",
    },
    "news-xu-xiangyu-and-yan-tianqi-are-2026-chinese-chess-c-en": {
        "video_id": "M7mQrRxIg-M",
        "reason": "ply 3: declared piece pawn does not match actual cannon",
    },
    "news-xu-xiangyu-and-yan-tianqi-are-2026-chinese-chess-c-zh": {
        "video_id": "na82AsZBxKU",
        "reason": "ply 3: declared piece pawn does not match actual cannon",
    },
    "evergreen-33-7-2026-08-13-en": {
        "video_id": "6uZ1lxn-oUs",
        "reason": "ply 3: declared piece pawn does not match actual cannon",
    },
    "evergreen-33-0-2026-08-13-en": {
        "video_id": "tA3vZMgrfg8",
        "reason": "ply 3: declared piece pawn does not match actual cannon",
    },
    "evergreen-33-1-2026-08-13-en": {
        "video_id": "gSgVXtG9Snw",
        "reason": "ply 1: declared piece pawn does not match actual rook; rook path is blocked by red pawn",
    },
    "curriculum-en-010-the-general-en": {
        "video_id": "QEdAG1azW2U",
        "reason": "ply 3: destination is occupied by a friendly piece; prior plies also create flying-general alignment",
        "lesson_key": "en-010-the-general",
        "language": "en",
    },
}


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--confirmation", required=True)
    parser.add_argument("--deletion-run-id", default="31761045747")
    args = parser.parse_args()
    if args.confirmation != CONFIRMATION:
        raise SystemExit("Local quarantine refused: confirmation token does not match")

    db_path = Path(args.db)
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN IMMEDIATE")
        for job_id, target in TARGETS.items():
            publication = conn.execute(
                "SELECT job_id, video_id, video_url, playlist_id, playlist_url, metadata_json FROM youtube_publications WHERE job_id = ? LIMIT 1",
                (job_id,),
            ).fetchone()
            if publication is None:
                raise RuntimeError(f"Missing publication row for {job_id}")
            if str(publication["video_id"]) != target["video_id"]:
                raise RuntimeError(
                    f"Video ID mismatch for {job_id}: expected {target['video_id']}, received {publication['video_id']}"
                )

        counts = {"publications": 0, "catalog": 0, "playlist_links": 0, "candidates": 0, "curriculum": 0}
        for job_id, target in TARGETS.items():
            publication = conn.execute(
                "SELECT video_id, video_url, playlist_id, playlist_url, metadata_json FROM youtube_publications WHERE job_id = ? LIMIT 1",
                (job_id,),
            ).fetchone()
            metadata = json.loads(publication["metadata_json"] or "{}")
            metadata["remediation"] = {
                "status": "deleted_invalid_content",
                "reason": target["reason"],
                "deleted_at": now,
                "deletion_workflow_run_id": str(args.deletion_run_id),
                "original_video_id": publication["video_id"],
                "original_video_url": publication["video_url"],
                "original_playlist_id": publication["playlist_id"],
                "original_playlist_url": publication["playlist_url"],
            }
            conn.execute(
                """
                UPDATE youtube_publications
                SET status = ?, video_id = NULL, video_url = NULL, playlist_id = NULL, playlist_url = NULL,
                    metadata_json = ?, error_message = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (
                    "deleted_invalid_content",
                    _json(metadata),
                    target["reason"],
                    now,
                    job_id,
                ),
            )
            counts["publications"] += 1

            catalog = conn.execute(
                "SELECT metadata_json FROM youtube_videos WHERE job_id = ? LIMIT 1",
                (job_id,),
            ).fetchone()
            if catalog is not None:
                catalog_metadata = json.loads(catalog["metadata_json"] or "{}")
                catalog_metadata["remediation"] = metadata["remediation"]
                conn.execute(
                    """
                    UPDATE youtube_videos
                    SET status = ?, video_id = NULL, video_url = NULL, privacy_status = ?, metadata_json = ?, error_message = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (
                        "deleted_invalid_content",
                        "deleted",
                        _json(catalog_metadata),
                        target["reason"],
                        now,
                        job_id,
                    ),
                )
                counts["catalog"] += 1

            conn.execute(
                """
                UPDATE youtube_video_playlists
                SET youtube_playlist_id = NULL, playlist_item_id = NULL, status = ?, error_message = ?, updated_at = ?
                WHERE job_id = ?
                """,
                ("deleted_invalid_content", target["reason"], now, job_id),
            )
            counts["playlist_links"] += conn.execute("SELECT changes()").fetchone()[0]

            conn.execute(
                "UPDATE content_candidates SET status = 'discovered', updated_at = ? WHERE published_job_id = ?",
                (now, job_id),
            )
            counts["candidates"] += conn.execute("SELECT changes()").fetchone()[0]

            lesson_key = target.get("lesson_key")
            if lesson_key:
                conn.execute(
                    """
                    UPDATE curriculum_episode_plans
                    SET status = 'retry', error_message = ?, updated_at = ?
                    WHERE lesson_key = ? AND language = ?
                    """,
                    (target["reason"], now, lesson_key, target.get("language", "en")),
                )
                counts["curriculum"] += conn.execute("SELECT changes()").fetchone()[0]

        conn.commit()
        print(json.dumps({
            "status": "quarantined",
            "updated_at": now,
            "deletion_workflow_run_id": str(args.deletion_run_id),
            "counts": counts,
            "job_ids": list(TARGETS),
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
