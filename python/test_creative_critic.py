from __future__ import annotations

import os
import unittest
from copy import deepcopy
from unittest.mock import patch

from creative_critic import apply_repairs, review_job, sync_repaired_scenes


FEN = "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR r"


def valid_job() -> dict:
    return {
        "id": "critic-test",
        "language": "en",
        "fen": FEN,
        "moves": [],
        "narration": "This board is a map of routes.",
        "narrationSegments": [
            {"sceneId": 1, "kind": "intro", "startSec": 0.0, "endSec": 2.0, "text": "This board is a map of routes."}
        ],
        "visualStoryboard": [
            {
                "index": 1,
                "visualKind": "board_identity",
                "headline": "Board Map",
                "narration": "This board is a map of routes.",
                "visualInstruction": "Trace the nine files and ten ranks.",
                "semanticTags": ["board", "routes"],
                "visualPlan": {"mode": "board_overlay", "focus": "board route map", "primitives": ["files", "ranks"]},
            }
        ],
    }


class CreativeCriticTests(unittest.TestCase):
    def test_storyboard_preflight_approves_valid_job_without_mp4(self):
        result = review_job(valid_job(), {}, require_ai=False)
        self.assertEqual(result["decision"], "approve")
        self.assertGreaterEqual(result["score"], 82)

    def test_final_artifact_requires_visual_qa(self):
        result = review_job(valid_job(), {}, visual_qa=None, require_ai=False, final_artifact=True)
        self.assertNotEqual(result["decision"], "approve")
        self.assertTrue(any("final render evidence" in error for error in result["errors"]))

    def test_final_artifact_approves_only_with_ok_visual_qa(self):
        result = review_job(
            valid_job(),
            {},
            visual_qa={"ok": True, "durationSec": 2.0, "errors": [], "scenes": [{"sceneId": 1, "visualKind": "board_identity", "primitives": ["files", "ranks"], "fingerprint": "abc"}]},
            require_ai=False,
            final_artifact=True,
        )
        self.assertEqual(result["decision"], "approve")

    def test_illegal_move_is_fail_closed(self):
        job = valid_job()
        job["moves"] = [{"ply": 1, "from": [3, 9], "to": [4, 9], "piece": "advisor", "side": "red"}]
        result = review_job(job, {}, require_ai=False)
        self.assertEqual(result["decision"], "reject")
        self.assertEqual(result["score"], 0)
        self.assertTrue(any("illegal" in error for error in result["errors"]))

    def test_repairs_cannot_change_moves_or_narration(self):
        job = valid_job()
        original = deepcopy(job)
        review = {"scene_repairs": [{"sceneId": 1, "narration": "invented", "visualInstruction": "Change only the route highlight."}]}
        errors = apply_repairs(job, review)
        self.assertTrue(errors)
        self.assertEqual(job, original)

    def test_safe_repair_is_copied_into_render_segments(self):
        job = valid_job()
        review = {"scene_repairs": [{"sceneId": 1, "headline": "Route Map", "visualInstruction": "Pulse the route intersections.", "visualPlan": {"mode": "board_overlay", "focus": "route intersections", "primitives": ["all_intersections"]}}]}
        self.assertEqual(apply_repairs(job, review), [])
        sync_repaired_scenes(job)
        self.assertEqual(job["narrationSegments"][0]["headline"], "Route Map")
        self.assertEqual(job["narrationSegments"][0]["visualPlan"]["primitives"], ["all_intersections"])

    def test_required_ai_router_missing_is_fail_closed(self):
        with patch.dict(os.environ, {"PREPUBLISH_CRITIC_REQUIRED": "1"}, clear=False), patch("creative_critic.load_router", return_value=None):
            result = review_job(valid_job(), {}, require_ai=True)
        self.assertEqual(result["decision"], "reject")
        self.assertTrue(any("PREPUBLISH_CRITIC_REQUIRED" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
