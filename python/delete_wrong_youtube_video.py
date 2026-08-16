#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

import youtube_publisher

EXPECTED_CHANNEL_ID = "UCM7pTdgZRwDZ2gZDtC6SITg"
EXPECTED_VIDEO_ID = "YpT0HzHTR2s"
EXPECTED_TITLE = "The Opening Mistake That Gives Away the Center — Series 33.1 | Xiangqi Opening"
CONFIRMATION = "DELETE_WRONG_EVERGREEN_REPUBLISH_EN012"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirmation", required=True)
    args = parser.parse_args()
    if args.confirmation != CONFIRMATION:
        raise SystemExit("Deletion refused: confirmation token does not match")
    service: Any = youtube_publisher.build_service()
    channel = youtube_publisher._execute_with_backoff(lambda: service.channels().list(part="id", mine=True))
    ids = [str(item.get("id")) for item in (channel.get("items") or []) if item.get("id")]
    if ids != [EXPECTED_CHANNEL_ID]:
        raise RuntimeError(f"Authenticated channel mismatch: {ids}")
    response = youtube_publisher._execute_with_backoff(lambda: service.videos().list(part="id,snippet,status", id=EXPECTED_VIDEO_ID))
    items = response.get("items") or []
    if len(items) != 1:
        raise RuntimeError(f"Expected exactly one target video, found {len(items)}")
    item = items[0]
    title = str((item.get("snippet") or {}).get("title") or "")
    if title != EXPECTED_TITLE:
        raise RuntimeError(f"Target title mismatch: {title!r}")
    print(json.dumps({"phase": "preflight_passed", "channel_id": EXPECTED_CHANNEL_ID, "video_id": EXPECTED_VIDEO_ID, "title": title}, ensure_ascii=False))
    youtube_publisher._execute_with_backoff(lambda: service.videos().delete(id=EXPECTED_VIDEO_ID))
    verify = youtube_publisher._execute_with_backoff(lambda: service.videos().list(part="id", id=EXPECTED_VIDEO_ID))
    if verify.get("items"):
        raise RuntimeError("Deletion verification failed: target still exists")
    print(json.dumps({"phase": "deleted_and_verified", "video_id": EXPECTED_VIDEO_ID}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
