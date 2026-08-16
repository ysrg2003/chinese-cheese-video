from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import tts


# Official Google Gemini-TTS male voices from the 2026-08-16 catalog.
GEMINI_MALE_VOICES = [
    "Achird",
    "Algenib",
    "Algieba",
    "Alnilam",
    "Charon",
    "Enceladus",
    "Fenrir",
    "Iapetus",
    "Orus",
    "Puck",
    "Rasalgethi",
    "Sadachbia",
    "Sadaltager",
    "Schedar",
    "Umbriel",
    "Zubenelgenubi",
]
EDGE_MALE_VOICES = ["en-US-GuyNeural"]
SAMPLE_TEXT = "The advisor moves one point diagonally and remains inside the palace."


def duration_seconds(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def safe_name(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate isolated samples for all official male TTS voices")
    parser.add_argument("--output-dir", default="tts-voice-comparison")
    parser.add_argument("--include-edge", action="store_true")
    args = parser.parse_args()

    root = Path(args.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    os.environ["TTS_PROVIDER"] = "ai_router"
    os.environ["TTS_EDGE_FALLBACK_ENABLED"] = "0"
    results: list[dict[str, object]] = []

    samples = [("ai_router_gemini", voice) for voice in GEMINI_MALE_VOICES]
    if args.include_edge:
        samples.append(("edge_tts_last_resort_reference", EDGE_MALE_VOICES[0]))

    for provider_family, voice in samples:
        sample_dir = root / f"{provider_family}__{safe_name(voice)}"
        sample_dir.mkdir(parents=True, exist_ok=True)
        try:
            if provider_family == "ai_router_gemini":
                os.environ["TTS_PROVIDER"] = "ai_router"
                os.environ["TTS_VOICE_EN"] = voice
                audio_path, words_path, cues = tts.synthesize(
                    {"language": "en", "narration": SAMPLE_TEXT}, sample_dir
                )
            else:
                os.environ["TTS_PROVIDER"] = "edge_tts"
                os.environ["TTS_EDGE_VOICE_EN"] = voice
                audio_path, words_path, cues = tts.synthesize(
                    {"language": "en", "narration": SAMPLE_TEXT}, sample_dir
                )
            audio_path = Path(audio_path)
            duration = duration_seconds(audio_path)
            result = {
                "provider_family": provider_family,
                "voice": voice,
                "status": "success",
                "audio_path": str(audio_path),
                "audio_bytes": audio_path.stat().st_size,
                "duration_seconds": duration,
                "word_cue_count": len(cues),
                "words_path": str(words_path),
                "sample_text": SAMPLE_TEXT,
            }
        except Exception as exc:
            result = {
                "provider_family": provider_family,
                "voice": voice,
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}"[:1200],
                "sample_text": SAMPLE_TEXT,
            }
        (sample_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        results.append(result)

    summary = {
        "sample_count": len(results),
        "success_count": sum(item["status"] == "success" for item in results),
        "failure_count": sum(item["status"] == "failed" for item in results),
        "voices": results,
        "fallback_policy": "Edge TTS is last-resort in production; it is included here only as a labeled reference sample.",
    }
    (root / "comparison.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    # A provider outage or one unavailable preview voice should be visible in
    # the report but should not discard successful samples from other voices.
    return 0 if summary["success_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
