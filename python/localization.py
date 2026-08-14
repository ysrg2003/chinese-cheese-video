from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from ai_router_bridge import load_router
from tts import align_narration_segments_to_cues, captions_from_narration_segments, captions_from_word_cues, synthesize
from youtube_publisher import YouTubePublisherError, _execute_with_backoff


class LocalizationError(RuntimeError):
    """Raised when a required translation or localization artifact cannot be produced."""


ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
CJK_RE = re.compile(r"[\u3400-\u9fff]")


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _reject_arabic(text: str, field: str) -> str:
    if ARABIC_RE.search(text):
        raise LocalizationError(f"Arabic text is not allowed in {field}")
    return text


def _require_zh(text: str, field: str) -> str:
    text = _reject_arabic(_clean_text(text), field)
    if not text or not CJK_RE.search(text):
        raise LocalizationError(f"Chinese localization is empty or not Chinese: {field}")
    return text


def _english_segments(job: dict[str, Any]) -> list[dict[str, Any]]:
    segments = job.get("narrationSegments")
    if isinstance(segments, list) and segments:
        return [
            {
                "index": index,
                "kind": str(segment.get("kind") or "speech"),
                "movePly": segment.get("movePly"),
                "text": _clean_text(segment.get("text")),
            }
            for index, segment in enumerate(segments)
            if isinstance(segment, dict) and _clean_text(segment.get("text"))
        ]
    narration = _clean_text(job.get("narration"))
    return [{"index": 0, "kind": "speech", "movePly": None, "text": narration}] if narration else []


def _translation_prompt(job: dict[str, Any], english_metadata: dict[str, Any]) -> tuple[str, str]:
    source_segments = _english_segments(job)
    system = (
        "You are a professional Xiangqi educational translator. Return JSON only. "
        "Translate from English into natural Simplified Chinese for mainland Chinese viewers. "
        "Preserve Xiangqi piece names and all move meaning exactly. Never invent moves, coordinates, "
        "rules, captures, or strategy. Do not output Arabic. Keep segment indexes unchanged."
    )
    user = json.dumps(
        {
            "task": "Create Chinese localization for one already-validated English Xiangqi video.",
            "output_schema": {
                "title": "Simplified Chinese title",
                "description": "Simplified Chinese description with no Arabic",
                "segments": [{"index": 0, "text": "translated segment"}],
            },
            "english_title": english_metadata.get("title"),
            "english_description": english_metadata.get("description"),
            "english_segments": source_segments,
        },
        ensure_ascii=False,
    )
    return system, user


def translate_job_to_chinese(job: dict[str, Any], english_metadata: dict[str, Any]) -> dict[str, Any]:
    existing = job.get("localization", {}).get("zh") if isinstance(job.get("localization"), dict) else None
    if isinstance(existing, dict) and existing.get("title") and existing.get("segments"):
        payload = existing
    else:
        router = load_router()
        if router is None:
            raise LocalizationError("AI Router is not available for Chinese localization")
        system, user = _translation_prompt(job, english_metadata)
        try:
            payload = router.complete_json(
                chain=os.getenv("AI_ROUTER_CHAIN", "default"),
                operation=f"localization:zh:{job.get('id', 'unknown')}",
                system_prompt=system,
                user_prompt=user,
            )
        except Exception as exc:
            raise LocalizationError(f"Chinese translation failed: {exc}") from exc
        finally:
            router.close()
    if not isinstance(payload, dict):
        raise LocalizationError("Chinese translation did not return a JSON object")
    title = _require_zh(payload.get("title"), "title")
    description = _require_zh(payload.get("description"), "description")
    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list):
        raise LocalizationError("Chinese translation did not return segments")
    by_index: dict[int, str] = {}
    for item in raw_segments:
        if not isinstance(item, dict):
            raise LocalizationError("Chinese segment is not an object")
        index = int(item.get("index"))
        by_index[index] = _require_zh(item.get("text"), f"segment[{index}]")
    source_segments = _english_segments(job)
    if set(by_index) != {int(item["index"]) for item in source_segments}:
        raise LocalizationError("Chinese segment indexes do not match the English narration")
    segments = []
    for source in source_segments:
        segments.append({
            "kind": source["kind"],
            "movePly": source.get("movePly"),
            "text": by_index[int(source["index"])],
            "captionText": by_index[int(source["index"])],
            "captionPosition": "board" if source["kind"] == "move" else "bottom",
        })
    return {"title": title, "description": description, "segments": segments}


def _srt_time(seconds: float) -> str:
    millis = int(round(max(0.0, float(seconds)) * 1000))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(captions: list[dict[str, Any]], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for index, caption in enumerate(captions, start=1):
        text = _clean_text(caption.get("text"))
        if not text:
            continue
        start = float(caption.get("startSec", 0.0))
        end = max(start + 0.05, float(caption.get("endSec", start + 0.05)))
        lines.extend([str(index), f"{_srt_time(start)} --> {_srt_time(end)}", text, ""])
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def write_vtt(captions: list[dict[str, Any]], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = ["WEBVTT", ""]
    for index, caption in enumerate(captions, start=1):
        text = _clean_text(caption.get("text"))
        if not text:
            continue
        start = float(caption.get("startSec", 0.0))
        end = max(start + 0.05, float(caption.get("endSec", start + 0.05)))
        lines.extend([str(index), f"{_vtt_time(start)} --> {_vtt_time(end)}", text, ""])
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def _vtt_time(seconds: float) -> str:
    millis = int(round(max(0.0, float(seconds)) * 1000))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def generate_localization_assets(job: dict[str, Any], english_metadata: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    if output_dir is None:
        raise LocalizationError("Localization output directory is required")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if not _english_segments(job):
        raise LocalizationError("English narration is missing; cannot create Chinese audio or captions")
    zh = translate_job_to_chinese(job, english_metadata)
    zh_job = dict(job)
    zh_job["language"] = "zh"
    zh_job["narration"] = " ".join(segment["text"] for segment in zh["segments"])
    zh_job["narrationSegments"] = zh["segments"]
    zh_audio, _, zh_word_cues = synthesize(zh_job, output / "zh")
    aligned = align_narration_segments_to_cues(
        zh["segments"], zh_word_cues, "zh", fallback_duration=float(job.get("durationInSeconds") or 0)
    )
    zh_captions = captions_from_narration_segments(aligned, "zh") if aligned else captions_from_word_cues(zh_word_cues, "zh")
    zh_srt = write_srt(zh_captions, output / "zh" / "captions.srt")
    zh_vtt = write_vtt(zh_captions, output / "zh" / "captions.vtt")
    en_captions = job.get("captions") or []
    en_srt = write_srt(en_captions, output / "en" / "captions.srt")
    en_vtt = write_vtt(en_captions, output / "en" / "captions.vtt")
    payload = {
        "zh": {
            "title": zh["title"],
            "description": zh["description"],
            "audio_path": str(zh_audio),
            "caption_srt": str(zh_srt),
            "caption_vtt": str(zh_vtt),
            "duration_seconds": float(zh_word_cues[-1]["endSec"]) if zh_word_cues else 0.0,
            "segments": zh["segments"],
            "audio_track_status": "generated_studio_upload_required",
        },
        "en": {"caption_srt": str(en_srt), "caption_vtt": str(en_vtt)},
        "notes": "YouTube Data API captions and localizations are automated. Alternate audio attachment requires eligible YouTube Studio multi-language-audio access.",
    }
    (output / "localization.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _upload_caption(service: Any, video_id: str, caption_path: str | Path, language: str, name: str) -> dict[str, Any]:
    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(str(caption_path), mimetype="application/octet-stream", resumable=False)
    captions_api = service.captions()
    existing_id = None
    if hasattr(captions_api, "list"):
        response = _execute_with_backoff(lambda: captions_api.list(part="id,snippet", videoId=video_id))
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            if snippet.get("language") == language and snippet.get("name") == name:
                existing_id = item.get("id")
                break
    if existing_id and hasattr(captions_api, "update"):
        body = {"id": existing_id, "snippet": {"videoId": video_id, "language": language, "name": name, "isDraft": False}}
        return _execute_with_backoff(lambda: captions_api.update(part="snippet", body=body, media_body=media))
    body = {"snippet": {"videoId": video_id, "language": language, "name": name, "isDraft": False}}
    return _execute_with_backoff(lambda: captions_api.insert(part="snippet", body=body, media_body=media))


def upload_caption_tracks(service: Any, video_id: str, assets: dict[str, Any]) -> dict[str, Any]:
    uploaded: dict[str, Any] = {}
    tracks = [
        ("en", assets.get("en", {}).get("caption_srt"), "English transcript"),
        ("zh-Hans", assets.get("zh", {}).get("caption_srt"), "简体中文 transcript"),
    ]
    for language, path, name in tracks:
        if not path or not Path(path).exists():
            continue
        try:
            uploaded[language] = _upload_caption(service, video_id, path, language, name)
        except Exception as exc:
            uploaded[language] = {"status": "failed", "error": str(exc)}
    return uploaded


def update_localized_metadata(service: Any, video_id: str, english_metadata: dict[str, Any], zh: dict[str, Any]) -> dict[str, Any]:
    body = {
        "id": video_id,
        "snippet": {
            "title": english_metadata["title"],
            "description": english_metadata["description"],
            "tags": english_metadata.get("tags", []),
            "categoryId": english_metadata.get("categoryId", "20"),
            "defaultLanguage": "en",
        },
        "localizations": {
            "en": {"title": english_metadata["title"], "description": english_metadata["description"]},
            "zh-Hans": {"title": zh["title"], "description": zh["description"]},
        },
    }
    return _execute_with_backoff(lambda: service.videos().update(part="snippet,localizations", body=body))


def set_thumbnail(service: Any, video_id: str, thumbnail_path: str | Path) -> dict[str, Any]:
    from googleapiclient.http import MediaFileUpload

    path = Path(thumbnail_path)
    if not path.exists():
        raise YouTubePublisherError(f"Thumbnail does not exist: {path}")
    media = MediaFileUpload(str(path), mimetype="image/jpeg", resumable=False)
    return _execute_with_backoff(lambda: service.thumbnails().set(videoId=video_id, media_body=media))
