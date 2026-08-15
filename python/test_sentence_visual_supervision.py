from __future__ import annotations

import unittest

from sentence_visual_supervision import expand_narration_segments, validate_sentence_visual_coverage
from visual_director import add_visual_storyboard, validate_visual_storyboard


class SentenceVisualSupervisionTests(unittest.TestCase):
    def test_new_unseen_concept_gets_flexible_concept_focus(self) -> None:
        job = {
            "id": "novel-concept",
            "language": "en",
            "narration": "The first pattern changes the rhythm of the position.",
            "narrationSegments": [
                {"kind": "intro", "text": "The first pattern changes the rhythm of the position."}
            ],
        }
        expanded = expand_narration_segments(job)
        self.assertEqual(expanded["sentenceVisualSupervision"]["sentenceCount"], 1)
        intent = expanded["sentenceVisualIntents"][0]
        self.assertEqual(intent["visualTreatment"], "concept_focus")
        self.assertEqual(intent["confidence"], "inferred")
        self.assertEqual(intent["primitives"], ["concept_focus"])
        self.assertEqual(validate_sentence_visual_coverage(expanded), [])

    def test_causal_abstract_language_gets_three_stage_editorial_bridge(self) -> None:
        job = {
            "language": "en",
            "narrationSegments": [{"kind": "intro", "text": "A tempo shift changes initiative after an exchange."}],
        }
        expanded = expand_narration_segments(job)
        intent = expanded["sentenceVisualIntents"][0]
        self.assertEqual(intent["visualTreatment"], "causal_bridge")
        self.assertEqual(intent["confidence"], "editorial")
        self.assertEqual(intent["coverage"], "bridge_only")
        self.assertEqual(intent["bridgeLabels"], ["BASELINE", "EXCHANGE", "INITIATIVE SHIFTS"])
        self.assertEqual(validate_sentence_visual_coverage(expanded), [])

    def test_multiple_sentences_receive_distinct_ids_and_intents(self) -> None:
        job = {
            "language": "en",
            "narrationSegments": [
                {"kind": "intro", "text": "The river divides the board. The next lesson explains the soldiers."}
            ],
        }
        expanded = expand_narration_segments(job)
        self.assertEqual(len(expanded["narrationSegments"]), 2)
        self.assertEqual(len(expanded["sentenceVisualIntents"]), 2)
        self.assertNotEqual(
            expanded["narrationSegments"][0]["sentenceId"],
            expanded["narrationSegments"][1]["sentenceId"],
        )
        self.assertEqual(expanded["narrationSegments"][0]["visualIntent"]["visualTreatment"], "region_split")
        self.assertEqual(expanded["narrationSegments"][1]["visualIntent"]["visualTreatment"], "piece_spotlight")

    def test_expansion_keeps_global_timing_across_untimed_source_segments(self) -> None:
        job = {
            "language": "en",
            "narrationSegments": [
                {"kind": "move", "movePhase": "action", "text": "Move the elephant."},
                {"kind": "move_reply", "movePhase": "reply", "text": "Now block the eye."},
                {"kind": "move_effect", "movePhase": "effect", "text": "The route changes."},
            ],
        }
        expanded = expand_narration_segments(job)
        windows = [(item["startSec"], item["endSec"]) for item in expanded["narrationSegments"]]
        self.assertEqual(len(windows), 3)
        for previous, current in zip(windows, windows[1:]):
            self.assertGreaterEqual(current[0], previous[1])

    def test_expansion_is_idempotent(self) -> None:
        job = {
            "language": "en",
            "narrationSegments": [{"kind": "intro", "text": "A new idea appears."}],
        }
        first = expand_narration_segments(job)
        first_segments = list(first["narrationSegments"])
        second = expand_narration_segments(first)
        self.assertEqual(second["narrationSegments"], first_segments)

    def test_adjacent_unknown_concepts_are_distinct_and_renderable(self) -> None:
        narration = "The first pattern appears. The surprising idea remains."
        job = {
            "id": "adjacent-new-concepts",
            "language": "en",
            "content_type": "definition",
            "narration": narration,
            "narrationSegments": [{"kind": "intro", "text": narration}],
            "moves": [],
            "visual_mode": "storyboard",
        }
        puzzle = {"language": "en", "content_type": "definition", "moves": [], "visualStoryboard": []}
        result = add_visual_storyboard(job, puzzle)
        self.assertEqual(len(result["narrationSegments"]), 2)
        self.assertTrue(all(item["visualKind"] == "board_overview" for item in result["narrationSegments"]))
        self.assertTrue(all("concept_focus" in item["visualPlan"]["primitives"] for item in result["narrationSegments"]))
        self.assertNotEqual(
            result["narrationSegments"][0]["visualPlan"]["focus"],
            result["narrationSegments"][1]["visualPlan"]["focus"],
        )
        self.assertEqual(validate_visual_storyboard(result), [])

    def test_unknown_concept_fallback_is_renderable_and_has_no_fake_move(self) -> None:
        puzzle = {
            "language": "en",
            "content_type": "definition",
            "fen": "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR r",
            "moves": [],
            "title": "A New Strategic Idea",
        }
        job = {
            "id": "novel-concept",
            "language": "en",
            "title": "A New Strategic Idea",
            "content_type": "definition",
            "narration": "The first pattern changes the rhythm of the position.",
            "narrationSegments": [{"kind": "intro", "text": "The first pattern changes the rhythm of the position."}],
            "moves": [],
            "visual_mode": "storyboard",
        }
        result = add_visual_storyboard(job, puzzle)
        self.assertEqual(result["visualStoryboardSource"], "fallback")
        self.assertEqual(result["narrationSegments"][0]["visualIntent"]["visualTreatment"], "concept_focus")
        self.assertIn("concept_focus", result["narrationSegments"][0]["visualPlan"]["primitives"])
        self.assertEqual(result["moves"], [])
        self.assertEqual(validate_visual_storyboard(result), [])


if __name__ == "__main__":
    unittest.main()
