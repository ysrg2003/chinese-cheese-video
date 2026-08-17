"""Fail-closed render-time visual QA for the Xiangqi production pipeline.

This module deliberately runs after Remotion has produced the MP4 and before any
thumbnail or YouTube side effect. It verifies the artifact that will actually be
published, not only the storyboard JSON or a later local proof frame.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat


FRAME_WIDTH = 1080
FRAME_HEIGHT = 1920
SIDE_STRIP = (0, 450, 64, 1450)


def _expected_frame_size(job: dict[str, Any]) -> tuple[int, int]:
    """Return the same semantic format dimensions enforced by Remotion."""
    declared = (int(job.get("renderedWidth") or 0), int(job.get("renderedHeight") or 0))
    if declared[0] > 0 and declared[1] > 0:
        return declared
    return (1080, 1920) if str(job.get("format") or "lesson").strip().lower() == "short" else (1920, 1080)


def _probe_duration(video_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nk=1",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def _sample_time(start: float, end: float, duration: float) -> float:
    # Avoid both transition edges; this samples the scene while its visual
    # treatment is fully visible and remains inside the real MP4 duration.
    window = max(0.0, end - start)
    offset = min(0.7, max(0.18, window * 0.28))
    return max(0.0, min(duration - 0.04, start + offset))


def _extract_frame(video_path: Path, second: float, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{second:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _fingerprint(image: Image.Image) -> str:
    small = image.convert("RGB").resize((32, 32), Image.Resampling.BILINEAR)
    return hashlib.sha256(small.tobytes()).hexdigest()[:20]


def _fit_cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_width, target_height = size
    source = image.convert("RGB")
    scale = max(target_width / source.width, target_height / source.height)
    resized = source.resize((max(target_width, round(source.width * scale)), max(target_height, round(source.height * scale))), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_width) // 2)
    top = max(0, (resized.height - target_height) // 2)
    return resized.crop((left, top, left + target_width, top + target_height))


def _asset_side_strip_similarity(frame: Image.Image, asset: Image.Image, frame_size: tuple[int, int]) -> float:
    """Return a 0..1 similarity for the unoccluded side strip.

    GeneratedVisualAsset is a full-frame backdrop below the board and semantic
    overlays. The left strip is outside the board and therefore remains a stable
    pixel witness that the asset was actually composited into the MP4.
    """
    frame_rgb = frame.convert("RGB").resize(frame_size, Image.Resampling.BILINEAR)
    asset_rgb = _fit_cover(asset, frame_size)
    strip = SIDE_STRIP if frame_size[0] < frame_size[1] else (1080, 120, 1840, 960)
    frame_crop = frame_rgb.crop(strip).resize((64, 64), Image.Resampling.BILINEAR)
    asset_crop = asset_rgb.crop(strip).resize((64, 64), Image.Resampling.BILINEAR)
    difference = ImageChops.difference(frame_crop, asset_crop)
    mean_difference = sum(ImageStat.Stat(difference).mean) / 3.0
    return max(0.0, min(1.0, 1.0 - mean_difference / 255.0))


def _scene_index_map(job: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        int(scene.get("index")): scene
        for scene in job.get("visualStoryboard", [])
        if isinstance(scene, dict) and scene.get("index") is not None
    }


def _segment_records(job: dict[str, Any]) -> list[dict[str, Any]]:
    return [segment for segment in job.get("narrationSegments", []) if isinstance(segment, dict)]


def verify_rendered_visuals(
    job: dict[str, Any],
    video_path: Path,
    qa_dir: Path,
    public_root: Path,
) -> dict[str, Any]:
    """Verify every narrated segment against frames extracted from the final MP4."""
    errors: list[str] = []
    qa_dir.mkdir(parents=True, exist_ok=True)
    if not video_path.is_file() or video_path.stat().st_size < 4096:
        return {"ok": False, "errors": [f"rendered MP4 is missing or too small: {video_path}"], "scenes": []}

    try:
        duration = _probe_duration(video_path)
    except Exception as exc:
        return {"ok": False, "errors": [f"cannot probe rendered MP4 duration: {exc}"], "scenes": []}

    expected_frame_size = _expected_frame_size(job)
    scenes = _scene_index_map(job)
    segments = _segment_records(job)
    if not segments:
        errors.append("rendered job has no narrationSegments")
    records: list[dict[str, Any]] = []
    fingerprints: dict[int, str] = {}
    for ordinal, segment in enumerate(segments, start=1):
        scene_id = int(segment.get("sceneId", ordinal))
        scene = scenes.get(scene_id)
        start = float(segment.get("startSec", 0.0) or 0.0)
        end = float(segment.get("endSec", start) or start)
        if end <= start:
            errors.append(f"scene_{scene_id} has no positive visual window")
            continue
        if start < -0.02 or end > duration + 0.08:
            errors.append(f"scene_{scene_id} window {start:.3f}-{end:.3f}s exceeds MP4 duration {duration:.3f}s")
            continue
        if not scene:
            errors.append(f"scene_{scene_id} has no visualStoryboard entry")
            continue
        plan = scene.get("visualPlan") if isinstance(scene.get("visualPlan"), dict) else {}
        primitives = plan.get("primitives") if isinstance(plan.get("primitives"), list) else []
        if not str(plan.get("focus") or "").strip() or not primitives:
            errors.append(f"scene_{scene_id} has no actionable visualPlan in production job")
        frame_second = _sample_time(start, end, duration)
        frame_path = qa_dir / f"scene-{scene_id:02d}.jpg"
        try:
            _extract_frame(video_path, frame_second, frame_path)
            with Image.open(frame_path) as image:
                frame = image.convert("RGB")
                if frame.size != expected_frame_size:
                    errors.append(f"scene_{scene_id} frame has unexpected size {frame.size}; expected {expected_frame_size}")
                if sum(ImageStat.Stat(frame).mean) < 12.0:
                    errors.append(f"scene_{scene_id} sampled frame is effectively blank")
                fingerprint = _fingerprint(frame)
        except Exception as exc:
            errors.append(f"scene_{scene_id} frame extraction failed: {exc}")
            fingerprint = ""
        fingerprints[scene_id] = fingerprint
        record: dict[str, Any] = {
            "sceneId": scene_id,
            "startSec": start,
            "endSec": end,
            "sampleSec": frame_second,
            "frame": str(frame_path),
            "segmentKind": segment.get("kind"),
            "visualKind": scene.get("visualKind"),
            "primitives": [str(value) for value in primitives],
            "fingerprint": fingerprint,
            "asset": None,
        }

        generated_asset = scene.get("generatedAsset")
        if generated_asset is not None:
            if not isinstance(generated_asset, dict):
                errors.append(f"scene_{scene_id} generatedAsset is not an object")
            else:
                src = str(generated_asset.get("src") or "")
                asset_path = public_root / src if src.startswith("generated/") and ".." not in src else None
                if asset_path is None or not asset_path.is_file():
                    errors.append(f"scene_{scene_id} generatedAsset is not present at render time: {src}")
                else:
                    try:
                        with Image.open(asset_path) as asset_image, Image.open(frame_path) as frame_image:
                            similarity = _asset_side_strip_similarity(frame_image, asset_image, expected_frame_size)
                        record["asset"] = {"src": src, "sideStripSimilarity": round(similarity, 4)}
                        if similarity < 0.55:
                            errors.append(f"scene_{scene_id} generatedAsset does not appear in rendered side-strip witness: similarity={similarity:.3f}")
                    except Exception as exc:
                        errors.append(f"scene_{scene_id} generatedAsset visibility check failed: {exc}")

        records.append(record)

    # A static sentence must create a visible change. Identical fingerprints for
    # adjacent static scenes mean the storyboard was metadata-only or rendered as
    # the same generic frame, which is the exact failure this gate prevents.
    for previous, current in zip(records, records[1:]):
        previous_is_static = previous.get("segmentKind") != "move"
        current_is_static = current.get("segmentKind") != "move"
        if previous_is_static and current_is_static and previous.get("fingerprint") and previous.get("fingerprint") == current.get("fingerprint"):
            if previous.get("primitives") != current.get("primitives"):
                errors.append(f"adjacent static scenes {previous['sceneId']} and {current['sceneId']} rendered identically despite different visual plans")

    result = {
        "contract": "rendered_mp4_scene_asset_witness_v1",
        "ok": not errors,
        "errors": errors,
        "durationSec": round(duration, 3),
        "scenes": records,
    }
    (qa_dir / "visual-qa.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Fail-closed QA for a rendered Xiangqi MP4")
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--qa-dir", required=True, type=Path)
    parser.add_argument("--public-root", required=True, type=Path)
    args = parser.parse_args()
    job = json.loads(args.job.read_text(encoding="utf-8"))
    result = verify_rendered_visuals(job, args.video, args.qa_dir, args.public_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
