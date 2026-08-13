import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from visual_assets import _normalise_asset_plan, _validate_and_write_image, add_generated_visual_assets


class VisualAssetPipelineTests(unittest.TestCase):
    def setUp(self):
        self.job = {
            "id": "visual-asset-test",
            "language": "en",
            "visualStoryboard": [
                {"index": 1, "visualKind": "history_timeline", "movePly": None, "narration": "History"},
                {"index": 2, "visualKind": "move_path", "movePly": 1, "narration": "Move"},
                {"index": 3, "visualKind": "cultural_heritage", "movePly": None, "narration": "Culture"},
            ],
        }

    def test_plan_rejects_move_scene_and_caps_count(self):
        prompt = "Create a vertical cinematic Chinese heritage editorial image, no written words, no logos, no board grid, warm lacquer red and antique gold."
        raw = [
            {"sceneIndex": 2, "useGeneratedAsset": True, "assetRole": "editorial_backdrop", "prompt": prompt},
            {"sceneIndex": 1, "useGeneratedAsset": True, "assetRole": "historical_inset", "prompt": prompt},
            {"sceneIndex": 3, "useGeneratedAsset": True, "assetRole": "cultural_inset", "prompt": prompt},
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

    def test_valid_asset_is_saved_and_attached_only_to_static_scene(self):
        image = Image.new("RGB", (720, 1280), color=(125, 53, 31))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        class FakeClient:
            def generate(self, prompt):
                return buffer.getvalue(), "png", {"service_job_id": "fake-job", "mime_type": "image/png", "bytes": len(buffer.getvalue())}

        prompt = "Create a portrait Chinese heritage editorial establishing image with paper, warm lacquer red, no text, no board, and a quiet edge for overlay."
        plan = [{"sceneIndex": 1, "useGeneratedAsset": True, "assetRole": "historical_inset", "prompt": prompt, "reason": "History context"}]
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"VISUAL_ASSET_MAX_PER_VIDEO": "2"}, clear=False), patch("visual_assets.VisualAssetClient.from_environment", return_value=FakeClient()), patch("visual_assets._plan_assets_with_ai", return_value=plan):
            result = add_generated_visual_assets(self.job.copy(), {}, Path(directory) / "stage", Path(directory) / "public")
            asset = result["visualAssets"]["assets"][0]
            self.assertTrue((Path(directory) / "public" / "assets").exists())
            self.assertTrue(asset["src"].startswith("generated/visual-asset-test/assets/"))
            self.assertEqual(result["visualStoryboard"][0]["generatedAsset"]["assetRole"], "historical_inset")
            self.assertNotIn("generatedAsset", result["visualStoryboard"][1])


if __name__ == "__main__":
    unittest.main()
