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

    def test_pcm_conversion_applies_loudness_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(tts.subprocess, "run") as run:
            output = Path(directory) / "voice.mp3"
            tts._pcm_to_mp3(b"\x00\x00" * 240, output)
            command = run.call_args.args[0]
            self.assertIn("loudnorm=I=-16:TP=-1.5:LRA=7", command)
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
