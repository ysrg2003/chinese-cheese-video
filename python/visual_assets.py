"""Optional AI-generated visual assets for the autonomous Xiangqi video pipeline.

The canonical Remotion board is never replaced. Assets are generated only for selected
non-move scenes, stored per job, and rendered as a restrained editorial backdrop.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from PIL import Image

from ai_router_bridge import load_router
from reference_render import render_reference_scene


ASSET_API_DEFAULT = "https://yousefsg-chatgpt-api.hf.space"
MAX_ASSETS_DEFAULT = 2
POLL_SECONDS = 3.0
ROOT = Path(__file__).resolve().parents[1]
REFERENCE_FPS = 30
BOARD_X, BOARD_Y, CELL = 70, 390, 104
EDITABLE_SCENE_KINDS = {"river_palaces", "generals_goal", "rule_focus", "history_timeline", "cultural_heritage"}
ALLOWED_ROLES = {"editorial_backdrop", "historical_inset", "cultural_inset", "concept_inset"}
INELIGIBLE_KINDS = {"move_path", "attack_line", "capture_sequence", "cannon_screen", "defense_zone", "threat_marker"}

VISUAL_ASSET_PLANNER_INSTRUCTIONS = """
You are the reference-edit planner for an autonomous Xiangqi educational video. Return valid JSON only:
{"assets":[{"sceneIndex":1,"useGeneratedAsset":true,"assetRole":"concept_inset","editPrompt":"English localized edit instruction","reason":"short factual reason"}]}

Study the supplied narration, semantic visual plan, and canonical board storyboard. Select zero, one, or two non-move scenes only when a localized material or color edit would make the exact existing scene clearer and the scene's visualPlan explicitly permits a reference edit. The pipeline will upload the original Remotion scene and an exact transparent mask. Never request a new composition, a new board, a realistic replacement scene, or a full-image regeneration.

The reference image is authoritative. The editPrompt must describe only what to add inside the masked region and must explicitly preserve all unmasked pixels, board lines, piece positions, labels, perspective, and layout. For the river scene, request a flat cool-blue flowing-water texture inside the existing rectangular river band; never request a scenic landscape or a new river surrounding a board. For palace or setup scenes, request only a subtle material or color treatment inside the existing region. Exact moves, coordinates, captures, tactical lines, and piece geometry stay deterministic Remotion overlays and must not be edited.

Every editPrompt must be English, concise, and include: edit only the transparent masked region; preserve everything outside it exactly; no new text, numerals, logos, watermarks, people, hands, chessboard, Xiangqi grid, or changed pieces. Do not invent historical facts.

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

    def _poll_and_download(self, job_id: str, status_path: str, download_path: str) -> tuple[bytes, str, dict[str, Any]]:
        deadline = time.monotonic() + self.timeout_seconds
        last_payload: dict[str, Any] = {}
        while time.monotonic() < deadline:
            response = requests.get(f"{self.base_url}{status_path}", headers={"Authorization": f"Bearer {self.api_key}"}, timeout=30)
            response.raise_for_status()
            last_payload = response.json()
            status = str(last_payload.get("status") or "")
            if status == "done":
                downloaded = requests.get(f"{self.base_url}{download_path}", headers={"Authorization": f"Bearer {self.api_key}"}, timeout=120)
                downloaded.raise_for_status()
                return downloaded.content, str(last_payload.get("extension") or "png"), last_payload
            if status == "error":
                raise RuntimeError(str(last_payload.get("error") or "visual asset job failed"))
            time.sleep(POLL_SECONDS)
        raise TimeoutError(f"visual asset job timed out after {self.timeout_seconds}s: {job_id}")

    def generate(self, prompt: str) -> tuple[bytes, str, dict[str, Any]]:
        created = requests.post(f"{self.base_url}/v1/visual-assets/jobs", headers=self.headers, json={"prompt": prompt}, timeout=45)
        created.raise_for_status()
        job_id = str(created.json().get("job_id") or "")
        if not job_id:
            raise RuntimeError("visual asset service did not return job_id")
        body, extension, metadata = self._poll_and_download(job_id, f"/v1/visual-assets/jobs/{job_id}", f"/v1/visual-assets/jobs/{job_id}/download")
        return body, extension, {"service_job_id": job_id, **metadata}

    def reference_edit(self, reference_path: Path, mask_path: Path | None, edit_prompt: str) -> tuple[bytes, str, dict[str, Any]]:
        files: dict[str, tuple[str, bytes, str]] = {
            "reference": (reference_path.name, reference_path.read_bytes(), "image/png"),
        }
        if mask_path:
            files["mask"] = (mask_path.name, mask_path.read_bytes(), "image/png")
        created = requests.post(
            f"{self.base_url}/v1/visual-assets/reference-edits",
            headers={"Authorization": f"Bearer {self.api_key}"},
            files=files,
            data={"prompt": edit_prompt, "preserve_outside_mask": "true"},
            timeout=60,
        )
        created.raise_for_status()
        job_id = str(created.json().get("job_id") or "")
        if not job_id:
            raise RuntimeError("reference edit service did not return job_id")
        body, extension, metadata = self._poll_and_download(job_id, f"/v1/visual-assets/reference-edits/{job_id}", f"/v1/visual-assets/reference-edits/{job_id}/download")
        return body, extension, {"service_job_id": job_id, "mode": "reference_edit", **metadata}


def _positive_int(value: Any, default: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _asset_prompt_is_safe(value: Any) -> bool:
    prompt = str(value or "").strip()
    lowered = prompt.lower()
    forbidden = ("new scene", "new board", "full image", "from scratch", "replace the board", "arabic")
    return 40 <= len(prompt) <= 2500 and not any(term in lowered for term in forbidden) and "preserve" in lowered and "masked" in lowered


def _eligible_scenes(job: dict[str, Any]) -> dict[int, dict[str, Any]]:
    eligible: dict[int, dict[str, Any]] = {}
    for index, scene in enumerate(job.get("visualStoryboard", []), start=1):
        if not isinstance(scene, dict):
            continue
        scene_index = _positive_int(scene.get("index"), index)
        visual_kind = str(scene.get("visualKind") or "")
        visual_plan = scene.get("visualPlan") if isinstance(scene.get("visualPlan"), dict) else {}
        if scene.get("movePly") is not None or visual_kind in INELIGIBLE_KINDS or str(visual_plan.get("mode") or "board_overlay") != "reference_edit":
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
        "reference_contract": {
            "reference": "An exact Remotion PNG of the canonical scene will be uploaded.",
            "mask": "A same-size transparent PNG will mark the only editable region.",
            "allowed_scene_kinds": sorted(EDITABLE_SCENE_KINDS),
        },
        "scenes": [
            {
                "sceneIndex": scene.get("index", index),
                "movePly": scene.get("movePly"),
                "visualKind": scene.get("visualKind"),
                "narration": scene.get("narration"),
                "visualInstruction": scene.get("visualInstruction"),
                "semanticTags": scene.get("semanticTags") or [],
                "visualPlan": scene.get("visualPlan") or {},
                "eligibleForReferenceEdit": str(scene.get("visualKind") or "") in EDITABLE_SCENE_KINDS and scene.get("movePly") is None and str((scene.get("visualPlan") or {}).get("mode") or "board_overlay") == "reference_edit",
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
        edit_prompt = str(raw.get("editPrompt") or raw.get("prompt") or "").strip()
        if role not in ALLOWED_ROLES or not _asset_prompt_is_safe(edit_prompt):
            continue
        normalized.append({
            "sceneIndex": scene_index,
            "assetRole": role,
            "editPrompt": edit_prompt,
            "reason": str(raw.get("reason") or "").strip()[:240],
        })
        used_scenes.add(scene_index)
        if len(normalized) >= maximum:
            break
    return normalized


def _safe_reference_label(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return path.name


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


def validate_and_annotate_visual_assets(job: dict[str, Any], public_root: Path | None = None) -> list[str]:
    """Validate every attached visual asset and record its real render window."""
    public_root = public_root or (ROOT / "public")
    metadata = job.get("visualAssets") if isinstance(job.get("visualAssets"), dict) else {}
    assets = metadata.get("assets") if isinstance(metadata.get("assets"), list) else []
    scenes = {int(scene.get("index")): scene for scene in job.get("visualStoryboard", []) if isinstance(scene, dict) and scene.get("index") is not None}
    segments = [segment for segment in job.get("narrationSegments", []) if isinstance(segment, dict)]
    errors: list[str] = []
    manifest: list[dict[str, Any]] = []
    for ordinal, asset in enumerate(assets, start=1):
        if not isinstance(asset, dict):
            errors.append(f"asset_{ordinal} is not an object")
            continue
        src = str(asset.get("src") or "")
        scene_index = _positive_int(asset.get("sceneIndex"), 0)
        if not src.startswith("generated/") or ".." in src:
            errors.append(f"asset_{ordinal} has unsafe source")
            continue
        path = public_root / src
        if not path.is_file():
            errors.append(f"asset_{ordinal} missing file: {src}")
            continue
        try:
            content = path.read_bytes()
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
            with Image.open(io.BytesIO(content)) as image:
                width, height = image.size
        except Exception as exc:
            errors.append(f"asset_{ordinal} unreadable: {src}: {exc}")
            continue
        actual_hash = hashlib.sha256(content).hexdigest()
        if asset.get("sha256") and str(asset["sha256"]) != actual_hash:
            errors.append(f"asset_{ordinal} sha256 mismatch: {src}")
        scene = scenes.get(scene_index)
        if scene is None or not isinstance(scene.get("generatedAsset"), dict) or scene["generatedAsset"].get("src") != src:
            errors.append(f"asset_{ordinal} is not attached to scene_{scene_index}")
        matching = [segment for segment in segments if int(segment.get("sceneId", -1)) == scene_index and segment.get("startSec") is not None and segment.get("endSec") is not None]
        if not matching:
            errors.append(f"asset_{ordinal} has no timed segment for scene_{scene_index}")
            continue
        start = min(float(segment.get("startSec", 0.0)) for segment in matching)
        end = max(float(segment.get("endSec", start)) for segment in matching)
        if end - start < 0.75:
            errors.append(f"asset_{ordinal} scene_{scene_index} visibility window is too short: {end - start:.2f}s")
        asset["width"] = width
        asset["height"] = height
        asset["sha256"] = actual_hash
        asset["visibleStartSec"] = start
        asset["visibleEndSec"] = end
        asset["visibilityDurationSec"] = round(end - start, 3)
        manifest.append({key: asset.get(key) for key in ("sceneIndex", "src", "assetRole", "width", "height", "sha256", "visibleStartSec", "visibleEndSec", "visibilityDurationSec")})
    metadata["manifest"] = manifest
    metadata["contract"] = "durable_file_hash_scene_timing_v1"
    job["visualAssets"] = metadata
    return errors


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
    metadata["plans"] = [{key: value for key, value in plan.items() if key != "editPrompt"} for plan in plans]
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
            scene = scenes[scene_index]
            reference_path, mask_path = render_reference_scene(job, scene, stage_dir)
            content, extension, service_meta = client.reference_edit(reference_path, mask_path, plan["editPrompt"])
            stem = public_asset_dir / f"scene-{scene_index:02d}-{ordinal:02d}"
            public_path, image_meta = _validate_and_write_image(content, extension, stem)
            stage_path = stage_asset_dir / public_path.name
            stage_path.write_bytes(content)
            public_src = f"generated/{job['id']}/assets/{public_path.name}"
            asset = {
                "sceneIndex": scene_index,
                "assetRole": plan["assetRole"],
                "src": public_src,
                "editPrompt": plan["editPrompt"],
                "reason": plan["reason"],
                "reference": _safe_reference_label(reference_path),
                "mask": _safe_reference_label(mask_path),
                "service": {key: service_meta.get(key) for key in ("service_job_id", "extension", "mime_type", "bytes", "mode")},
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
