import unittest

from visual_director import FIRST_LESSON_FALLBACK, add_visual_storyboard


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

    def test_non_foundation_job_is_unchanged(self) -> None:
        ordinary = {**self.job, "visual_mode": None, "narration": "Normal lesson"}
        result = add_visual_storyboard(dict(ordinary), {**self.puzzle, "visual_mode": None})
        self.assertEqual(result, ordinary)


if __name__ == "__main__":
    unittest.main()
