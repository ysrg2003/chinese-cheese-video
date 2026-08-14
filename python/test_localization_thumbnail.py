import tempfile
import unittest
from pathlib import Path

from localization import validate_localization_assets, write_srt, write_vtt
from thumbnail import _headline, validate_thumbnail_assets


class LocalizationThumbnailTests(unittest.TestCase):
    def test_srt_and_vtt_write_exact_timing(self):
        captions = [
            {"startSec": 0.0, "endSec": 1.25, "text": "Move one."},
            {"startSec": 1.25, "endSec": 2.5, "text": "第一步。"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            srt = write_srt(captions, Path(directory) / "captions.srt")
            vtt = write_vtt(captions, Path(directory) / "captions.vtt")
            self.assertIn("00:00:00,000 --> 00:00:01,250", srt.read_text())
            self.assertIn("00:00:01.250 --> 00:00:02.500", vtt.read_text())
            self.assertIn("第一步。", srt.read_text())

    def test_thumbnail_asset_gate_requires_only_english_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            en = root / "thumbnail_en.jpg"
            from PIL import Image
            Image.new("RGB", (1280, 720), (20, 30, 40)).save(en, format="JPEG")
            self.assertEqual(validate_thumbnail_assets({"default": str(en), "english": str(en)}), [])

    def test_thumbnail_asset_gate_rejects_missing_or_wrong_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "thumbnail_en.jpg"
            from PIL import Image
            Image.new("RGB", (100, 100), (20, 30, 40)).save(path, format="JPEG")
            errors = validate_thumbnail_assets({"english": str(path)})
            self.assertTrue(any("dimensions invalid" in error for error in errors))

    def test_localization_gate_accepts_disabled_english_captions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("zh/voice.mp3", "zh/captions.srt", "zh/captions.vtt"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"artifact")
            assets = {
                "en": {"enabled": False, "source": "english_captions_disabled_in_video"},
                "zh": {
                    "title": "什么是中国象棋？",
                    "description": "这是一个中国象棋教学视频。",
                    "audio_path": str(root / "zh/voice.mp3"),
                    "caption_srt": str(root / "zh/captions.srt"),
                    "caption_vtt": str(root / "zh/captions.vtt"),
                },
            }
            self.assertEqual(validate_localization_assets(assets), [])

    def test_thumbnail_headline_stays_short_and_english_primary(self):
        headline = _headline("Set Up All 32 Pieces | Xiangqi Rules", "en")
        self.assertLessEqual(len(headline.replace("\\n", " ").split()), 7)
        self.assertIn("SET", headline)


if __name__ == "__main__":
    unittest.main()
