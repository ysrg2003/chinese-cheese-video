from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from local_store import LocalStore
from xiangqi_rules import validate_move_sequence
from youtube_publisher import _execute_with_backoff, build_service, publish_video


ROOT = Path(__file__).resolve().parents[1]


def _candidate_id_from_job(job_id: str, language: str) -> str:
    suffix = f"-{language}"
    return job_id[:-len(suffix)] if job_id.endswith(suffix) else job_id


def _reconcile_deleted_published_rows(store: LocalStore) -> list[dict[str, Any]]:
    """Repair local rows whose YouTube video disappeared outside this process."""
    with store._connect() as connection:
        rows = connection.execute(
            """
            SELECT job_id, language, content_type, status, video_id, video_url, playlist_id,
                   playlist_url, metadata_json
            FROM youtube_publications
            WHERE video_id IS NOT NULL AND status = 'published'
            ORDER BY updated_at ASC
            LIMIT 100
            """
        ).fetchall()
    if not rows:
        return []
    service = build_service()
    existing: set[str] = set()
    for offset in range(0, len(rows), 50):
        batch = rows[offset:offset + 50]
        response = _execute_with_backoff(
            lambda batch=batch: service.videos().list(
                part="id", id=",".join(str(row["video_id"]) for row in batch), maxResults=len(batch)
            )
        )
        existing.update(str(item.get("id")) for item in response.get("items") or [] if item.get("id"))
    repaired: list[dict[str, Any]] = []
    for row in rows:
        video_id = str(row["video_id"])
        if video_id in existing:
            continue
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        metadata = dict(metadata) if isinstance(metadata, dict) else {}
        metadata["external_deletion"] = {
            "status": "detected",
            "video_id": video_id,
            "detected_by": "reconcile_youtube",
        }
        job_id = str(row["job_id"])
        language = str(row["language"] or "en")
        candidate_id = _candidate_id_from_job(job_id, language)
        store.upsert_youtube_publication(
            job_id,
            language,
            str(row["content_type"] or "definition"),
            "deleted_external",
            video_id=video_id,
            video_url=row["video_url"],
            playlist_id=row["playlist_id"],
            playlist_url=row["playlist_url"],
            metadata=metadata,
            error_message="YouTube video no longer exists; local publication was requeued.",
        )
        store.update_candidate(candidate_id, "discovered")
        stored_job = store.get_video_job_payload(job_id) or {}
        lesson_key = str(stored_job.get("curriculum_lesson_key") or metadata.get("curriculum_lesson_key") or "").strip()
        if lesson_key and language == "en":
            store.update_curriculum_episode(
                lesson_key,
                language,
                "retry",
                candidate_id=candidate_id,
                job_id=job_id,
                error_message="YouTube video was deleted externally; lesson must be regenerated.",
            )
        repaired.append({"job_id": job_id, "video_id": video_id, "status": "deleted_external", "lesson_key": lesson_key})
    return repaired


def main() -> int:
    if os.getenv("YOUTUBE_PUBLISH_ENABLED", "0").lower() not in {"1", "true", "yes"}:
        print(json.dumps({"enabled": False, "selected": 0, "published": 0, "failed": 0}))
        return 0

    store = LocalStore()
    repaired_deleted = _reconcile_deleted_published_rows(store)
    with store._connect() as connection:
        rows = connection.execute(
            """
            SELECT job_id, language, content_type, status, video_id, video_url, playlist_id,
                   playlist_url, metadata_json, error_message
            FROM youtube_publications
            WHERE video_id IS NOT NULL AND status IN ('failed', 'uploaded_playlist_pending', 'published_localization_pending', 'published_thumbnail_pending')
            ORDER BY updated_at ASC
            LIMIT 20
            """
        ).fetchall()

    metrics = {"enabled": True, "selected": len(rows), "published": 0, "failed": 0, "repaired_deleted": repaired_deleted, "items": []}
    for row in rows:
        publication = dict(row)
        metadata: dict[str, Any] = json.loads(publication.pop("metadata_json") or "{}")
        language = str(row["language"] or "en")
        stored_job = store.get_video_job_payload(row["job_id"])
        if stored_job:
            job = dict(stored_job)
            job["id"] = row["job_id"]
            job["language"] = language
            job.setdefault("title", metadata.get("title") or row["job_id"])
            job.setdefault("content_type", row["content_type"] or "definition")
        else:
            job = {
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
        legal = validate_move_sequence(str(job.get("fen") or ""), job.get("moves") or [])
        if not legal["ok"]:
            blocked_metadata = dict(metadata)
            blocked_metadata["quality_gate"] = {
                "status": "blocked_invalid_content",
                "errors": legal["errors"],
                "plies_checked": legal.get("plies_checked", 0),
            }
            store.upsert_youtube_publication(
                row["job_id"], language, row["content_type"] or "definition", "blocked_invalid_content",
                video_id=row["video_id"], video_url=row["video_url"], playlist_id=row["playlist_id"],
                playlist_url=row["playlist_url"], metadata=blocked_metadata,
                error_message="Stored publication failed deterministic Xiangqi legal-move validation",
            )
            candidate_id = str(row["job_id"])
            suffix = f"-{language}"
            if candidate_id.endswith(suffix):
                candidate_id = candidate_id[: -len(suffix)]
            store.update_candidate(candidate_id, "blocked")
            metrics["failed"] += 1
            metrics["items"].append({"job_id": row["job_id"], "video_id": row["video_id"], "status": "blocked_invalid_content", "errors": legal["errors"]})
            continue
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
                lesson_key = str(job.get("curriculum_lesson_key") or metadata.get("curriculum_lesson_key") or "").strip()
                if lesson_key and language == "en":
                    store.update_curriculum_episode(lesson_key, language, "published", candidate_id=candidate_id, job_id=row["job_id"])
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
