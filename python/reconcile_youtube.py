from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from local_store import LocalStore
from youtube_publisher import publish_video


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if os.getenv("YOUTUBE_PUBLISH_ENABLED", "0").lower() not in {"1", "true", "yes"}:
        print(json.dumps({"enabled": False, "selected": 0, "published": 0, "failed": 0}))
        return 0

    store = LocalStore()
    with store._connect() as connection:
        rows = connection.execute(
            """
            SELECT job_id, language, content_type, status, video_id, video_url, playlist_id,
                   playlist_url, metadata_json, error_message
            FROM youtube_publications
            WHERE video_id IS NOT NULL AND status IN ('failed', 'uploaded_playlist_pending')
            ORDER BY updated_at ASC
            LIMIT 20
            """
        ).fetchall()

    metrics = {"enabled": True, "selected": len(rows), "published": 0, "failed": 0, "items": []}
    for row in rows:
        publication = dict(row)
        metadata: dict[str, Any] = json.loads(publication.pop("metadata_json") or "{}")
        language = str(row["language"] or "en")
        job: dict[str, Any] = {
            "id": row["job_id"],
            "title": metadata.get("title") or row["job_id"],
            "language": language,
            "content_type": row["content_type"] or "definition",
            "source_url": metadata.get("source_url"),
            "source_kind": metadata.get("source_kind", "reconciled_publication"),
            "topic_key": metadata.get("topic_key"),
            "narration": metadata.get("narration", ""),
            "captions": metadata.get("captions", []),
        }
        try:
            result = publish_video(None, job, existing_publication=publication)
            store.upsert_youtube_publication(
                row["job_id"],
                language,
                row["content_type"] or "definition",
                result.get("status", "failed"),
                video_id=result.get("video_id") or row["video_id"],
                video_url=result.get("video_url") or row["video_url"],
                playlist_id=result.get("playlist_id"),
                playlist_url=result.get("playlist_url"),
                metadata=result.get("metadata", metadata),
                error_message=result.get("error_message"),
            )
            store.upsert_youtube_catalog(job, result)
            if result.get("status") == "published":
                candidate_id = str(row["job_id"])
                suffix = f"-{language}"
                if candidate_id.endswith(suffix):
                    candidate_id = candidate_id[: -len(suffix)]
                store.update_candidate(candidate_id, "published", published_job_id=row["job_id"])
                metrics["published"] += 1
            else:
                metrics["failed"] += 1
            metrics["items"].append({"job_id": row["job_id"], "video_id": result.get("video_id"), "status": result.get("status"), "playlist_id": result.get("playlist_id"), "error": result.get("error_message")})
        except Exception as exc:
            metrics["failed"] += 1
            metrics["items"].append({"job_id": row["job_id"], "video_id": row["video_id"], "status": "failed", "error": str(exc)})
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
