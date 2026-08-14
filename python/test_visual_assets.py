import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from visual_assets import _normalise_asset_plan, _validate_and_write_image, add_generated_visual_assets, validate_and_annotate_visual_assets


class VisualAssetPipelineTests(unittest.TestCase):
    def setUp(self):
        self.job = {
            "id": "visual-asset-test",
            "language": "en",
            "visualStoryboard": [
                {"index": 1, "visualKind": "river_palaces", "movePly": None, "narration": "River"},
                {"index": 2, "visualKind": "move_path", "movePly": 1, "narration": "Move"},
                {"index": 3, "visualKind": "rule_focus", "movePly": None, "narration": "Palace rule"},
            ],
        }

    def test_plan_rejects_move_scene_and_caps_count(self):
        prompt = "Edit only the transparent masked region; preserve everything outside it exactly; add a flat cool-blue flowing-water texture inside the existing river band; no text or changed pieces."
        raw = [
            {"sceneIndex": 2, "useGeneratedAsset": True, "assetRole": "editorial_backdrop", "editPrompt": prompt},
            {"sceneIndex": 1, "useGeneratedAsset": True, "assetRole": "historical_inset", "editPrompt": prompt},
            {"sceneIndex": 3, "useGeneratedAsset": True, "assetRole": "cultural_inset", "editPrompt": prompt},
        ]
        plans = _normalise_asset_plan(raw, self.job, maximum=1)
        self.assertEqual([plan["sceneIndex"] for plan in plans], [1])
        self.assertEqual(plans[0]["assetRole"], "historical_inset")

    def test_validate_and_write_png(self):
        image = Image.new("RGB", (512, 768), color=(128, 45, 33))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        with tempfile.TemporaryDirectory() as directory:
            path, metadata = _validate_and_write_image(buffer.getvalue(), "png", Path(directory) / "asset")
            self.assertTrue(path.exists())
            self.assertEqual(path.suffix, ".png")
            self.assertEqual((metadata["width"], metadata["height"]), (512, 768))

    def test_missing_credentials_keeps_board_fallback(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"CHATGPT_VISUAL_API_KEY": "", "VISUAL_ASSET_ENABLED": "1"}, clear=False):
            result = add_generated_visual_assets(self.job.copy(), {}, Path(directory) / "stage", Path(directory) / "public")
        self.assertEqual(result["visualAssets"]["reason"], "disabled_or_missing_service_credentials")
        self.assertEqual(result["visualAssets"]["assets"], [])

    def test_asset_contract_requires_durable_file_scene_mapping_and_timing(self):
        image = Image.new("RGB", (720, 1280), color=(125, 53, 31))
        with tempfile.TemporaryDirectory() as directory:
            public_root = Path(directory) / "public"
            asset_path = public_root / "generated" / "contract-test" / "assets" / "scene-01.png"
            asset_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(asset_path, format="PNG")
            job = {
                "id": "contract-test",
                "visualStoryboard": [{"index": 1, "visualKind": "river_palaces", "generatedAsset": {"src": "generated/contract-test/assets/scene-01.png", "assetRole": "editorial_backdrop"}}],
                "narrationSegments": [{"sceneId": 1, "startSec": 0.0, "endSec": 2.0}],
                "visualAssets": {"assets": [{"sceneIndex": 1, "src": "generated/contract-test/assets/scene-01.png", "assetRole": "editorial_backdrop"}]},
            }
            errors = validate_and_annotate_visual_assets(job, public_root=public_root)
            self.assertEqual(errors, [])
            self.assertEqual(job["visualAssets"]["contract"], "durable_file_hash_scene_timing_v1")
            self.assertEqual(job["visualAssets"]["manifest"][0]["visibilityDurationSec"], 2.0)

    def test_asset_contract_rejects_missing_file(self):
        job = {
            "id": "missing-test",
            "visualStoryboard": [{"index": 1, "visualKind": "river_palaces", "generatedAsset": {"src": "generated/missing/assets/scene.png", "assetRole": "editorial_backdrop"}}],
            "narrationSegments": [{"sceneId": 1, "startSec": 0.0, "endSec": 2.0}],
            "visualAssets": {"assets": [{"sceneIndex": 1, "src": "generated/missing/assets/scene.png", "assetRole": "editorial_backdrop"}]},
        }
        errors = validate_and_annotate_visual_assets(job, public_root=Path(tempfile.mkdtemp()))
        self.assertTrue(any("missing file" in error for error in errors))

    def test_valid_asset_is_saved_and_attached_only_to_static_scene(self):
        image = Image.new("RGB", (720, 1280), color=(125, 53, 31))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        class FakeClient:
            def reference_edit(self, reference_path, mask_path, edit_prompt):
                return buffer.getvalue(), "png", {"service_job_id": "fake-job", "mime_type": "image/png", "bytes": len(buffer.getvalue()), "mode": "reference_edit"}

        prompt = "Edit only the transparent masked region; preserve everything outside it exactly; add a flat cool-blue flowing-water texture inside the existing river band; no text or changed pieces."
        plan = [{"sceneIndex": 1, "useGeneratedAsset": True, "assetRole": "historical_inset", "editPrompt": prompt, "reason": "River context"}]
        def fake_reference_render(job, scene, stage_dir):
            reference_dir = stage_dir / "references"
            reference_dir.mkdir(parents=True, exist_ok=True)
            reference = reference_dir / "scene-01.png"
            mask = reference_dir / "scene-01.mask.png"
            Image.new("RGB", (1080, 1920), (190, 150, 80)).save(reference)
            Image.new("RGBA", (1080, 1920), (0, 0, 0, 0)).save(mask)
            return reference, mask
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"VISUAL_ASSET_MAX_PER_VIDEO": "2"}, clear=False), patch("visual_assets.VisualAssetClient.from_environment", return_value=FakeClient()), patch("visual_assets._plan_assets_with_ai", return_value=plan), patch("visual_assets.render_reference_scene", side_effect=fake_reference_render):
            result = add_generated_visual_assets(self.job.copy(), {}, Path(directory) / "stage", Path(directory) / "public")
            asset = result["visualAssets"]["assets"][0]
            self.assertTrue((Path(directory) / "public" / "assets").exists())
            self.assertTrue(asset["src"].startswith("generated/visual-asset-test/assets/"))
            self.assertEqual(result["visualStoryboard"][0]["generatedAsset"]["assetRole"], "historical_inset")
            self.assertNotIn("generatedAsset", result["visualStoryboard"][1])


if __name__ == "__main__":
    unittest.main()
