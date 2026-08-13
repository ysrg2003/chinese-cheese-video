from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

import edge_tts


VOICE_BY_LANGUAGE = {
    "en": "en-US-GuyNeural",
    "zh": "zh-CN-YunjianNeural",
}


def normalize_language(value: Any) -> str:
    value = str(value or "en").lower().strip()
    return "zh" if value in {"zh", "cn", "chinese", "中文", "简体中文"} else "en"


def _vtt_time(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


async def _synthesize(text: str, voice: str, audio_path: Path) -> list[dict[str, Any]]:
    communicate = edge_tts.Communicate(text, voice=voice)
    cues: list[dict[str, Any]] = []
    with audio_path.open("wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 10_000_000
                end = start + chunk["duration"] / 10_000_000
                cues.append({"startSec": round(start, 3), "endSec": round(end, 3), "text": chunk["text"]})
    return cues


def _spoken_units(text: Any, language: Any = "en") -> list[str]:
    normalized_language = normalize_language(language)
    value = str(text or "")
    if normalized_language == "zh":
        return re.findall(r"[\u3400-\u9fff]|[A-Za-z0-9]+", value)
    return re.findall(r"[\w’'-]+", value)


def align_narration_segments_to_cues(
    segments: list[dict[str, Any]],
    cues: list[dict[str, Any]],
    language: Any = "en",
    *,
    fallback_duration: float | None = None,
) -> list[dict[str, Any]]:
    """Attach exact audio windows to intro/move narration segments in order."""
    if not segments:
        return []
    if not cues:
        duration = float(fallback_duration or 0.0)
        weights = [max(1, len(_spoken_units(segment.get("text"), language))) for segment in segments]
        total = float(sum(weights)) or 1.0
        cursor = 0.0
        aligned: list[dict[str, Any]] = []
        for index, (segment, weight) in enumerate(zip(segments, weights)):
            end = duration if index == len(segments) - 1 else cursor + duration * weight / total
            aligned.append({**segment, "startSec": round(cursor, 3), "endSec": round(max(cursor + 0.05, end), 3), "source": "narration_segments"})
            cursor = end
        return aligned

    aligned = []
    cue_index = 0
    for segment in segments:
        expected = max(1, len(_spoken_units(segment.get("text"), language)))
        start = None
        end = None
        consumed = 0
        while cue_index < len(cues) and consumed < expected:
            cue = cues[cue_index]
            cue_index += 1
            cue_text = str(cue.get("text", "")).strip()
            units = len(_spoken_units(cue_text, language)) or 1
            start = float(cue.get("startSec", 0.0)) if start is None else start
            end = max(float(cue.get("endSec", 0.0)), float(start) + 0.05)
            consumed += units
        if start is None:
            start = float(aligned[-1]["endSec"]) if aligned else 0.0
            end = start + 0.05
        aligned.append({**segment, "startSec": round(start, 3), "endSec": round(max(start + 0.05, end or start), 3), "source": "edge_tts_segment_alignment"})
    return aligned


def captions_from_narration_segments(segments: list[dict[str, Any]], language: Any = "en") -> list[dict[str, Any]]:
    """Use one short spoken segment per cue; no caption persists across moves."""
    captions = []
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        captions.append({
            "startSec": float(segment.get("startSec", 0.0)),
            "endSec": float(segment.get("endSec", 0.05)),
            "text": text,
            "kind": segment.get("kind", "speech"),
            "movePly": segment.get("movePly"),
            "source": segment.get("source", "move_narration_audio"),
        })
    return captions


def captions_from_word_cues(
    cues: list[dict[str, Any]],
    language: Any = "en",
    *,
    max_units: int = 8,
    max_duration: float = 2.8,
) -> list[dict[str, Any]]:
    """Create display captions from the exact text and timing spoken by Edge-TTS.

    The previous pipeline let the director invent summary captions independently
    from narration. That is useful for editorial overlays, but it cannot be
    called a transcript. This function preserves every WordBoundary text unit
    exactly once and only groups adjacent units for readable on-screen timing.
    """
    normalized_language = normalize_language(language)
    joiner = "" if normalized_language == "zh" else " "
    captions: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_units = 0

    def flush() -> None:
        nonlocal current, current_units
        if not current:
            return
        captions.append(
            {
                "startSec": round(float(current[0]["startSec"]), 3),
                "endSec": round(float(current[-1]["endSec"]), 3),
                "text": joiner.join(str(item.get("text", "")).strip() for item in current if str(item.get("text", "")).strip()),
                "source": "edge_tts_word_boundaries",
            }
        )
        current = []
        current_units = 0

    for cue in cues:
        text = str(cue.get("text", "")).strip()
        if not text:
            continue
        start = float(cue.get("startSec", 0.0))
        end = max(start + 0.05, float(cue.get("endSec", start + 0.05)))
        if current:
            elapsed = end - float(current[0]["startSec"])
            if current_units >= max_units or elapsed > max_duration:
                flush()
        current.append({"startSec": start, "endSec": end, "text": text})
        current_units += 1
    flush()
    return captions


def captions_from_narration(text: str, duration: float, language: Any = "en") -> list[dict[str, Any]]:
    """Split the exact narration into timed display cues when boundaries are absent."""
    import re

    clean = " ".join(str(text or "").split()).strip()
    if not clean or duration <= 0:
        return []
    normalized_language = normalize_language(language)
    parts = [part.strip() for part in re.split(r"(?<=[.!?。！？])\\s+", clean) if part.strip()]
    if not parts:
        parts = [clean]
    weights = [max(1, len(re.findall(r"[\\u3400-\\u9fff]", part)) if normalized_language == "zh" else len(re.findall(r"\\b[\\w’'-]+\\b", part))) for part in parts]
    total = float(sum(weights)) or 1.0
    captions: list[dict[str, Any]] = []
    cursor = 0.0
    for index, (part, weight) in enumerate(zip(parts, weights)):
        end = duration if index == len(parts) - 1 else cursor + duration * (weight / total)
        captions.append({
            "startSec": round(cursor, 3),
            "endSec": round(max(cursor + 0.05, end), 3),
            "text": part,
            "source": "narration_fallback",
        })
        cursor = end
    return captions


def synthesize(job: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path, list[dict[str, Any]]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    audio_path = out / "voice.mp3"
    word_json_path = out / "voice_words.json"
    language = normalize_language(job.get("language"))
    voice = os.getenv(f"TTS_VOICE_{language.upper()}", VOICE_BY_LANGUAGE[language])
    cues = asyncio.run(_synthesize(job["narration"], voice, audio_path))
    word_json_path.write_text(json.dumps(cues, ensure_ascii=False, indent=2), encoding="utf-8")
    vtt_path = out / "voice.vtt"
    lines = ["WEBVTT", ""]
    for index, cue in enumerate(cues, start=1):
        lines.extend([str(index), f"{_vtt_time(cue['startSec'])} --> {_vtt_time(cue['endSec'])}", cue["text"], ""])
    vtt_path.write_text("\n".join(lines), encoding="utf-8")
    return audio_path, word_json_path, cues
