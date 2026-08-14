import tempfile
import unittest
from pathlib import Path

from localization import write_srt, write_vtt
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

    def test_thumbnail_asset_gate_requires_both_localized_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            en = root / "thumbnail_en.jpg"
            zh = root / "thumbnail_zh.jpg"
            from PIL import Image
            Image.new("RGB", (1280, 720), (20, 30, 40)).save(en, format="JPEG")
            Image.new("RGB", (1280, 720), (20, 30, 40)).save(zh, format="JPEG")
            self.assertEqual(validate_thumbnail_assets({"english": str(en), "zh_studio_localized": str(zh)}), [])

    def test_thumbnail_asset_gate_rejects_missing_or_wrong_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "thumbnail_en.jpg"
            from PIL import Image
            Image.new("RGB", (100, 100), (20, 30, 40)).save(path, format="JPEG")
            errors = validate_thumbnail_assets({"english": str(path), "zh_studio_localized": str(path.with_name("missing.jpg"))})
            self.assertTrue(any("dimensions invalid" in error for error in errors))
            self.assertTrue(any("thumbnail file missing" in error for error in errors))

    def test_thumbnail_headline_stays_short_and_english_primary(self):
        headline = _headline("Set Up All 32 Pieces | Xiangqi Rules", "en")
        self.assertLessEqual(len(headline.replace("\\n", " ").split()), 7)
        self.assertIn("SET", headline)


if __name__ == "__main__":
    unittest.main()
