"""Upload generated English thumbnails for already-published standard videos.

This command never uploads a video and never changes its title, description, or
playlist. It only generates the source-controlled English thumbnail and calls
YouTube thumbnails.set for the existing public video ID.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from local_store import LocalStore
from localization import set_thumbnail
from thumbnail import validate_thumbnail_assets
from youtube_publisher import YouTubePublisherError, _prepare_standard_thumbnail_assets, build_service


def _job_ids(value: list[str]) -> list[str]:
    result: list[str] = []
    for item in value:
        key = str(item or "").strip()
        if key and key not in result:
            result.append(key)
    return result


def backfill(job_ids: list[str], db_path: Path, output_root: Path) -> dict[str, Any]:
    store = LocalStore(db_path)
    service = build_service()
    report: dict[str, Any] = {"status": "completed", "selected": len(job_ids), "updated": 0, "skipped": 0, "failed": 0, "items": []}
    for job_id in job_ids:
        item: dict[str, Any] = {"job_id": job_id}
        try:
            publication = store.get_youtube_publication(job_id)
            if not publication or not publication.get("video_id"):
                raise YouTubePublisherError("No existing YouTube publication with a video_id")
            if str(publication.get("status") or "") not in {"published", "published_thumbnail_pending", "published_localization_pending"}:
                raise YouTubePublisherError(f"Publication is not an active public video: {publication.get('status')}")
            job = store.get_video_job_payload(job_id)
            if not job:
                raise YouTubePublisherError("Stored job payload is missing")
            job = dict(job)
            job["id"] = job_id
            job.setdefault("language", publication.get("language") or "en")
            job_format = str(job.get("format") or "lesson").strip().lower()
            if job_format == "short":
                item.update({"status": "skipped_short", "video_id": publication["video_id"]})
                report["skipped"] += 1
                report["items"].append(item)
                continue
            job_output = output_root / job_id
            assets = _prepare_standard_thumbnail_assets(None, job, job_output)
            errors = validate_thumbnail_assets(assets)
            if errors:
                raise YouTubePublisherError("Thumbnail validation failed: " + "; ".join(errors))
            response = set_thumbnail(service, str(publication["video_id"]), assets["default"])
            metadata = dict(publication.get("metadata") or {})
            metadata["thumbnail_policy"] = "api_upload_and_verify"
            metadata["thumbnail"] = {
                "default": assets["default"],
                "english": assets["english"],
                "width": assets.get("width"),
                "height": assets.get("height"),
                "default_upload": response,
                "default_upload_status": "api_response_confirmed",
                "source": "backfill_thumbnails.py",
            }
            store.upsert_youtube_publication(
                job_id,
                str(publication.get("language") or job.get("language") or "en"),
                str(publication.get("content_type") or job.get("content_type") or "definition"),
                "published",
                video_id=publication.get("video_id"),
                video_url=publication.get("video_url"),
                playlist_id=publication.get("playlist_id"),
                playlist_url=publication.get("playlist_url"),
                metadata=metadata,
                error_message=None,
            )
            store.upsert_youtube_catalog(job, {
                "status": "published",
                "video_id": publication.get("video_id"),
                "video_url": publication.get("video_url"),
                "playlist_id": publication.get("playlist_id"),
                "playlist_url": publication.get("playlist_url"),
                "metadata": metadata,
                "thumbnail_policy": "api_upload_and_verify",
            })
            item.update({"status": "updated", "video_id": publication["video_id"], "thumbnail": metadata["thumbnail"]})
            report["updated"] += 1
        except Exception as exc:
            item.update({"status": "failed", "error": str(exc)})
            report["failed"] += 1
        report["items"].append(item)
    if report["failed"]:
        report["status"] = "failed"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", action="append", required=True, help="Existing published job ID; repeat for multiple videos")
    parser.add_argument("--db-path", default=os.getenv("LOCAL_DB_PATH", "data/chinese_cheese_video.db"))
    parser.add_argument("--output-root", default="output/thumbnail-backfill")
    parser.add_argument("--report", default="thumbnail-backfill-report.json")
    args = parser.parse_args()
    report = backfill(_job_ids(args.job_id), Path(args.db_path), Path(args.output_root))
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
