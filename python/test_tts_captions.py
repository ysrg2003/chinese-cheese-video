from __future__ import annotations

import unittest

from tts import captions_from_word_cues


class CaptionTranscriptTests(unittest.TestCase):
    def test_english_captions_preserve_spoken_word_units(self) -> None:
        cues = [
            {"startSec": 0.0, "endSec": 0.35, "text": "The"},
            {"startSec": 0.35, "endSec": 0.8, "text": "cannon"},
            {"startSec": 0.8, "endSec": 1.2, "text": "opens"},
            {"startSec": 1.2, "endSec": 1.7, "text": "the"},
            {"startSec": 1.7, "endSec": 2.2, "text": "file."},
        ]
        captions = captions_from_word_cues(cues, "en", max_units=3, max_duration=10)
        self.assertEqual(" ".join(cue["text"] for cue in cues), " ".join(cue["text"] for cue in captions))
        self.assertEqual(captions[0]["startSec"], 0.0)
        self.assertEqual(captions[-1]["endSec"], 2.2)
        self.assertTrue(all(caption["source"] == "edge_tts_word_boundaries" for caption in captions))

    def test_chinese_captions_preserve_spoken_units_without_invented_summary(self) -> None:
        cues = [
            {"startSec": 0.0, "endSec": 0.4, "text": "第一步"},
            {"startSec": 0.4, "endSec": 0.9, "text": "打开"},
            {"startSec": 0.9, "endSec": 1.4, "text": "线路"},
        ]
        captions = captions_from_word_cues(cues, "zh", max_units=8, max_duration=10)
        self.assertEqual("第一步打开线路", "".join(caption["text"] for caption in captions))
        self.assertNotIn("战术", "".join(caption["text"] for caption in captions))


if __name__ == "__main__":
    unittest.main()
