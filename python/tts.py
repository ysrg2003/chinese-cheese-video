from __future__ import annotations

import asyncio
import json
import os
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
