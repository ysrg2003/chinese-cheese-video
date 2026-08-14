#!/usr/bin/env python3
"""Permanently delete the eight Xiangqi videos identified by the 2026-08-14 audit.

This is intentionally narrow and fail-closed. It verifies the authenticated channel,
verifies every target exists before deleting anything, and requires an explicit
confirmation flag. It never accepts arbitrary video IDs from an unreviewed caller.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import youtube_publisher

EXPECTED_CHANNEL_ID = "UCM7pTdgZRwDZ2gZDtC6SITg"
CONFIRMATION = "DELETE_INVALID_XIANGQI_VIDEOS"
TARGET_VIDEO_IDS = (
    "wmJ5-34N6z8",
    "KkaGX4ujyfI",
    "M7mQrRxIg-M",
    "na82AsZBxKU",
    "6uZ1lxn-oUs",
    "tA3vZMgrfg8",
    "gSgVXtG9Snw",
    "QEdAG1azW2U",
)


class PermanentDeletionError(RuntimeError):
    pass


def _channel_id(service: Any) -> str:
    response = youtube_publisher._execute_with_backoff(
        lambda: service.channels().list(part="id", mine=True)
    )
    items = response.get("items") or []
    ids = [str(item.get("id")) for item in items if item.get("id")]
    if ids != [EXPECTED_CHANNEL_ID]:
        raise PermanentDeletionError(
            f"Authenticated channel mismatch: expected {EXPECTED_CHANNEL_ID}, received {ids}"
        )
    return ids[0]


def _preflight_videos(service: Any) -> tuple[list[dict[str, Any]], list[str]]:
    response = youtube_publisher._execute_with_backoff(
        lambda: service.videos().list(
            part="id,snippet,status",
            id=",".join(TARGET_VIDEO_IDS),
            maxResults=len(TARGET_VIDEO_IDS),
        )
    )
    items = response.get("items") or []
    found = {str(item.get("id")): item for item in items if item.get("id")}
    missing = [video_id for video_id in TARGET_VIDEO_IDS if video_id not in found]
    return [found[video_id] for video_id in TARGET_VIDEO_IDS if video_id in found], missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirmation", required=True)
    args = parser.parse_args()
    if args.confirmation != CONFIRMATION:
        raise SystemExit("Permanent deletion refused: confirmation token does not match")

    service = youtube_publisher.build_service()
    channel_id = _channel_id(service)
    items, already_absent = _preflight_videos(service)
    if not items:
        raise PermanentDeletionError("Preflight found no remaining target videos to delete")
    print(json.dumps({
        "phase": "preflight_passed",
        "channel_id": channel_id,
        "already_absent_video_ids": already_absent,
        "targets": [
            {
                "video_id": str(item.get("id")),
                "title": ((item.get("snippet") or {}).get("title")),
                "privacy_status": ((item.get("status") or {}).get("privacyStatus")),
            }
            for item in items
        ],
    }, ensure_ascii=False, indent=2))

    deleted: list[str] = []
    present_ids = [str(item.get("id")) for item in items]
    for video_id in present_ids:
        youtube_publisher._execute_with_backoff(
            lambda video_id=video_id: service.videos().delete(id=video_id)
        )
        deleted.append(video_id)
        print(json.dumps({"phase": "deleted", "video_id": video_id}))

    print(json.dumps({
        "phase": "completed",
        "channel_id": channel_id,
        "requested_video_ids": list(TARGET_VIDEO_IDS),
        "already_absent_video_ids": already_absent,
        "deleted_video_ids": deleted,
        "count_deleted_now": len(deleted),
        "count_already_absent": len(already_absent),
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Permanent deletion failed: {exc}", file=sys.stderr)
        raise
