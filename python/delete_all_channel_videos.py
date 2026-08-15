#!/usr/bin/env python3
"""Back up and permanently delete every video owned by the configured Xiangqi channel."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import youtube_publisher

EXPECTED_CHANNEL_ID = "UCM7pTdgZRwDZ2gZDtC6SITg"
CONFIRMATION = "DELETE_ALL_XIANGQI_CHANNEL_VIDEOS"


def _owned_channel(service: Any) -> tuple[str, str, str]:
    response = youtube_publisher._execute_with_backoff(
        lambda: service.channels().list(part="id,snippet,contentDetails", mine=True, maxResults=1)
    )
    items = response.get("items") or []
    if len(items) != 1 or str(items[0].get("id")) != EXPECTED_CHANNEL_ID:
        raise RuntimeError(f"Authenticated channel mismatch: expected {EXPECTED_CHANNEL_ID}, received {items}")
    item = items[0]
    uploads = str(((item.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads") or "")
    if not uploads:
        raise RuntimeError("Authenticated channel has no uploads playlist")
    return EXPECTED_CHANNEL_ID, str((item.get("snippet") or {}).get("title") or ""), uploads


def enumerate_videos(service: Any, uploads_playlist_id: str) -> list[dict[str, Any]]:
    ids: list[str] = []
    token: str | None = None
    while True:
        def request(token: str | None = token) -> Any:
            kwargs = {"part": "contentDetails,snippet", "playlistId": uploads_playlist_id, "maxResults": 50}
            if token:
                kwargs["pageToken"] = token
            return service.playlistItems().list(**kwargs)
        response = youtube_publisher._execute_with_backoff(request)
        for item in response.get("items") or []:
            video_id = str(((item.get("contentDetails") or {}).get("videoId") or ""))
            if video_id and video_id not in ids:
                ids.append(video_id)
        token = response.get("nextPageToken")
        if not token:
            break

    videos: list[dict[str, Any]] = []
    for start in range(0, len(ids), 50):
        chunk = ids[start:start + 50]
        response = youtube_publisher._execute_with_backoff(
            lambda chunk=chunk: service.videos().list(
                part="id,snippet,status,contentDetails,statistics",
                id=",".join(chunk),
                maxResults=len(chunk),
            )
        )
        by_id = {str(item.get("id")): item for item in response.get("items") or []}
        for video_id in chunk:
            item = by_id.get(video_id)
            if not item:
                continue
            snippet = item.get("snippet") or {}
            status = item.get("status") or {}
            videos.append({
                "video_id": video_id,
                "title": snippet.get("title"),
                "description": snippet.get("description"),
                "published_at": snippet.get("publishedAt"),
                "privacy_status": status.get("privacyStatus"),
                "upload_status": status.get("uploadStatus"),
                "made_for_kids": status.get("madeForKids"),
                "duration": (item.get("contentDetails") or {}).get("duration"),
                "view_count": (item.get("statistics") or {}).get("viewCount"),
                "like_count": (item.get("statistics") or {}).get("likeCount"),
                "tags": snippet.get("tags") or [],
                "category_id": snippet.get("categoryId"),
                "playlist_upload_order": len(videos) + 1,
            })
    return videos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirmation", required=True)
    parser.add_argument("--manifest", default="full-channel-video-audit.json")
    parser.add_argument("--report", default="channel-video-deletion-report.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.confirmation != CONFIRMATION:
        raise SystemExit("Deletion refused: confirmation token does not match")

    service = youtube_publisher.build_service()
    channel_id, channel_title, uploads = _owned_channel(service)
    videos = enumerate_videos(service, uploads)
    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "contract": "full_channel_video_backup_v1",
        "channel_id": channel_id,
        "channel_title": channel_title,
        "uploads_playlist_id": uploads,
        "enumerated_at": now,
        "video_count": len(videos),
        "videos": videos,
    }
    Path(args.manifest).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report: dict[str, Any] = {
        "contract": "full_channel_deletion_v1",
        "channel_id": channel_id,
        "channel_title": channel_title,
        "uploads_playlist_id": uploads,
        "manifest": args.manifest,
        "requested_at": now,
        "target_video_ids": [item["video_id"] for item in videos],
        "target_count": len(videos),
        "deleted_video_ids": [],
        "errors": [],
        "dry_run": bool(args.dry_run),
    }
    if not args.dry_run:
        for item in videos:
            video_id = item["video_id"]
            try:
                youtube_publisher._execute_with_backoff(lambda video_id=video_id: service.videos().delete(id=video_id))
                report["deleted_video_ids"].append(video_id)
            except Exception as exc:
                report["errors"].append({"video_id": video_id, "error": str(exc)})
                break
    report["status"] = "dry_run" if args.dry_run else ("deleted_all" if not report["errors"] else "partial_failure")
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
