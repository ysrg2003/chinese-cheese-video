from __future__ import annotations

import re
from typing import Any


def normalize_language(value: Any) -> str:
    value = str(value or "en").lower().strip()
    return "zh" if value in {"zh", "cn", "chinese", "中文", "简体中文"} else "en"


def estimate_narration_seconds(text: str, language: str = "en") -> float:
    language = normalize_language(language)
    clean = str(text or "").strip()
    if not clean:
        return 0.0
    if language == "zh":
        units = len(re.findall(r"[\u3400-\u9fff]", clean))
        return max(2.0, units / 4.0)
    words = re.findall(r"\b[\w’'-]+\b", clean)
    return max(2.0, len(words) / 2.35)


def estimate_content_duration(
    narration: str,
    moves: list[dict[str, Any]] | None,
    language: str = "en",
    audio_duration: float | None = None,
    requested_duration: float | None = None,
) -> float:
    move_count = len(moves or [])
    spoken = float(audio_duration or estimate_narration_seconds(narration, language))
    move_time = 0.0 if move_count == 0 else 2.2 + move_count * 1.55
    content_time = max(spoken + 3.0, move_time + 1.2)
    if requested_duration and requested_duration > 0:
        content_time = max(content_time, float(requested_duration))
    return round(max(5.0, content_time), 3)


def retime_moves(moves: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    if not moves:
        return []
    start_padding = min(3.5, max(1.2, duration * 0.12))
    end_padding = min(2.0, max(0.8, duration * 0.08))
    usable = max(1.0, duration - start_padding - end_padding)
    slot = usable / len(moves)
    move_length = min(1.8, max(0.65, slot * 0.62))
    retimed: list[dict[str, Any]] = []
    for index, move in enumerate(moves):
        clone = dict(move)
        start = start_padding + index * slot
        clone["startSec"] = round(start, 3)
        clone["endSec"] = round(min(duration - end_padding, start + move_length), 3)
        retimed.append(clone)
    return retimed


def sync_moves_to_narration_segments(moves: list[dict[str, Any]], segments: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    """Use the audio-aligned move segment windows for board animation."""
    by_ply = {
        int(segment["movePly"]): segment
        for segment in segments
        if segment.get("kind") == "move" and segment.get("movePly") is not None and segment.get("startSec") is not None and segment.get("endSec") is not None
    }
    synced: list[dict[str, Any]] = []
    for move in moves:
        clone = dict(move)
        segment = by_ply.get(int(move.get("ply", 0)))
        if segment:
            start = max(0.0, min(float(segment.get("startSec", 0.0)), duration))
            end = max(start + 0.05, min(float(segment.get("endSec", duration)), duration))
            clone["startSec"] = round(start, 3)
            clone["endSec"] = round(end, 3)
        synced.append(clone)
    return synced


def clamp_captions(captions: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    for cue in captions:
        try:
            start = max(0.0, min(float(cue.get("startSec", 0.0)), duration))
            end = max(start + 0.05, min(float(cue.get("endSec", duration)), duration))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        clean.append({**cue, "startSec": round(start, 3), "endSec": round(end, 3)})
    return clean


def fit_captions(captions: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    clean = clamp_captions(captions, duration)
    if not clean:
        return clean
    last_end = max(float(cue["endSec"]) for cue in clean)
    if last_end < duration * 0.78 and last_end > 0:
        scale = duration / last_end
        clean = [
            {**cue, "startSec": round(min(duration, cue["startSec"] * scale), 3), "endSec": round(min(duration, cue["endSec"] * scale), 3)}
            for cue in clean
        ]
    return clean


def _time_narration_segments_without_audio(segments: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    if not segments or duration <= 0:
        return []
    weights = [max(1, len(str(segment.get("text") or "").split())) for segment in segments]
    total = float(sum(weights)) or 1.0
    cursor = 0.0
    timed: list[dict[str, Any]] = []
    for index, (segment, weight) in enumerate(zip(segments, weights)):
        end = duration if index == len(segments) - 1 else cursor + duration * weight / total
        timed.append({
            **segment,
            "startSec": round(cursor, 3),
            "endSec": round(max(cursor + 0.05, end), 3),
            "source": "narration_segments_fallback",
        })
        cursor = end
    return timed


def _captions_from_timed_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    captions: list[dict[str, Any]] = []
    for segment in segments:
        text = str(segment.get("captionText") or segment.get("text") or "").strip()
        if not text:
            continue
        captions.append({
            "startSec": float(segment.get("startSec", 0.0)),
            "endSec": float(segment.get("endSec", 0.05)),
            "text": text,
            "kind": segment.get("kind", "speech"),
            "movePly": segment.get("movePly"),
            "captionPosition": segment.get("captionPosition", "board" if segment.get("kind") == "move" else "bottom"),
            "source": segment.get("source", "narration_segments_fallback"),
        })
    return captions


def finalize_timing(
    job: dict[str, Any],
    audio_duration: float | None = None,
    requested_duration: float | None = None,
) -> dict[str, Any]:
    duration = estimate_content_duration(
        job.get("narration", ""),
        job.get("moves", []),
        job.get("language", "en"),
        audio_duration=audio_duration,
        requested_duration=requested_duration,
    )
    job["durationInSeconds"] = duration
    job["moves"] = retime_moves(job.get("moves", []), duration)
    narration_segments = [dict(segment) for segment in job.get("narrationSegments", []) if isinstance(segment, dict)]
    timed_segments = [segment for segment in narration_segments if segment.get("startSec") is not None and segment.get("endSec") is not None]
    if narration_segments and not timed_segments:
        narration_segments = _time_narration_segments_without_audio(narration_segments, duration)
        job["narrationSegments"] = narration_segments
        timed_segments = narration_segments
    job["moves"] = sync_moves_to_narration_segments(job["moves"], timed_segments, duration)
    job["captions"] = _captions_from_timed_segments(timed_segments) if timed_segments else fit_captions(job.get("captions", []), duration)
    return job
