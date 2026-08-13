import unittest

from visual_director import FIRST_LESSON_FALLBACK, add_visual_storyboard, validate_visual_storyboard


class VisualDirectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.puzzle = {
            "curriculum_lesson_key": "en-001-what-is-xiangqi",
            "visual_mode": "foundation_storyboard",
            "target_seconds": 55,
            "language": "en",
            "title": "What Is Xiangqi?",
        }
        self.job = {
            "id": "storyboard-test",
            "title": "What Is Xiangqi?",
            "language": "en",
            "visual_mode": "foundation_storyboard",
            "narration": "placeholder",
            "narrationSegments": [],
            "captions": [],
        }

    def test_fallback_storyboard_replaces_static_intro_with_seven_visual_scenes(self) -> None:
        storyboard_job = add_visual_storyboard(dict(self.job), self.puzzle)
        self.assertEqual(storyboard_job["visualStoryboardSource"], "fallback")
        self.assertEqual(len(storyboard_job["visualStoryboard"]), 7)
        self.assertEqual(len(storyboard_job["narrationSegments"]), 7)
        self.assertEqual(storyboard_job["moves"] if "moves" in storyboard_job else [], [])
        self.assertEqual(
            [segment["visualKind"] for segment in storyboard_job["narrationSegments"]],
            [scene["visualKind"] for scene in FIRST_LESSON_FALLBACK],
        )
        self.assertTrue(all(segment["captionPosition"] == "bottom" for segment in storyboard_job["narrationSegments"]))
        self.assertGreater(storyboard_job["durationInSeconds"], 40)

    def test_disabled_job_is_unchanged(self) -> None:
        ordinary = {**self.job, "visual_mode": "none", "narration": "Normal lesson"}
        result = add_visual_storyboard(dict(ordinary), {**self.puzzle, "visual_mode": "none"})
        self.assertEqual(result, ordinary)

    def test_storyboard_validation_passes_for_synced_move(self) -> None:
        job = {
            "visual_mode": "storyboard",
            "visualStoryboard": [{"index": 1, "visualKind": "move_path", "headline": "Move One", "visualInstruction": "Show the supplied path."}],
            "moves": [{"ply": 1, "from": [1, 7], "to": [1, 4]}],
            "narrationSegments": [{"kind": "move", "movePly": 1, "visualKind": "move_path", "startSec": 0.0, "endSec": 4.0}],
        }
        self.assertEqual(validate_visual_storyboard(job, audio_duration=4.0), [])

    def test_storyboard_validation_blocks_scene_past_audio(self) -> None:
        job = {
            "visual_mode": "storyboard",
            "visualStoryboard": [{"index": 1, "visualKind": "move_path", "headline": "Move One", "visualInstruction": "Show the supplied path."}],
            "moves": [{"ply": 1, "from": [1, 7], "to": [1, 4]}],
            "narrationSegments": [{"kind": "move", "movePly": 1, "visualKind": "move_path", "startSec": 0.0, "endSec": 7.0}],
        }
        errors = validate_visual_storyboard(job, audio_duration=5.0)
        self.assertTrue(any("exceeds_audio_duration" in error for error in errors))

    def test_generic_move_job_gets_visual_beat_without_rewriting_audio(self) -> None:
        ordinary = {
            "id": "tactics-test",
            "title": "Cannon Tactic",
            "language": "en",
            "visual_mode": "storyboard",
            "content_type": "tactics",
            "narration": "The cannon opens a forcing line.",
            "moves": [{"ply": 1, "from": [1, 7], "to": [1, 4], "piece": "cannon", "side": "red", "purpose": "open the line"}],
            "narrationSegments": [{"kind": "move", "movePly": 1, "text": "The cannon opens a forcing line.", "captionText": "Open the line", "captionPosition": "board"}],
            "captions": [],
        }
        result = add_visual_storyboard(dict(ordinary), {"language": "en", "content_type": "tactics", "visual_mode": "storyboard"})
        self.assertEqual(result["visual_mode"], "storyboard")
        self.assertEqual(result["narration"], ordinary["narration"])
        self.assertEqual(len(result["visualStoryboard"]), 1)
        self.assertEqual(result["visualStoryboard"][0]["visualKind"], "cannon_screen")
        self.assertEqual(result["narrationSegments"][0]["visualKind"], "cannon_screen")

    def test_history_fallback_uses_specialized_visual_progression(self) -> None:
        job = {
            "id": "history-test",
            "title": "A Short History of Xiangqi",
            "language": "en",
            "visual_mode": "storyboard",
            "content_type": "definition",
            "narration": "History introduction.",
            "moves": [],
            "captions": [],
            "narrationSegments": [
                {"kind": "intro", "text": "Xiangqi developed across centuries of Chinese culture."},
                {"kind": "intro", "text": "The game became a contest between two disciplined armies."},
                {"kind": "intro", "text": "Its board preserved a distinctive river and palace structure."},
                {"kind": "intro", "text": "Today, players learn the board before the tactics."},
            ],
        }
        result = add_visual_storyboard(dict(job), {"curriculum_lesson_key": "en-002-history-of-xiangqi", "language": "en", "visual_mode": "storyboard"})
        kinds = [scene["visualKind"] for scene in result["visualStoryboard"]]
        self.assertEqual(kinds[0], "board_overview")
        self.assertIn("two_armies", kinds)
        self.assertIn("river_palaces", kinds)
        self.assertEqual(kinds[-1], "learning_roadmap")
        self.assertNotIn("before_after", kinds)
        self.assertTrue(all(scene["headline"] != "What Changes Next" for scene in result["visualStoryboard"]))
        self.assertEqual(validate_visual_storyboard(result), [])

    def test_definition_fallback_maps_board_terms_to_rendered_visuals(self) -> None:
        job = {
            "id": "definition-test",
            "title": "How the Xiangqi Board Works",
            "language": "en",
            "visual_mode": "storyboard",
            "content_type": "definition",
            "narration": "Board lesson.",
            "moves": [],
            "captions": [],
            "narrationSegments": [
                {"kind": "intro", "text": "The board has nine files and ten ranks."},
                {"kind": "intro", "text": "Pieces stand on intersections, not inside squares."},
                {"kind": "intro", "text": "The river separates the two sides."},
                {"kind": "intro", "text": "Next, we learn the setup."},
            ],
        }
        result = add_visual_storyboard(dict(job), {"curriculum_lesson_key": "en-005-the-9x10-point-board", "language": "en", "visual_mode": "storyboard"})
        self.assertEqual(
            [scene["visualKind"] for scene in result["visualStoryboard"]],
            ["coordinate_map", "intersections", "river_palaces", "learning_roadmap"],
        )


if __name__ == "__main__":
    unittest.main()
