"""Render canonical Remotion scene references and exact editable masks."""

from __future__ import annotations

import json
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_WIDTH = 1080
REFERENCE_HEIGHT = 1920
REFERENCE_FPS = 30
BOARD_X, BOARD_Y, CELL = 70, 390, 104


def _mask_for_scene(scene_kind: str) -> Image.Image:
    # Opaque means preserve. Transparent means the editor may change the region.
    mask = Image.new("RGBA", (REFERENCE_WIDTH, REFERENCE_HEIGHT), (255, 255, 255, 255))
    draw = ImageDraw.Draw(mask)
    if scene_kind == "river_palaces":
        draw.rectangle(
            (BOARD_X + 28, BOARD_Y + 28 + 4 * CELL, BOARD_X + 28 + 8 * CELL, BOARD_Y + 28 + 5 * CELL),
            fill=(0, 0, 0, 0),
        )
    elif scene_kind in {"generals_goal", "rule_focus"}:
        for top in (BOARD_Y + 28, BOARD_Y + 28 + 7 * CELL):
            draw.rectangle((BOARD_X + 28, top, BOARD_X + 28 + 2 * CELL, top + 2 * CELL), fill=(0, 0, 0, 0))
    else:
        raise ValueError(f"scene kind does not have a safe localized mask: {scene_kind}")
    return mask


def render_reference_scene(job: dict[str, Any], scene: dict[str, Any], stage_dir: Path) -> tuple[Path, Path]:
    scene_kind = str(scene.get("visualKind") or "")
    reference_dir = stage_dir / "references"
    reference_dir.mkdir(parents=True, exist_ok=True)
    reference_path = reference_dir / f"scene-{int(scene.get('index', 1)):02d}.png"
    mask_path = reference_dir / f"scene-{int(scene.get('index', 1)):02d}.mask.png"

    reference_job = deepcopy(job)
    reference_job["referenceMode"] = True
    reference_job["audioSrc"] = ""
    reference_job["moves"] = []
    reference_job["durationInSeconds"] = 2.0
    reference_job["narrationSegments"] = [{
        "kind": "intro",
        "text": str(scene.get("narration") or ""),
        "captionText": "",
        "sceneId": 1,
        "visualKind": scene_kind,
        "headline": "",
        "visualInstruction": scene.get("visualInstruction") or "",
        "startSec": 0.0,
        "endSec": 2.0,
    }]
    reference_job["visualStoryboard"] = [{
        **scene,
        "index": 1,
        "segmentIndex": 1,
        "generatedAsset": None,
    }]
    props_path = reference_dir / f"scene-{int(scene.get('index', 1)):02d}.job.json"
    props_path.write_text(json.dumps(reference_job, ensure_ascii=False), encoding="utf-8")
    frame = int(0.8 * REFERENCE_FPS)
    command = [
        "npx", "remotion", "still", "src/index.tsx", "XiangqiComposition",
        str(reference_path), f"--props={props_path}", f"--frame={frame}",
        "--image-format=png", "--log=error",
    ]
    subprocess.run(command, cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    _mask_for_scene(scene_kind).save(mask_path, format="PNG")
    return reference_path, mask_path
