from __future__ import annotations

import argparse
import json
from typing import Any

from youtube_publisher import _execute_with_backoff, build_service


TARGET_LANGUAGE_PREFIXES = ("en", "en-US", "en-GB")
TARGET_NAMES = {"English transcript"}


def list_redundant_english_tracks(service: Any, video_id: str) -> list[dict[str, Any]]:
    response = _execute_with_backoff(
        lambda: service.captions().list(part="id,snippet", videoId=video_id)
    )
    matches: list[dict[str, Any]] = []
    for item in response.get("items", []):
        snippet = item.get("snippet", {}) or {}
        language = str(snippet.get("language") or "")
        name = str(snippet.get("name") or "")
        track_kind = str(snippet.get("trackKind") or "standard")
        # Only remove the exact manual track created by this project. Automatic
        # captions normally use trackKind=ASR and are never selected here.
        if language in TARGET_LANGUAGE_PREFIXES and name in TARGET_NAMES and track_kind != "ASR":
            matches.append(item)
    return matches


def remove_redundant_english_tracks(service: Any, video_id: str, *, dry_run: bool = False) -> dict[str, Any]:
    matches = list_redundant_english_tracks(service, video_id)
    deleted: list[str] = []
    if not dry_run:
        for item in matches:
            caption_id = str(item.get("id") or "").strip()
            if not caption_id:
                continue
            _execute_with_backoff(lambda caption_id=caption_id: service.captions().delete(id=caption_id))
            deleted.append(caption_id)
    return {
        "video_id": video_id,
        "dry_run": dry_run,
        "matched": [
            {
                "id": item.get("id"),
                "language": (item.get("snippet") or {}).get("language"),
                "name": (item.get("snippet") or {}).get("name"),
                "trackKind": (item.get("snippet") or {}).get("trackKind"),
            }
            for item in matches
        ],
        "deleted_ids": deleted,
        "status": "dry_run" if dry_run else "completed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove only the legacy English transcript track created by Xiangqi Lab")
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--assert-absent", action="store_true", help="Fail if a matching manual English transcript still exists")
    args = parser.parse_args()
    result = remove_redundant_english_tracks(build_service(), args.video_id, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.assert_absent and result.get("matched"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
