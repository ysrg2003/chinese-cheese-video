import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from visual_qa import verify_rendered_visuals


class RenderedVisualQATests(unittest.TestCase):
    def _job(self, asset_src: str | None = None):
        scene = {
            "index": 1,
            "visualKind": "army_setup",
            "headline": "Piece Families And Homes",
            "visualPlan": {
                "mode": "board_overlay",
                "focus": "piece families at starting homes",
                "primitives": ["piece_family_anchor", "mirror_setup"],
            },
        }
        if asset_src:
            scene["generatedAsset"] = {"src": asset_src, "assetRole": "editorial_backdrop"}
        return {
            "id": "visual-qa-test",
            "visualStoryboard": [scene],
            "narrationSegments": [{"sceneId": 1, "startSec": 0.0, "endSec": 2.0, "kind": "intro", "visualKind": "army_setup"}],
        }

    def _fake_frame(self, _video_path: Path, _second: float, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1080, 1920), (185, 135, 82)).save(output_path, format="JPEG")

    def test_rendered_frame_and_asset_witness_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "job.mp4"
            video.write_bytes(b"x" * 6000)
            public_root = root / "public"
            asset = public_root / "generated" / "visual-qa-test" / "assets" / "scene-01.png"
            asset.parent.mkdir(parents=True)
            Image.new("RGB", (1080, 1920), (185, 135, 82)).save(asset, format="PNG")
            with patch("visual_qa._probe_duration", return_value=2.5), patch("visual_qa._extract_frame", side_effect=self._fake_frame):
                result = verify_rendered_visuals(self._job("generated/visual-qa-test/assets/scene-01.png"), video, root / "qa", public_root)
            self.assertTrue(result["ok"], result["errors"])
            self.assertEqual(result["contract"], "rendered_mp4_scene_asset_witness_v1")
            self.assertEqual(result["scenes"][0]["asset"]["sideStripSimilarity"], 1.0)

    def test_missing_asset_fails_before_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "job.mp4"
            video.write_bytes(b"x" * 6000)
            with patch("visual_qa._probe_duration", return_value=2.5), patch("visual_qa._extract_frame", side_effect=self._fake_frame):
                result = verify_rendered_visuals(self._job("generated/visual-qa-test/assets/missing.png"), video, root / "qa", root / "public")
            self.assertFalse(result["ok"])
            self.assertTrue(any("not present at render time" in error for error in result["errors"]))

    def test_unactionable_plan_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "job.mp4"
            video.write_bytes(b"x" * 6000)
            job = self._job()
            job["visualStoryboard"][0]["visualPlan"] = {"mode": "board_overlay", "focus": "", "primitives": []}
            with patch("visual_qa._probe_duration", return_value=2.5), patch("visual_qa._extract_frame", side_effect=self._fake_frame):
                result = verify_rendered_visuals(job, video, root / "qa", root / "public")
            self.assertFalse(result["ok"])
            self.assertTrue(any("no actionable visualPlan" in error for error in result["errors"]))

    def test_scene_outside_rendered_duration_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "job.mp4"
            video.write_bytes(b"x" * 6000)
            job = self._job()
            job["narrationSegments"][0]["endSec"] = 5.0
            with patch("visual_qa._probe_duration", return_value=2.5), patch("visual_qa._extract_frame", side_effect=self._fake_frame):
                result = verify_rendered_visuals(job, video, root / "qa", root / "public")
            self.assertFalse(result["ok"])
            self.assertTrue(any("exceeds MP4 duration" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
