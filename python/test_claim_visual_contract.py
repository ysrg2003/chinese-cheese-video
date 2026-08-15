from __future__ import annotations

import os
import unittest

from creative_critic import _filter_unsafe_repairs, review_job
from visual_director import _semantic_visual_contract


class ClaimVisualContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous = os.environ.get("PREPUBLISH_CRITIC_REQUIRED")
        os.environ["PREPUBLISH_CRITIC_REQUIRED"] = "0"

    def tearDown(self) -> None:
        if self.previous is None:
            os.environ.pop("PREPUBLISH_CRITIC_REQUIRED", None)
        else:
            os.environ["PREPUBLISH_CRITIC_REQUIRED"] = self.previous

    def test_horse_leg_claim_selects_horse_leg_primitive(self) -> None:
        semantic = _semantic_visual_contract(
            {
                "kind": "move_constraint",
                "movePhase": "constraint",
                "movePly": 1,
                "text": "The Horse Leg is blocked.",
                "move": {
                    "piece": "knight",
                    "side": "black",
                    "claims": [{"claimType": "horse_leg_block"}],
                },
            },
            "rule_focus",
            "en",
        )
        self.assertIn("horse_leg", semantic["visualPlan"]["primitives"])
        self.assertNotIn("elephant_eye", semantic["visualPlan"]["primitives"])

    def test_critic_does_not_block_valid_storyboard_on_empty_repair(self) -> None:
        review = {
            "decision": "repair",
            "score": 78,
            "summary": "Needs a visual correction.",
            "scene_repairs": [],
            "deterministic": {"errors": []},
        }
        result = _filter_unsafe_repairs({}, review)
        self.assertEqual(result["decision"], "repair")
        self.assertLessEqual(result["score"], 79)
        self.assertIn("discarded_unsafe_repairs", result)
        self.assertTrue(any("no actionable" in error for error in result.get("errors", [])))

    def test_critic_rejects_scene_without_claim_primitive(self) -> None:
        job = {
            "language": "en",
            "fen": "test",
            "moves": [{"ply": 1, "piece": "knight", "claims": [{"claimType": "horse_leg_block"}], "purpose": "show the rule"}],
            "claimsByPly": {1: [{"claimType": "horse_leg_block"}]},
            "claimProof": {"ok": True},
            "researchBundle": {"status": "grounded", "sourceHash": "test"},
            "visualStoryboard": [{
                "index": 1,
                "movePly": 1,
                "visualInstruction": "Show the move.",
                "visualPlan": {"mode": "board_overlay", "focus": "piece", "primitives": ["piece_anchor"]},
            }],
            "narrationSegments": [{"sceneId": 1, "movePly": 1, "movePhase": "constraint", "text": "The Horse Leg is blocked."}],
        }
        result = review_job(job, {}, require_ai=False)
        self.assertNotEqual(result["decision"], "approve")
        self.assertTrue(any("horse_leg" in error for error in result.get("errors", [])))


if __name__ == "__main__":
    unittest.main()
