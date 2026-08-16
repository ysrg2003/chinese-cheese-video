from __future__ import annotations

import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import tts


class _FakeRouter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def complete_auto(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "output_type": "audio",
            "mime_type": "audio/pcm",
            "sample_rate_hz": 24000,
            "data_base64": base64.b64encode(b"pcm-bytes").decode("ascii"),
        }

    def close(self) -> None:
        return None


class RouterTtsTests(unittest.TestCase):
    def test_default_provider_is_ai_router_and_uses_male_schedar_voice(self) -> None:
        fake = _FakeRouter()
        with tempfile.TemporaryDirectory() as directory, patch.object(tts, "load_router", return_value=fake), patch.object(tts, "_pcm_to_mp3") as convert:
            old_provider = os.environ.pop("TTS_PROVIDER", None)
            old_voice = os.environ.pop("TTS_VOICE_EN", None)
            try:
                audio_path, words_path, cues = tts.synthesize(
                    {"language": "en", "narration": "The general stays inside the palace."}, directory
                )
            finally:
                if old_provider is not None:
                    os.environ["TTS_PROVIDER"] = old_provider
                if old_voice is not None:
                    os.environ["TTS_VOICE_EN"] = old_voice
            self.assertEqual(audio_path, Path(directory) / "voice.mp3")
            self.assertEqual(words_path, Path(directory) / "voice_words.json")
            self.assertEqual(cues, [])
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual(fake.calls[0]["output_type"], "audio")
            self.assertEqual(fake.calls[0]["voice"], "Schedar")
            self.assertIn("adult male educational narrator", str(fake.calls[0]["user_prompt"]))
            convert.assert_called_once()

    def test_narration_segments_are_generated_in_bounded_batches(self) -> None:
        calls: list[tuple[str, str]] = []

        def fake_synthesize(text: str, voice: str, audio_path: Path, language: str) -> list[dict[str, object]]:
            calls.append((text, voice))
            audio_path.write_bytes(b"fake-mp3")
            return []

        job = {
            "language": "en",
            "narrationSegments": [
                {"kind": "intro", "text": "First short explanation."},
                {"kind": "move", "text": "The elephant moves two points diagonally."},
                {"kind": "effect", "text": "This protects the river crossing."},
                {"kind": "outro", "text": "Now observe the legal response."},
            ],
        }
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"TTS_BATCH_MAX_SEGMENTS": "2", "TTS_BATCH_MAX_CHARS": "120"}, clear=False
        ), patch.object(tts, "_synthesize_ai_router", side_effect=fake_synthesize), patch.object(
            tts, "_audio_duration_seconds", return_value=1.0
        ), patch.object(tts, "_merge_audio_chunks") as merge:
            cues, batch_count = tts._synthesize_ai_router_batched(job, "Schedar", Path(directory) / "voice.mp3", "en")
        self.assertEqual(batch_count, 2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(cues), 4)
        self.assertEqual(cues[0]["startSec"], 0.0)
        self.assertEqual(cues[-1]["endSec"], 2.0)
        self.assertEqual([cue["source"] for cue in cues], ["ai_router_batched_segment"] * 4)
        merge.assert_called_once()

    def test_pcm_conversion_applies_loudness_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(tts.subprocess, "run") as run:
            output = Path(directory) / "voice.mp3"
            tts._pcm_to_mp3(b"\x00\x00" * 240, output)
            command = run.call_args.args[0]
            self.assertIn("loudnorm=I=-16:TP=-1.5:LRA=7,dynaudnorm=f=150:g=15:p=0.9:m=10", command)
            self.assertIn("-q:a", command)
            self.assertIn("2", command)

    def test_edge_is_called_only_after_ai_router_failure(self) -> None:
        edge = AsyncMock(return_value=[{"startSec": 0.0, "endSec": 0.5, "text": "Fallback"}])
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {"TTS_PROVIDER": "ai_router", "TTS_EDGE_FALLBACK_ENABLED": "1"},
            clear=False,
        ), patch.object(tts, "_synthesize_ai_router", side_effect=RuntimeError("all router routes failed")) as router_call, patch.object(tts, "_synthesize_edge", edge):
            audio_path, _, cues = tts.synthesize(
                {"language": "en", "narration": "The advisor stays inside the palace."}, directory
            )
            provider = json.loads((Path(directory) / "voice_provider.json").read_text(encoding="utf-8"))
        router_call.assert_called_once()
        edge.assert_awaited_once()
        self.assertEqual(cues[0]["text"], "Fallback")
        self.assertEqual(provider["provider_used"], "edge_tts_last_resort")
        self.assertEqual(provider["voice"], "en-US-GuyNeural")
        self.assertEqual(Path(audio_path).name, "voice.mp3")

    def test_disabled_edge_fallback_preserves_router_failure(self) -> None:
        edge = AsyncMock()
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {"TTS_PROVIDER": "ai_router", "TTS_EDGE_FALLBACK_ENABLED": "0"},
            clear=False,
        ), patch.object(tts, "_synthesize_ai_router", side_effect=RuntimeError("all router routes failed")), patch.object(tts, "_synthesize_edge", edge):
            with self.assertRaisesRegex(RuntimeError, "all router routes failed"):
                tts.synthesize({"language": "en", "narration": "Test."}, directory)
        edge.assert_not_awaited()

    def test_explicit_edge_provider_remains_legacy_only(self) -> None:
        with patch.dict(os.environ, {"TTS_PROVIDER": "invalid"}, clear=False), tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "Unsupported TTS_PROVIDER"):
                tts.synthesize({"language": "en", "narration": "Test."}, directory)


if __name__ == "__main__":
    unittest.main()
