from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

from ai_router_bridge import load_router

try:
    import edge_tts
except ImportError:  # Legacy provider is optional when AI Router TTS is enabled.
    edge_tts = None


# Schedar is the selected male Gemini-TTS voice for both channel languages.
# Keep the default here aligned with GitHub Actions so local and autonomous
# production cannot silently diverge.
VOICE_BY_LANGUAGE = {
    "en": "Schedar",
    "zh": "Schedar",
}

# Edge TTS is deliberately last-resort only. These are male voices and are
# never attempted while the AI Router chain is still succeeding.
EDGE_VOICE_BY_LANGUAGE = {
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


async def _synthesize_edge(text: str, voice: str, audio_path: Path) -> list[dict[str, Any]]:
    if edge_tts is None:
        raise RuntimeError("Edge-TTS is not installed")
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


def _pcm_to_mp3(pcm: bytes, output_path: Path, *, sample_rate_hz: int = 24000, channels: int = 1) -> None:
    """Convert Router PCM output to the MP3 artifact consumed by Remotion."""
    wav_path = output_path.with_suffix(".router.wav")
    try:
        with wave.open(str(wav_path), "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate_hz)
            wav_file.writeframes(pcm)
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path),
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=7,dynaudnorm=f=150:g=15:p=0.9:m=10",
                "-ar", "24000", "-ac", str(channels),
                "-codec:a", "libmp3lame", "-q:a", "2", str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        wav_path.unlink(missing_ok=True)


def _synthesize_ai_router(text: str, voice: str, audio_path: Path, language: str) -> list[dict[str, Any]]:
    router = load_router()
    if router is None:
        raise RuntimeError("AI Router is required for TTS but could not be imported")
    prompt = (
        "Speak as a clear, calm adult male educational narrator. "
        "Read exactly the following text, without adding, omitting, or paraphrasing any words. "
        f"The language is {language}.\n\n{text}"
    )
    try:
        result = router.complete_auto(
            user_prompt=prompt,
            output_type="audio",
            operation="video_narration_tts",
            voice=voice,
        )
        encoded = str(result.get("data_base64") or "")
        if not encoded:
            raise RuntimeError("AI Router TTS returned no audio data")
        pcm = base64.b64decode(encoded)
        mime_type = str(result.get("mime_type") or "audio/pcm").lower()
        if "mpeg" in mime_type or "mp3" in mime_type:
            audio_path.write_bytes(pcm)
        elif "wav" in mime_type or "wave" in mime_type:
            audio_path.write_bytes(pcm)
        else:
            _pcm_to_mp3(pcm, audio_path, sample_rate_hz=int(result.get("sample_rate_hz") or 24000))
        return []
    finally:
        close = getattr(router, "close", None)
        if callable(close):
            close()


def _audio_duration_seconds(audio_path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return max(0.05, float(result.stdout.strip()))


def _merge_audio_chunks(chunks: list[Path], output_path: Path) -> None:
    if not chunks:
        raise RuntimeError("No TTS audio chunks were generated")
    concat_path = output_path.with_suffix(".concat.txt")
    entries = []
    for chunk in chunks:
        escaped = chunk.as_posix().replace("'", "'\\\\''")
        entries.append(f"file '{escaped}'")
    concat_path.write_text("\n".join(entries) + "\n", encoding="utf-8")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_path),
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=7,dynaudnorm=f=150:g=15:p=0.9:m=10,aresample=async=1:first_pts=0",
                "-ar", "24000", "-ac", "1", "-codec:a", "libmp3lame", "-q:a", "2", str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        concat_path.unlink(missing_ok=True)


def _narration_batches(job: dict[str, Any], language: str) -> list[list[dict[str, Any]]]:
    segments = [segment for segment in job.get("narrationSegments") or [] if str(segment.get("text") or "").strip()]
    if not segments:
        return []
    try:
        max_chars = max(180, min(1200, int(os.getenv("TTS_BATCH_MAX_CHARS", "480"))))
    except ValueError:
        max_chars = 480
    try:
        max_segments = max(1, min(6, int(os.getenv("TTS_BATCH_MAX_SEGMENTS", "3"))))
    except ValueError:
        max_segments = 3
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    chars = 0
    for segment in segments:
        text = str(segment.get("text") or "").strip()
        if current and (len(current) >= max_segments or chars + len(text) > max_chars):
            batches.append(current)
            current = []
            chars = 0
        current.append(segment)
        chars += len(text)
    if current:
        batches.append(current)
    return batches


def _synthesize_ai_router_batched(job: dict[str, Any], voice: str, audio_path: Path, language: str) -> tuple[list[dict[str, Any]], int]:
    batches = _narration_batches(job, language)
    if not batches:
        cues = _synthesize_ai_router(str(job.get("narration") or ""), voice, audio_path, language)
        return cues, 1
    with tempfile.TemporaryDirectory(prefix="xiangqi-tts-") as directory:
        chunk_paths: list[Path] = []
        cues: list[dict[str, Any]] = []
        cursor = 0.0
        for index, batch in enumerate(batches):
            chunk_path = Path(directory) / f"chunk-{index:03d}.mp3"
            batch_text = " ".join(str(segment.get("text") or "").strip() for segment in batch)
            _synthesize_ai_router(batch_text, voice, chunk_path, language)
            duration = _audio_duration_seconds(chunk_path)
            weights = [max(1, len(_spoken_units(segment.get("text"), language))) for segment in batch]
            total = float(sum(weights)) or 1.0
            local_cursor = 0.0
            for segment, weight in zip(batch, weights):
                local_end = duration if segment is batch[-1] else local_cursor + duration * weight / total
                cues.append({
                    "startSec": round(cursor + local_cursor, 3),
                    "endSec": round(max(cursor + local_cursor + 0.05, cursor + local_end), 3),
                    "text": str(segment.get("text") or "").strip(),
                    "source": "ai_router_batched_segment",
                })
                local_cursor = local_end
            chunk_paths.append(chunk_path)
            cursor += duration
        _merge_audio_chunks(chunk_paths, audio_path)
        return cues, len(batches)


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
        aligned.append({**segment, "startSec": round(start, 3), "endSec": round(max(start + 0.05, end or start), 3), "source": "audio_segment_alignment"})
    return aligned


def captions_from_narration_segments(segments: list[dict[str, Any]], language: Any = "en") -> list[dict[str, Any]]:
    """Use one short spoken segment per cue; no caption persists across moves."""
    captions = []
    for segment in segments:
        text = str(segment.get("captionText") or segment.get("text", "")).strip()
        if not text:
            continue
        captions.append({
            "startSec": float(segment.get("startSec", 0.0)),
            "endSec": float(segment.get("endSec", 0.05)),
            "text": text,
            "kind": segment.get("kind", "speech"),
            "movePly": segment.get("movePly"),
            "captionPosition": segment.get("captionPosition", "board" if segment.get("kind") == "move" else "bottom"),
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
    voice = os.getenv(f"TTS_VOICE_{language.upper()}", VOICE_BY_LANGUAGE[language]).strip()
    provider = os.getenv("TTS_PROVIDER", "ai_router").strip().lower()
    provider_used = provider
    fallback_error: str | None = None
    batch_count = 1
    if provider == "edge_tts":
        voice = os.getenv(f"TTS_EDGE_VOICE_{language.upper()}", EDGE_VOICE_BY_LANGUAGE[language]).strip()
        cues = asyncio.run(_synthesize_edge(job["narration"], voice, audio_path))
        provider_used = "edge_tts_explicit"
        cue_source = "edge_tts_word_boundaries"
    elif provider == "ai_router":
        try:
            # load_router() owns the complete ordered model/key chain. We do
            # not rotate keys or models here and we never call Edge first.
            cues, batch_count = _synthesize_ai_router_batched(job, voice, audio_path, language)
            cue_source = "ai_router_batched_segments" if batch_count > 1 or job.get("narrationSegments") else "ai_router_audio_duration"
        except Exception as exc:
            fallback_enabled = os.getenv("TTS_EDGE_FALLBACK_ENABLED", "1").strip().lower() in {"1", "true", "yes"}
            if not fallback_enabled:
                raise
            fallback_voice = os.getenv(
                f"TTS_EDGE_VOICE_{language.upper()}", EDGE_VOICE_BY_LANGUAGE[language]
            ).strip()
            fallback_error = f"{type(exc).__name__}: {exc}"[:1000]
            cues = asyncio.run(_synthesize_edge(job["narration"], fallback_voice, audio_path))
            provider_used = "edge_tts_last_resort"
            cue_source = "edge_tts_word_boundaries"
    else:
        raise RuntimeError(f"Unsupported TTS_PROVIDER: {provider}")
    word_json_path.write_text(json.dumps(cues, ensure_ascii=False, indent=2), encoding="utf-8")
    vtt_path = out / "voice.vtt"
    lines = ["WEBVTT", ""]
    for index, cue in enumerate(cues, start=1):
        lines.extend([str(index), f"{_vtt_time(cue['startSec'])} --> {_vtt_time(cue['endSec'])}", cue["text"], ""])
    vtt_path.write_text("\n".join(lines), encoding="utf-8")
    (out / "voice_provider.json").write_text(
        json.dumps(
            {
                "requested_provider": provider,
                "provider_used": provider_used,
                "voice": voice if provider_used.startswith("ai_router") else os.getenv(
                    f"TTS_EDGE_VOICE_{language.upper()}", EDGE_VOICE_BY_LANGUAGE[language]
                ).strip(),
                "language": language,
                "cue_source": cue_source,
                "fallback_error": fallback_error,
                "batch_count": batch_count,
                "batch_max_chars": os.getenv("TTS_BATCH_MAX_CHARS", "480"),
                "batch_max_segments": os.getenv("TTS_BATCH_MAX_SEGMENTS", "3"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return audio_path, word_json_path, cues
