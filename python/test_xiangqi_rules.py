import unittest

from director import DEFAULT_MOVE_VARIANTS, make_job, _fallback
from xiangqi_rules import IllegalPositionError, validate_move_sequence


START_FEN = "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR r"


class XiangqiRulesTests(unittest.TestCase):
    def test_standard_position_has_red_to_move_and_legal_sample_line(self):
        result = validate_move_sequence(
            START_FEN,
            [
                {"ply": 1, "from": [0, 6], "to": [0, 5], "piece": "pawn", "side": "red"},
                {"ply": 2, "from": [0, 3], "to": [0, 4], "piece": "pawn", "side": "black"},
                {"ply": 3, "from": [1, 7], "to": [1, 4], "piece": "cannon", "side": "red"},
            ],
        )
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["plies_checked"], 3)
        self.assertEqual(result["moves"][2]["piece"], "cannon")

    def test_video_incident_rejects_advisor_replacing_own_general(self):
        result = validate_move_sequence(
            START_FEN,
            [
                {"ply": 1, "from": [4, 9], "to": [4, 8], "piece": "king", "side": "red"},
                {"ply": 2, "from": [4, 0], "to": [4, 1], "piece": "king", "side": "black"},
                {"ply": 3, "from": [3, 9], "to": [4, 8], "piece": "advisor", "side": "red"},
            ],
        )
        self.assertFalse(result["ok"])
        self.assertIn("friendly", result["errors"][0])

    def test_flying_general_position_is_rejected(self):
        with self.assertRaises(IllegalPositionError):
            validate_move_sequence("4k4/9/9/9/9/9/9/9/9/4K4 r", [])

    def test_move_cannot_expose_flying_general(self):
        fen = "4k4/9/9/9/4R4/9/9/9/9/4K4 r"
        result = validate_move_sequence(
            fen,
            [{"ply": 1, "from": [4, 4], "to": [3, 4], "piece": "rook", "side": "red"}],
        )
        self.assertFalse(result["ok"])
        self.assertIn("check", result["errors"][0])

    def test_advisor_is_diagonal_only_and_stays_in_palace(self):
        result = validate_move_sequence(
            START_FEN,
            [{"ply": 1, "from": [3, 9], "to": [3, 8], "piece": "advisor", "side": "red"}],
        )
        self.assertFalse(result["ok"])
        self.assertIn("geometry", result["errors"][0])

    def test_horse_leg_block_is_rejected(self):
        fen = "4k4/9/9/9/9/9/4P4/9/1P7/1H2K3R r"
        result = validate_move_sequence(
            fen,
            [{"ply": 1, "from": [1, 9], "to": [2, 7], "piece": "knight", "side": "red"}],
        )
        self.assertFalse(result["ok"])
        self.assertIn("geometry", result["errors"][0])

    def test_elephant_eye_block_is_rejected(self):
        fen = "4k4/9/9/9/9/9/3PP4/2B6/9/4K4 r"
        result = validate_move_sequence(
            fen,
            [{"ply": 1, "from": [2, 7], "to": [4, 5], "piece": "bishop", "side": "red"}],
        )
        self.assertFalse(result["ok"])
        self.assertIn("geometry", result["errors"][0])

    def test_cannon_quiet_move_cannot_jump_a_screen(self):
        fen = "4k4/9/9/9/9/9/1P2P4/1C5C1/9/4K3R r"
        result = validate_move_sequence(
            fen,
            [{"ply": 1, "from": [1, 7], "to": [1, 4], "piece": "cannon", "side": "red"}],
        )
        self.assertFalse(result["ok"])
        self.assertIn("geometry", result["errors"][0])

    def test_cannon_capture_requires_exactly_one_screen(self):
        fen = "1r2k3r/9/9/9/9/9/1P2P4/1C5C1/9/4K3R r"
        result = validate_move_sequence(
            fen,
            [{"ply": 1, "from": [1, 7], "to": [1, 0], "piece": "cannon", "side": "red"}],
        )
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["moves"][0]["captured"], "rook")

    def test_soldier_cannot_move_backward_or_sideways_before_river(self):
        result = validate_move_sequence(
            START_FEN,
            [{"ply": 1, "from": [0, 6], "to": [1, 6], "piece": "pawn", "side": "red"}],
        )
        self.assertFalse(result["ok"])
        self.assertIn("geometry", result["errors"][0])

    def test_all_builtin_fallback_variants_are_legal_after_piece_inference(self):
        puzzle = {
            "fen": START_FEN,
            "language": "en",
            "content_type": "opening",
            "source_kind": "rss",
            "title": "Fallback lesson",
        }
        for index, variant in enumerate(DEFAULT_MOVE_VARIANTS):
            puzzle["topic_key"] = f"variant-{index}"
            puzzle["moves"] = variant
            director_data = _fallback(puzzle, "en")
            job = make_job(f"fallback-{index}", puzzle, director_data)
            self.assertEqual(len(job["moves"]), 3)

    def test_declared_piece_and_side_must_match_board(self):
        result = validate_move_sequence(
            START_FEN,
            [{"ply": 1, "from": [0, 6], "to": [0, 5], "piece": "king", "side": "red"}],
        )
        self.assertFalse(result["ok"])
        self.assertIn("declared piece", result["errors"][0])


if __name__ == "__main__":
    unittest.main()
