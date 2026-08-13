import unittest

from timing import retime_moves, sync_moves_to_narration_segments


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
