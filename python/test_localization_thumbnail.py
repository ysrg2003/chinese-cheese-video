import tempfile
import unittest
from pathlib import Path

from localization import write_srt, write_vtt
from thumbnail import _headline


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

    def test_thumbnail_headline_stays_short_and_english_primary(self):
        headline = _headline("Set Up All 32 Pieces | Xiangqi Rules", "en")
        self.assertLessEqual(len(headline.replace("\\n", " ").split()), 7)
        self.assertIn("SET", headline)


if __name__ == "__main__":
    unittest.main()
