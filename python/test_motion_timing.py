import unittest

from timing import fit_narration_segments_to_duration, retime_moves, sync_moves_to_narration_segments


class MotionTimingTests(unittest.TestCase):
    def test_animation_window_is_shorter_than_spoken_move_window(self) -> None:
        moves = [{
            "ply": 1,
            "from": [1, 7],
            "to": [1, 4],
            "piece": "cannon",
            "side": "red",
            "label": "Aim through the screen",
        }]
        retimed = retime_moves(moves, 12.0)
        move = retimed[0]
        self.assertGreater(move["endSec"], move["startSec"])
        self.assertGreaterEqual(move["animationStartSec"], move["startSec"])
        self.assertLessEqual(move["animationEndSec"], move["endSec"])
        self.assertLess(move["animationEndSec"] - move["animationStartSec"], move["endSec"] - move["startSec"])
        self.assertLessEqual(move["animationEndSec"] - move["animationStartSec"], 0.95)

    def test_visual_storyboard_windows_fit_real_audio_duration(self) -> None:
        segments = [
            {"kind": "intro", "sceneId": 1, "startSec": 0.0, "endSec": 10.8},
            {"kind": "intro", "sceneId": 2, "startSec": 10.8, "endSec": 20.9},
            {"kind": "intro", "sceneId": 3, "startSec": 20.9, "endSec": 31.1},
            {"kind": "intro", "sceneId": 4, "startSec": 31.1, "endSec": 41.3},
            {"kind": "intro", "sceneId": 5, "startSec": 41.3, "endSec": 52.7},
            {"kind": "intro", "sceneId": 6, "startSec": 52.7, "endSec": 64.2},
            {"kind": "intro", "sceneId": 7, "startSec": 64.2, "endSec": 75.0},
        ]
        fitted = fit_narration_segments_to_duration(segments, 50.213)
        self.assertEqual(fitted[0]["startSec"], 0.0)
        self.assertAlmostEqual(fitted[-1]["endSec"], 50.213, places=3)
        self.assertTrue(all(segment["endSec"] <= 50.213 for segment in fitted))
        self.assertTrue(all(fitted[index]["endSec"] <= fitted[index + 1]["startSec"] + 0.01 for index in range(len(fitted) - 1)))

    def test_audio_alignment_recomputes_fast_animation_window(self) -> None:
        moves = [{
            "ply": 1,
            "from": [0, 6],
            "to": [0, 5],
            "piece": "pawn",
            "side": "red",
            "label": "Open a route",
            "startSec": 0.0,
            "endSec": 1.0,
        }]
        synced = sync_moves_to_narration_segments(
            moves,
            [{"kind": "move", "movePly": 1, "startSec": 4.0, "endSec": 7.0}],
            10.0,
        )
        move = synced[0]
        self.assertEqual(move["startSec"], 4.0)
        self.assertEqual(move["endSec"], 7.0)
        self.assertEqual(move["animationStartSec"], 4.0)
        self.assertLess(move["animationEndSec"], 7.0)


if __name__ == "__main__":
    unittest.main()
