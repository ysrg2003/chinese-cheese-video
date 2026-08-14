from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from director import build_narration_segments
from run_pipeline import apply_caption_delivery_policy
from tts import align_narration_segments_to_cues, captions_from_narration_segments, captions_from_word_cues


class CaptionTranscriptTests(unittest.TestCase):
    def test_english_teaching_cues_remain_enabled_by_default(self) -> None:
        job = {"language": "en", "captions": [{"text": "spoken words"}], "captions_source": "edge_tts_word_boundaries_short"}
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("YOUTUBE_ENGLISH_CAPTIONS_IN_VIDEO", None)
            result = apply_caption_delivery_policy(job)
        self.assertEqual(result["captions"], [{"text": "spoken words"}])
        self.assertEqual(result["captions_source"], "edge_tts_word_boundaries_short")

    def test_english_teaching_cues_can_be_explicitly_disabled(self) -> None:
        job = {"language": "en", "captions": [{"text": "spoken words"}], "captions_source": "edge_tts_word_boundaries_short"}
        with patch.dict(os.environ, {"YOUTUBE_ENGLISH_CAPTIONS_IN_VIDEO": "0"}, clear=False):
            result = apply_caption_delivery_policy(job)
        self.assertEqual(result["captions"], [])
        self.assertEqual(result["captions_source"], "english_captions_disabled_in_video")

    def test_chinese_caption_delivery_is_not_changed_by_english_policy(self) -> None:
        job = {"language": "zh", "captions": [{"text": "中文"}], "captions_source": "zh_audio"}
        result = apply_caption_delivery_policy(job)
        self.assertEqual(result["captions"], [{"text": "中文"}])
        self.assertEqual(result["captions_source"], "zh_audio")

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

    def test_move_narration_segments_are_short_and_aligned_to_audio(self) -> None:
        moves = [
            {"ply": 1, "from": [0, 6], "to": [0, 5], "piece": "pawn", "side": "red", "label": "Advance"},
            {"ply": 2, "from": [0, 3], "to": [0, 4], "piece": "pawn", "side": "black", "label": "Reply"},
        ]
        narration, segments = build_narration_segments("Watch the opening idea.", moves, "en", "opening")
        cues = [
            {"startSec": 0.0, "endSec": 0.8, "text": "Watch the opening idea."},
            {"startSec": 0.8, "endSec": 1.2, "text": "Move"},
            {"startSec": 1.2, "endSec": 1.8, "text": "1:"},
            {"startSec": 1.8, "endSec": 2.4, "text": "the red pawn"},
            {"startSec": 2.4, "endSec": 3.2, "text": "goes from file 1, rank 7 to file 1, rank 6;"},
            {"startSec": 3.2, "endSec": 4.0, "text": "watch how this develops the position."},
            {"startSec": 4.0, "endSec": 4.5, "text": "Move"},
            {"startSec": 4.5, "endSec": 5.1, "text": "2:"},
            {"startSec": 5.1, "endSec": 5.8, "text": "the black pawn"},
            {"startSec": 5.8, "endSec": 6.6, "text": "goes from file 1, rank 4 to file 1, rank 5;"},
            {"startSec": 6.6, "endSec": 7.4, "text": "watch how this develops the position."},
        ]
        aligned = align_narration_segments_to_cues(segments, cues, "en", fallback_duration=7.4)
        captions = captions_from_narration_segments(aligned, "en")
        self.assertIn("Move 1", narration)
        self.assertIn("Move 2", narration)
        self.assertEqual(len(captions), 9)
        self.assertEqual(captions[1]["movePly"], 1)
        self.assertEqual(captions[1]["kind"], "move")
        self.assertEqual(captions[2]["kind"], "move_reply")
        self.assertEqual(captions[3]["kind"], "move_effect")
        self.assertEqual(captions[4]["kind"], "move_constraint")
        self.assertEqual(captions[5]["movePly"], 2)
        self.assertLessEqual(captions[1]["endSec"], captions[5]["startSec"])
        self.assertLess(len(captions[1]["text"].split()), 24)
        self.assertEqual(captions[0]["captionPosition"], "bottom")
        self.assertEqual(captions[1]["captionPosition"], "board")
        self.assertIn("likely response", narration)
        self.assertIn("the position changes", narration)
        self.assertIn("Move 1", segments[1]["text"])
        self.assertEqual(segments[1]["movePhase"], "action")
        self.assertEqual(segments[2]["movePhase"], "reply")
        self.assertEqual(segments[3]["movePhase"], "effect")
        self.assertEqual(segments[4]["movePhase"], "constraint")
        self.assertLess(len(segments[1]["captionText"].split()), len(segments[1]["text"].split()))

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
