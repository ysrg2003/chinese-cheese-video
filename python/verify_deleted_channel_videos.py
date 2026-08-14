"""Verify that the user-deleted Xiangqi videos are absent from the owned channel.

This is read-only. It exists to keep SQLite reset separate from a successful
YouTube deletion and to avoid accepting an unverified browser-side deletion.
"""

from __future__ import annotations

import json
from typing import Any

import youtube_publisher

EXPECTED_CHANNEL_ID = "UCM7pTdgZRwDZ2gZDtC6SITg"
DELETED_BY_USER_VIDEO_IDS = (
    "oolASOuPoQc",
    "mQERRtjjgjk",
    "7DEqaNIh3HE",
    "Tg_DcCPxXuo",
    "a8xHxTuBDAM",
    "zq7vLtLHdSM",
    "8KUaj4IiH_8",
)


class DeletionVerificationError(RuntimeError):
    pass


def _owned_channel_id(service: Any) -> str:
    response = youtube_publisher._execute_with_backoff(
        lambda: service.channels().list(part="id", mine=True)
    )
    channel_ids = [str(item.get("id")) for item in response.get("items") or [] if item.get("id")]
    if channel_ids != [EXPECTED_CHANNEL_ID]:
        raise DeletionVerificationError(
            f"Authenticated channel mismatch: expected {EXPECTED_CHANNEL_ID}, received {channel_ids}"
        )
    return channel_ids[0]


def verify_absent(service: Any) -> dict[str, Any]:
    channel_id = _owned_channel_id(service)
    response = youtube_publisher._execute_with_backoff(
        lambda: service.videos().list(
            part="id,snippet,status",
            id=",".join(DELETED_BY_USER_VIDEO_IDS),
            maxResults=len(DELETED_BY_USER_VIDEO_IDS),
        )
    )
    present = {
        str(item.get("id")): {
            "title": str((item.get("snippet") or {}).get("title") or ""),
            "privacy_status": str((item.get("status") or {}).get("privacyStatus") or ""),
        }
        for item in response.get("items") or []
        if item.get("id")
    }
    absent = [video_id for video_id in DELETED_BY_USER_VIDEO_IDS if video_id not in present]
    report = {
        "channel_id": channel_id,
        "target_video_ids": list(DELETED_BY_USER_VIDEO_IDS),
        "absent_video_ids": absent,
        "present_videos": present,
        "verified_absent": not present,
    }
    if present:
        raise DeletionVerificationError(json.dumps(report, ensure_ascii=False))
    return report


def main() -> int:
    report = verify_absent(youtube_publisher.build_service())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
