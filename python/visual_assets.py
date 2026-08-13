"""Optional AI-generated visual assets for the autonomous Xiangqi video pipeline.

The canonical Remotion board is never replaced. Assets are generated only for selected
non-move scenes, stored per job, and rendered as a restrained editorial backdrop.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from PIL import Image

from ai_router_bridge import load_router


ASSET_API_DEFAULT = "https://yousefsg-chatgpt-api.hf.space"
MAX_ASSETS_DEFAULT = 2
POLL_SECONDS = 3.0
ALLOWED_ROLES = {"editorial_backdrop", "historical_inset", "cultural_inset", "concept_inset"}
INELIGIBLE_KINDS = {"move_path", "attack_line", "capture_sequence", "cannon_screen", "defense_zone", "threat_marker"}

VISUAL_ASSET_PLANNER_INSTRUCTIONS = """
You are the asset planner for an autonomous Xiangqi educational video. Return valid JSON only:
{"assets":[{"sceneIndex":1,"useGeneratedAsset":true,"assetRole":"editorial_backdrop","prompt":"English image prompt","reason":"short factual reason"}]}

Study the supplied narration and canonical board storyboard. Select zero, one, or two non-move scenes where a carefully controlled generated image would make the spoken idea more tangible. Do not generate an asset merely to decorate a board scene. The canonical Xiangqi board, real move arrows, piece positions, captions, and timing remain the primary teaching layer.

An eligible generated asset is an editorial atmospheric backdrop or inset, for example an ancient Chinese military-map texture for history, carved wooden Xiangqi tokens for cultural context, or a restrained strategic landscape for a high-level concept. Do not select a scene that explains an exact legal move, exact square, coordinate, capture, tactical line, or board geometry: those must remain deterministic Remotion diagrams.

Every prompt must be English, portrait-friendly, and contain all of these constraints: no written words, no numerals, no logos, no watermarks, no readable Chinese characters, no Western chessboard, no Xiangqi board grid, no identifiable real person, no hands moving pieces, no UI, no collage, and a clear central subject with quiet edges for overlay. Use one consistent premium editorial style: warm cinematic Chinese-heritage palette, lacquer red, ink black, antique gold, natural paper texture, dramatic soft light, realistic but tasteful, suitable behind a 9:16 educational video. Do not claim historical facts not in the narration.

Allowed assetRole values: editorial_backdrop, historical_inset, cultural_inset, concept_inset.
""".strip()


@dataclass(frozen=True)
class VisualAssetClient:
    base_url: str
    api_key: str
    timeout_seconds: int

    @classmethod
    def from_environment(cls) -> "VisualAssetClient | None":
        enabled = os.getenv("VISUAL_ASSET_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}
        api_key = os.getenv("CHATGPT_VISUAL_API_KEY", "").strip()
        if not enabled or not api_key:
            return None
        return cls(
            base_url=os.getenv("CHATGPT_VISUAL_API_BASE", ASSET_API_DEFAULT).rstrip("/"),
            api_key=api_key,
            timeout_seconds=max(60, int(os.getenv("VISUAL_ASSET_TIMEOUT_SECONDS", "720"))),
        )

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def generate(self, prompt: str) -> tuple[bytes, str, dict[str, Any]]:
        created = requests.post(
            f"{self.base_url}/v1/visual-assets/jobs",
            headers=self.headers,
            json={"prompt": prompt},
            timeout=45,
        )
        created.raise_for_status()
        job_id = str(created.json().get("job_id") or "")
        if not job_id:
            raise RuntimeError("visual asset service did not return job_id")

        deadline = time.monotonic() + self.timeout_seconds
        last_payload: dict[str, Any] = {}
        while time.monotonic() < deadline:
            response = requests.get(
                f"{self.base_url}/v1/visual-assets/jobs/{job_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30,
            )
            response.raise_for_status()
            last_payload = response.json()
            status = str(last_payload.get("status") or "")
            if status == "done":
                downloaded = requests.get(
                    f"{self.base_url}/v1/visual-assets/jobs/{job_id}/download",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=120,
                )
                downloaded.raise_for_status()
                return downloaded.content, str(last_payload.get("extension") or "png"), {"service_job_id": job_id, **last_payload}
            if status == "error":
                raise RuntimeError(str(last_payload.get("error") or "visual asset job failed"))
            time.sleep(POLL_SECONDS)
        raise TimeoutError(f"visual asset job timed out after {self.timeout_seconds}s: {job_id}")


def _positive_int(value: Any, default: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _asset_prompt_is_safe(value: Any) -> bool:
    prompt = str(value or "").strip()
    return 60 <= len(prompt) <= 2500 and "arabic" not in prompt.lower()


def _eligible_scenes(job: dict[str, Any]) -> dict[int, dict[str, Any]]:
    eligible: dict[int, dict[str, Any]] = {}
    for index, scene in enumerate(job.get("visualStoryboard", []), start=1):
        if not isinstance(scene, dict):
            continue
        scene_index = _positive_int(scene.get("index"), index)
        visual_kind = str(scene.get("visualKind") or "")
        if scene.get("movePly") is not None or visual_kind in INELIGIBLE_KINDS:
            continue
        eligible[scene_index] = scene
    return eligible


def _plan_assets_with_ai(job: dict[str, Any], puzzle: dict[str, Any]) -> list[dict[str, Any]]:
    router = load_router()
    if router is None:
        return []
    payload = {
        "language": job.get("language", "en"),
        "title": job.get("title"),
        "objective": job.get("objective") or puzzle.get("objective"),
        "content_type": job.get("content_type") or puzzle.get("content_type"),
        "visual_focus": job.get("visual_focus") or puzzle.get("visual_focus"),
        "scenes": [
            {
                "sceneIndex": scene.get("index", index),
                "movePly": scene.get("movePly"),
                "visualKind": scene.get("visualKind"),
                "narration": scene.get("narration"),
                "visualInstruction": scene.get("visualInstruction"),
            }
            for index, scene in enumerate(job.get("visualStoryboard", []), start=1)
            if isinstance(scene, dict)
        ],
    }
    try:
        result = router.complete_json(
            system_prompt=VISUAL_ASSET_PLANNER_INSTRUCTIONS,
            user_prompt=json.dumps(payload, ensure_ascii=False),
            operation=f"visual_asset_planner:{job.get('id')}",
            chain="default",
        )
    finally:
        router.close()
    if not isinstance(result, dict) or not isinstance(result.get("assets"), list):
        return []
    return [item for item in result["assets"] if isinstance(item, dict)]


def _normalise_asset_plan(raw_assets: list[dict[str, Any]], job: dict[str, Any], maximum: int) -> list[dict[str, Any]]:
    eligible = _eligible_scenes(job)
    normalized: list[dict[str, Any]] = []
    used_scenes: set[int] = set()
    for raw in raw_assets:
        if raw.get("useGeneratedAsset") is not True:
            continue
        scene_index = _positive_int(raw.get("sceneIndex"), 0)
        if scene_index not in eligible or scene_index in used_scenes:
            continue
        role = str(raw.get("assetRole") or "").strip()
        prompt = str(raw.get("prompt") or "").strip()
        if role not in ALLOWED_ROLES or not _asset_prompt_is_safe(prompt):
            continue
        normalized.append({
            "sceneIndex": scene_index,
            "assetRole": role,
            "prompt": prompt,
            "reason": str(raw.get("reason") or "").strip()[:240],
        })
        used_scenes.add(scene_index)
        if len(normalized) >= maximum:
            break
    return normalized


def _validate_and_write_image(content: bytes, preferred_extension: str, destination_stem: Path) -> tuple[Path, dict[str, Any]]:
    if len(content) < 2048 or len(content) > 18 * 1024 * 1024:
        raise ValueError(f"generated asset has invalid byte size: {len(content)}")
    with Image.open(io.BytesIO(content)) as image:
        image.verify()
    with Image.open(io.BytesIO(content)) as image:
        width, height = image.size
        fmt = (image.format or preferred_extension or "png").lower()
    if width < 512 or height < 512:
        raise ValueError(f"generated asset is too small: {width}x{height}")
    extension = {"jpeg": "jpg", "jpg": "jpg", "png": "png", "webp": "webp", "gif": "gif"}.get(fmt, preferred_extension.lower())
    if extension not in {"png", "jpg", "webp", "gif"}:
        raise ValueError(f"generated asset has unsupported format: {fmt}")
    path = destination_stem.with_suffix(f".{extension}")
    path.write_bytes(content)
    return path, {"width": width, "height": height, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def add_generated_visual_assets(job: dict[str, Any], puzzle: dict[str, Any], stage_dir: Path, public_dir: Path) -> dict[str, Any]:
    """Plan and obtain optional assets; always preserve the deterministic board fallback."""
    maximum = _positive_int(os.getenv("VISUAL_ASSET_MAX_PER_VIDEO"), MAX_ASSETS_DEFAULT)
    client = VisualAssetClient.from_environment()
    metadata: dict[str, Any] = {"enabled": client is not None, "planner": "ai_router", "assets": [], "failures": []}
    job["visualAssets"] = metadata
    if client is None or maximum == 0 or not job.get("visualStoryboard"):
        metadata["reason"] = "disabled_or_missing_service_credentials"
        return job

    try:
        raw_assets = _plan_assets_with_ai(job, puzzle)
    except Exception as exc:
        metadata["failures"].append({"stage": "planning", "error": str(exc)[:500]})
        return job
    plans = _normalise_asset_plan(raw_assets, job, maximum)
    metadata["plans"] = [{key: value for key, value in plan.items() if key != "prompt"} for plan in plans]
    if not plans:
        metadata["reason"] = "ai_planner_selected_no_asset"
        return job

    public_asset_dir = public_dir / "assets"
    stage_asset_dir = stage_dir / "assets"
    public_asset_dir.mkdir(parents=True, exist_ok=True)
    stage_asset_dir.mkdir(parents=True, exist_ok=True)
    scenes = {int(scene.get("index", index)): scene for index, scene in enumerate(job.get("visualStoryboard", []), start=1) if isinstance(scene, dict)}

    for ordinal, plan in enumerate(plans, start=1):
        scene_index = plan["sceneIndex"]
        try:
            content, extension, service_meta = client.generate(plan["prompt"])
            stem = public_asset_dir / f"scene-{scene_index:02d}-{ordinal:02d}"
            public_path, image_meta = _validate_and_write_image(content, extension, stem)
            stage_path = stage_asset_dir / public_path.name
            stage_path.write_bytes(content)
            public_src = f"generated/{job['id']}/assets/{public_path.name}"
            asset = {
                "sceneIndex": scene_index,
                "assetRole": plan["assetRole"],
                "src": public_src,
                "prompt": plan["prompt"],
                "reason": plan["reason"],
                "service": {key: service_meta.get(key) for key in ("service_job_id", "extension", "mime_type", "bytes")},
                **image_meta,
            }
            metadata["assets"].append(asset)
            if scene_index in scenes:
                scenes[scene_index]["generatedAsset"] = {"src": public_src, "assetRole": plan["assetRole"]}
        except Exception as exc:
            metadata["failures"].append({"sceneIndex": scene_index, "stage": "generation", "error": str(exc)[:500]})

    if not metadata["assets"]:
        metadata["reason"] = "all_requested_assets_failed"
    return job
