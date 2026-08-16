from __future__ import annotations

import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
    def test_default_provider_is_ai_router_and_uses_male_charon_voice(self) -> None:
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
            self.assertEqual(fake.calls[0]["voice"], "Charon")
            self.assertIn("adult male educational narrator", str(fake.calls[0]["user_prompt"]))
            convert.assert_called_once()

    def test_explicit_edge_provider_remains_legacy_only(self) -> None:
        with patch.dict(os.environ, {"TTS_PROVIDER": "invalid"}, clear=False), tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "Unsupported TTS_PROVIDER"):
                tts.synthesize({"language": "en", "narration": "Test."}, directory)


if __name__ == "__main__":
    unittest.main()
