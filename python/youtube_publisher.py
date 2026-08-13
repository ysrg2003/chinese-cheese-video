from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = ROOT / "config" / "youtube_metadata_policy.json"
DEFAULT_PLAYLISTS_PATH = ROOT / "config" / "youtube_playlists.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
RETRIABLE_STATUS_CODES = {500, 502, 503, 504}


class YouTubePublisherError(RuntimeError):
    """A publish operation failed or is not configured."""


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise YouTubePublisherError(f"Expected JSON object: {path}")
    return value


def _clip(value: str, limit: int) -> str:
    value = str(value or "").strip()
    if len(value) <= limit:
        return value
    clipped = value[: limit - 1].rstrip()
    return clipped + "…"


def _unique(values: list[str], limit: int | None = None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = str(value or "").strip()
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
        if limit is not None and len(result) >= limit:
            break
    return result


def _first_sentence(text: str, fallback: str) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if not clean:
        return fallback
    sentence = re.split(r"(?<=[.!?。！？])\s+", clean, maxsplit=1)[0]
    return _clip(sentence, 180)


def _decode_secret_json(value: str) -> dict[str, Any]:
    raw = value.strip()
    candidates = [raw]
    try:
        candidates.append(base64.b64decode(raw).decode("utf-8"))
    except Exception:
        pass
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (TypeError, json.JSONDecodeError):
            continue
    raise YouTubePublisherError("YOUTUBE_OAUTH_TOKEN_JSON is not valid OAuth token JSON or base64 JSON")


def load_policy(policy_path: str | Path = DEFAULT_POLICY_PATH) -> dict[str, Any]:
    return _load_json(policy_path)


def load_playlists(playlists_path: str | Path = DEFAULT_PLAYLISTS_PATH) -> dict[str, Any]:
    return _load_json(playlists_path)


def _content_config(policy: dict[str, Any], content_type: str, language: str) -> dict[str, Any]:
    content_type = content_type if content_type in policy.get("content_types", {}) else "definition"
    entry = policy["content_types"][content_type]
    language = language if language in {"en", "zh"} else "en"
    return {
        "content_type": content_type,
        "language": language,
        "entry": entry,
        "localized": entry.get(language, entry.get("en", {})),
        "playlist_key": entry.get("playlist_key", {}).get(language),
    }


def build_metadata(
    job: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    playlists: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or load_policy()
    playlists = playlists or load_playlists()
    language = str(job.get("language") or "en").lower()
    language = "zh" if language in {"zh", "cn", "chinese"} else "en"
    content_type = str(job.get("content_type") or job.get("metadata", {}).get("content_type") or "definition")
    config = _content_config(policy, content_type, language)
    language_policy = policy["languages"][language]
    localized = config["localized"]
    requested_playlist_key = str(job.get("playlist_key") or "").strip()
    configured_playlists = playlists.get("playlists", {})
    playlist_key = requested_playlist_key if requested_playlist_key in configured_playlists else (config["playlist_key"] or language_policy["default_playlist_key"])
    playlist_info = configured_playlists.get(playlist_key, {})

    raw_title = str(job.get("title") or localized.get("title_prefix") or "Xiangqi Lesson").strip()
    title_prefix = str(localized.get("title_prefix") or "Xiangqi").strip()
    title = raw_title if title_prefix.casefold() in raw_title.casefold() else f"{raw_title} | {title_prefix}"
    title = _clip(title, int(policy["channel"].get("max_title_chars", 100)))

    primary_keyword = title_prefix
    secondary_keywords = [str(item) for item in localized.get("secondary_keywords", [])]
    supporting_tags = [
        str(job.get("title") or ""),
        str(job.get("theme") or ""),
        str(job.get("source_kind") or ""),
    ]
    tags = _unique(
        list(language_policy.get("base_tags", []))
        + [primary_keyword]
        + secondary_keywords
        + supporting_tags,
        int(policy["channel"].get("max_tags", 15)),
    )
    hashtags = _unique(
        list(language_policy.get("base_hashtags", [])) + list(localized.get("hashtags", [])),
        min(int(policy["channel"].get("max_hashtags", 5)), 5),
    )
    hashtags_text = " ".join(hashtags)
    hook = str(job.get("hook") or _first_sentence(job.get("narration", ""), title)).strip()
    series_name = str(localized.get("series_name") or playlist_info.get("title") or "Xiangqi Lab")
    source_note = str(policy.get("source_note_template", "Original educational Xiangqi board analysis."))
    description = str(policy["description_template"]).format(
        primary_keyword=primary_keyword,
        hook=hook,
        series_name=series_name,
        language_label=language_policy.get("label", language),
        source_note=source_note,
        playlist_cta=language_policy.get("playlist_cta", "Continue the series in the linked playlist."),
        channel_cta=language_policy.get("channel_cta", "Subscribe to Xiangqi Lab."),
        hashtags=hashtags_text,
    )
    description = _clip(description, int(policy["channel"].get("max_description_chars", 5000)))
    return {
        "title": title,
        "description": description,
        "tags": tags,
        "hashtags": hashtags,
        "categoryId": str(policy["channel"].get("category_id", "20")),
        "language": language,
        "defaultAudioLanguage": "zh-Hans" if language == "zh" else "en",
        "content_type": content_type,
        "playlist_key": playlist_key,
        "playlist_title": playlist_info.get("title", playlist_key),
        "privacyStatus": str(os.getenv("YOUTUBE_PUBLISH_MODE", policy["channel"].get("default_privacy_status", "public"))),
    }


def _credentials_from_environment() -> Any:
    try:
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise YouTubePublisherError("Install google-api-python-client and google-auth-oauthlib first") from exc

    token_json = os.getenv("YOUTUBE_OAUTH_TOKEN_JSON")
    if not token_json:
        token_path = os.getenv("YOUTUBE_OAUTH_TOKEN_FILE")
        if token_path and Path(token_path).exists():
            token_json = Path(token_path).read_text(encoding="utf-8")
    if not token_json:
        raise YouTubePublisherError("Missing YOUTUBE_OAUTH_TOKEN_JSON or YOUTUBE_OAUTH_TOKEN_FILE")
    info = _decode_secret_json(token_json)
    credentials = Credentials.from_authorized_user_info(info, scopes=SCOPES)
    if not credentials.valid and not credentials.refresh_token:
        raise YouTubePublisherError("OAuth token is expired and has no refresh token")
    if not credentials.valid:
        from google.auth.transport.requests import Request
        credentials.refresh(Request())
    return credentials


def build_service() -> Any:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise YouTubePublisherError("Install google-api-python-client and google-auth-oauthlib first") from exc
    return build("youtube", "v3", credentials=_credentials_from_environment(), cache_discovery=False)


def _execute_with_backoff(request_factory: Any, *, max_attempts: int = 6) -> dict[str, Any]:
    delay = 2.0
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            response = request_factory().execute()
            return response if isinstance(response, dict) else {}
        except Exception as exc:
            last_error = exc
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status not in RETRIABLE_STATUS_CODES or attempt == max_attempts - 1:
                raise
            time.sleep(min(delay, 60.0))
            delay *= 2
    raise YouTubePublisherError(f"YouTube request failed: {last_error}")


def upload_video(service: Any, video_path: str | Path, metadata: dict[str, Any]) -> dict[str, Any]:
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata["tags"],
            "categoryId": metadata["categoryId"],
            "defaultLanguage": metadata["defaultAudioLanguage"],
            "defaultAudioLanguage": metadata["defaultAudioLanguage"],
        },
        "status": {
            "privacyStatus": metadata["privacyStatus"],
            "selfDeclaredMadeForKids": False,
        },
    }
    request = service.videos().insert(
        part="snippet,status",
        body=body,
        notifySubscribers=True,
        media_body=MediaFileUpload(str(video_path), chunksize=-1, resumable=True),
    )
    response = None
    retry = 0
    while response is None:
        try:
            _, response = request.next_chunk()
        except Exception as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status not in RETRIABLE_STATUS_CODES or retry >= 6:
                raise
            time.sleep(min(2 ** retry, 60))
            retry += 1
    if not response.get("id"):
        raise YouTubePublisherError(f"YouTube upload returned no video id: {response}")
    return response


def ensure_playlist(
    service: Any,
    playlist_config: dict[str, Any],
    *,
    auto_create: bool = True,
    exclude_ids: set[str] | None = None,
    force_create: bool = False,
) -> tuple[str, bool]:
    """Resolve a playlist by title, ignoring IDs known to be stale or deleted.

    YouTube can occasionally return a playlist entry that subsequently produces
    playlistNotFound when playlistItems.list is called.  The caller can pass
    that ID in ``exclude_ids`` so the next resolution creates a fresh playlist
    instead of looping on the same stale identifier.
    """
    title = str(playlist_config["title"])
    excluded = {str(value) for value in (exclude_ids or set()) if str(value).strip()}
    page_token: str | None = None
    while not force_create:
        response = _execute_with_backoff(
            lambda: service.playlists().list(part="id,snippet", mine=True, maxResults=50, pageToken=page_token)
        )
        for item in response.get("items", []):
            playlist_id = str(item.get("id") or "").strip()
            if playlist_id and playlist_id not in excluded and item.get("snippet", {}).get("title") == title:
                return playlist_id, False
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    if not auto_create:
        raise YouTubePublisherError(f"Playlist does not exist and auto creation is disabled: {title}")
    response = _execute_with_backoff(
        lambda: service.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {"title": title, "description": playlist_config.get("description", "")},
                "status": {"privacyStatus": playlist_config.get("privacy_status", "public")},
            },
        )
    )
    if not response.get("id"):
        raise YouTubePublisherError(f"Playlist creation returned no id: {title}")
    return str(response["id"]), True


def _is_playlist_not_found(exc: Exception) -> bool:
    status = getattr(getattr(exc, "resp", None), "status", None)
    message = str(exc)
    return str(status) == "404" and ("playlistNotFound" in message or "playlist" in message.lower())


def add_to_playlist(service: Any, playlist_id: str, video_id: str) -> dict[str, Any]:
    page_token: str | None = None
    while True:
        response = _execute_with_backoff(
            lambda: service.playlistItems().list(
                part="id,contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=page_token,
            )
        )
        for item in response.get("items", []):
            if item.get("contentDetails", {}).get("videoId") == video_id:
                return {"id": item.get("id"), "already_present": True}
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return _execute_with_backoff(
        lambda: service.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        )
    )


def publish_video(
    video_path: str | Path,
    job: dict[str, Any],
    *,
    policy_path: str | Path = DEFAULT_POLICY_PATH,
    playlists_path: str | Path = DEFAULT_PLAYLISTS_PATH,
    service: Any | None = None,
    existing_publication: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = build_metadata(job, policy=load_policy(policy_path), playlists=load_playlists(playlists_path))
    if os.getenv("YOUTUBE_PUBLISH_ENABLED", "0").lower() not in {"1", "true", "yes"}:
        return {"status": "disabled", "metadata": metadata}
    service = service or build_service()
    existing_video_id = str((existing_publication or {}).get("video_id") or "").strip()
    if existing_video_id:
        video_id = existing_video_id
    else:
        video_response = upload_video(service, video_path, metadata)
        video_id = str(video_response["id"])
    playlists = load_playlists(playlists_path)
    playlist_config = playlists["playlists"][metadata["playlist_key"]]
    playlist_id: str | None = None
    playlist_created = False
    try:
        auto_create = os.getenv("YOUTUBE_AUTO_CREATE_PLAYLISTS", "1").lower() in {"1", "true", "yes"}
        auto_create = auto_create and bool(playlists.get("auto_create", True))
        existing_playlist_id = str((existing_publication or {}).get("playlist_id") or "").strip()
        if existing_playlist_id:
            playlist_id = existing_playlist_id
        else:
            playlist_id, playlist_created = ensure_playlist(service, playlist_config, auto_create=auto_create)
        try:
            playlist_response = add_to_playlist(service, playlist_id, video_id)
        except Exception as exc:
            # A stale/deleted playlist must not strand a public video or cause
            # an endless retry loop. Resolve the title again while excluding
            # the bad ID, then create/use a fresh playlist when permitted.
            if not _is_playlist_not_found(exc):
                raise
            stale_playlist_id = playlist_id
            playlist_id = None
            playlist_id, playlist_created = ensure_playlist(
                service,
                playlist_config,
                auto_create=auto_create,
                exclude_ids={stale_playlist_id} if stale_playlist_id else set(),
                force_create=True,
            )
            # Newly-created YouTube playlists can take a short moment before
            # playlistItems.list accepts them consistently.
            time.sleep(2)
            playlist_response = add_to_playlist(service, playlist_id, video_id)
    except Exception as exc:
        return {
            "status": "uploaded_playlist_pending",
            "video_id": video_id,
            "video_url": f"https://www.youtube.com/watch?v={video_id}",
            "playlist_id": playlist_id,
            "playlist_url": f"https://www.youtube.com/playlist?list={playlist_id}" if playlist_id else None,
            "metadata": metadata,
            "error_message": str(exc),
        }
    return {
        "status": "published",
        "video_id": video_id,
        "video_url": f"https://www.youtube.com/watch?v={video_id}",
        "playlist_id": playlist_id,
        "playlist_url": f"https://www.youtube.com/playlist?list={playlist_id}",
        "playlist_created": playlist_created,
        "playlist_item": playlist_response,
        "metadata": metadata,
    }


def bootstrap_oauth(client_secrets_file: str, output_file: str) -> None:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise YouTubePublisherError("Install google-api-python-client and google-auth-oauthlib first") from exc
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
    credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    Path(output_file).write_text(credentials.to_json(), encoding="utf-8")
    print(f"Saved OAuth token JSON to {output_file}. Store its content as a protected GitHub secret; do not commit the file.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a Chinese Cheese Video to YouTube and its matching playlist")
    parser.add_argument("--video", help="Rendered MP4 path")
    parser.add_argument("--job-json", help="Rendered job.json path")
    parser.add_argument("--dry-run", action="store_true", help="Build and print metadata without OAuth or upload")
    parser.add_argument("--auth-client-secrets", help="Run one-time local OAuth bootstrap")
    parser.add_argument("--auth-output", default="youtube-token.json")
    args = parser.parse_args()
    if args.auth_client_secrets:
        bootstrap_oauth(args.auth_client_secrets, args.auth_output)
        return 0
    if not args.video or not args.job_json:
        parser.error("--video and --job-json are required unless --auth-client-secrets is used")
    job = _load_json(args.job_json)
    if args.dry_run:
        print(json.dumps({"status": "dry_run", "metadata": build_metadata(job)}, ensure_ascii=False, indent=2))
        return 0
    result = publish_video(args.video, job)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
