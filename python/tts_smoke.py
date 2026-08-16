from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import tts


TEXT = "The advisor moves one point diagonally and remains inside the palace."


def main() -> int:
    parser = argparse.ArgumentParser(description="Real AI Router Gemini-TTS smoke test")
    parser.add_argument("--output-dir", default="tts-smoke")
    args = parser.parse_args()

    os.environ["TTS_PROVIDER"] = "ai_router"
    os.environ["TTS_VOICE_EN"] = "Schedar"
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path, words_path, cues = tts.synthesize(
        {"language": "en", "narration": TEXT}, output_dir
    )
    audio_path = Path(audio_path)
    words_path = Path(words_path)
    if not audio_path.exists() or audio_path.stat().st_size <= 0:
        raise RuntimeError("AI Router TTS did not create a non-empty voice.mp3")
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    duration = float(probe.stdout.strip())
    if duration <= 0:
        raise RuntimeError(f"AI Router TTS produced an invalid duration: {duration}")
    loudness_probe = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(audio_path), "-af", "ebur128=peak=true", "-f", "null", "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    loudness_text = loudness_probe.stderr
    if "Summary:" not in loudness_text or "I:" not in loudness_text:
        raise RuntimeError("AI Router TTS loudness analysis did not return an ebur128 summary")
    manifest = {
        "provider": os.environ["TTS_PROVIDER"],
        "voice": os.environ["TTS_VOICE_EN"],
        "language": "en",
        "model_route": "ai-provider-router audio route",
        "sample_text": TEXT,
        "audio_path": str(audio_path),
        "audio_bytes": audio_path.stat().st_size,
        "duration_seconds": duration,
        "word_cue_count": len(cues),
        "loudness_filter": "loudnorm=I=-16:TP=-1.5:LRA=7,dynaudnorm=f=150:g=15:p=0.9:m=10",
        "loudness_analysis": "ffmpeg ebur128 peak=true completed",
        "words_path": str(words_path),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
