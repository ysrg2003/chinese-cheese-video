from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_pipeline


class RunPipelineCriticIntegrationTests(unittest.TestCase):
    def _job(self) -> dict:
        return {
            "id": "critic-integration",
            "language": "en",
            "fen": "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR r",
            "moves": [],
            "narrationSegments": [{"sceneId": 1, "kind": "intro", "startSec": 0.0, "endSec": 2.0, "text": "This board is a map of routes."}],
            "visualStoryboard": [{
                "index": 1,
                "visualKind": "board_identity",
                "headline": "Board Map",
                "visualInstruction": "Trace the nine files and ten ranks.",
                "semanticTags": ["board", "routes"],
                "visualPlan": {"mode": "board_overlay", "focus": "board route map", "primitives": ["files", "ranks"]},
            }],
        }

    def _qa(self) -> dict:
        return {"ok": True, "durationSec": 2.0, "errors": [], "scenes": [{"sceneId": 1, "visualKind": "board_identity", "primitives": ["files", "ranks"], "fingerprint": "abc"}]}

    def test_approved_artifact_renders_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "video.mp4"
            video.write_bytes(b"video")
            reviews = [
                {"decision": "approve", "score": 90, "summary": "preflight approved", "scene_repairs": []},
                {"decision": "approve", "score": 90, "summary": "artifact approved", "scene_repairs": []},
            ]
            with patch("run_pipeline.run_prepublication_review", side_effect=reviews) as critic, patch("run_pipeline.render_job", return_value=video) as render, patch("run_pipeline.verify_rendered_visuals", return_value=self._qa()):
                output, qa, review = run_pipeline._reviewed_render(self._job(), {}, root / "stage", root / "public")
            self.assertEqual(output, video)
            self.assertTrue(qa["ok"])
            self.assertEqual(review["decision"], "approve")
            self.assertEqual(render.call_count, 1)
            self.assertEqual(critic.call_count, 2)

    def test_repair_causes_bounded_rerender_before_acceptance(self):
        repair = {
            "decision": "repair",
            "score": 70,
            "summary": "Make route focus more explicit",
            "scene_repairs": [{
                "sceneId": 1,
                "headline": "Route Map",
                "visualInstruction": "Pulse the route intersections.",
                "visualKind": "board_identity",
                "semanticTags": ["routes", "intersections"],
                "visualPlan": {"mode": "board_overlay", "focus": "route intersections", "primitives": ["all_intersections"]},
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "video.mp4"
            video.write_bytes(b"video")
            reviews = [
                {"decision": "approve", "score": 90, "summary": "preflight approved", "scene_repairs": []},
                repair,
                {"decision": "approve", "score": 90, "summary": "preflight approved", "scene_repairs": []},
                {"decision": "approve", "score": 90, "summary": "artifact approved", "scene_repairs": []},
            ]
            with patch("run_pipeline.run_prepublication_review", side_effect=reviews), patch("run_pipeline.render_job", return_value=video) as render, patch("run_pipeline.verify_rendered_visuals", return_value=self._qa()):
                _, _, review = run_pipeline._reviewed_render(self._job(), {}, root / "stage", root / "public")
            self.assertEqual(review["decision"], "approve")
            self.assertEqual(render.call_count, 2)


if __name__ == "__main__":
    unittest.main()
