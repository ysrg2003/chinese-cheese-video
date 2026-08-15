from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from ai_router_bridge import load_router
from visual_director import ALL_VISUAL_KINDS, SUPPORTED_BOARD_PRIMITIVES
from xiangqi_rules import validate_move_sequence
from xiangqi_claims import CLAIM_TYPES, suspicious_claim_language, verify_claims


CRITIC_CONTRACT = "prepublish_creative_critic_v1"
DEFAULT_MAX_ITERATIONS = 2
MIN_APPROVAL_SCORE = 82

CREATIVE_CRITIC_INSTRUCTIONS = """
You are the senior pre-publication reviewer for an autonomous English-primary Xiangqi education channel.
Return valid JSON only with this schema:
{
  "decision": "approve" | "repair" | "reject",
  "score": 0,
  "summary": "one concise review summary",
  "checks": {
    "legal_accuracy": {"ok": true, "reason": "..."},
    "spoken_visual_alignment": {"ok": true, "reason": "..."},
    "teaching_value": {"ok": true, "reason": "..."},
    "beat_distinctness": {"ok": true, "reason": "..."},
    "asset_integration": {"ok": true, "reason": "..."}
  },
  "scene_repairs": [
    {
      "sceneId": 1,
      "reason": "specific defect",
      "headline": "2 to 6 words",
      "visualInstruction": "one concrete renderer-supported visual action",
      "visualKind": "permitted visual kind",
      "semanticTags": ["specific", "teaching", "tags"],
      "visualPlan": {"mode": "board_overlay", "focus": "what must be visible", "primitives": ["supported primitive"]}
    }
  ]
}

Review the exact supplied narration, each narration segment, its scene, and the final visual QA evidence when the review_phase is final_artifact. During storyboard_preflight, review the planned visual treatment and do not reject merely because a rendered frame does not exist yet.
Ask whether a viewer can immediately see the idea being spoken, whether the scene teaches rather than decorates,
and whether every move has distinct action, reply, effect, and constraint treatment. Do not invent a move,
coordinate, piece position, capture, rule, historical claim, or visual primitive. Never change narration,
caption text, move coordinates, move phase, FEN, or piece geometry. If a scene needs improvement, request a
small scene-only repair. Approve only when the video is publishable as an educational Xiangqi lesson.
Never use Arabic. English is required for English jobs and Chinese is required for Chinese jobs. Treat claimProof and researchBundle as mandatory evidence. Never approve a causal rule statement when the mechanical claim proof is absent or false.
""".strip()


def _truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _require_ai() -> bool:
    return _truthy(os.getenv("PREPUBLISH_CRITIC_REQUIRED"), False)


def _max_iterations() -> int:
    try:
        return max(0, min(4, int(os.getenv("PREPUBLISH_CRITIC_MAX_ITERATIONS", str(DEFAULT_MAX_ITERATIONS)))))
    except ValueError:
        return DEFAULT_MAX_ITERATIONS


def _scene_map(job: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        int(scene.get("index")): scene
        for scene in job.get("visualStoryboard", [])
        if isinstance(scene, dict) and scene.get("index") is not None
    }


def _segment_map(job: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = {}
    for ordinal, segment in enumerate(job.get("narrationSegments", []), start=1):
        if not isinstance(segment, dict):
            continue
        scene_id = int(segment.get("sceneId", ordinal))
        result.setdefault(scene_id, []).append(segment)
    return result


def _frame_evidence(visual_qa: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(visual_qa, dict):
        return {"available": False, "ok": False, "errors": ["final render QA has not run"]}
    records = []
    for scene in visual_qa.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        records.append({
            "sceneId": scene.get("sceneId"),
            "segmentKind": scene.get("segmentKind"),
            "visualKind": scene.get("visualKind"),
            "primitives": scene.get("primitives") or [],
            "sampleSec": scene.get("sampleSec"),
            "fingerprint": scene.get("fingerprint"),
            "asset": scene.get("asset"),
        })
    return {
        "available": True,
        "ok": visual_qa.get("ok") is True,
        "durationSec": visual_qa.get("durationSec"),
        "errors": list(visual_qa.get("errors") or []),
        "sceneEvidence": records,
    }


def _deterministic_review(job: dict[str, Any], visual_qa: dict[str, Any] | None, *, final_artifact: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    repairable: list[dict[str, Any]] = []
    language = str(job.get("language") or "en").lower()
    if language not in {"en", "zh"}:
        errors.append(f"unsupported language={language}")
    if any("\u0600" <= char <= "\u06ff" for char in json.dumps(job, ensure_ascii=False)):
        errors.append("Arabic content is present")

    try:
        legal = validate_move_sequence(str(job.get("fen") or ""), job.get("moves") or [])
    except Exception as exc:
        legal = {"ok": False, "errors": [f"legal validator failed: {exc}"]}
    if not legal.get("ok"):
        errors.extend([f"illegal move sequence: {error}" for error in legal.get("errors") or ["unknown legal error"]])
    claim_proof = job.get("claimProof") if isinstance(job.get("claimProof"), dict) else {}
    claims_by_ply = job.get("claimsByPly") if isinstance(job.get("claimsByPly"), dict) else {}
    if job.get("moves") and not claim_proof:
        errors.append("mechanical Xiangqi claim proof is missing")
    elif claim_proof and claim_proof.get("ok") is not True:
        errors.extend([f"claim proof failed: {error}" for error in claim_proof.get("errors") or ["claim proof is not ok"]])
    for move in job.get("moves") or []:
        try:
            ply = int(move.get("ply"))
        except (TypeError, ValueError):
            continue
        claims = claims_by_ply.get(str(ply), claims_by_ply.get(ply, []))
        if suspicious_claim_language(move) and not claims:
            errors.append(f"ply={ply} has causal language without structured claim")
        for claim in claims or []:
            if str(claim.get("claimType") or "") not in CLAIM_TYPES:
                errors.append(f"ply={ply} has unsupported claim type")

    scenes = _scene_map(job)
    segments = _segment_map(job)
    if not scenes:
        errors.append("visual storyboard is empty")
    if not segments:
        errors.append("narration segments are empty")
    if scenes and len(scenes) != len(segments):
        errors.append(f"scene/segment count mismatch: {len(scenes)} != {len(segments)}")

    for scene_id, scene in scenes.items():
        plan = scene.get("visualPlan") if isinstance(scene.get("visualPlan"), dict) else {}
        primitives = plan.get("primitives") if isinstance(plan.get("primitives"), list) else []
        if not str(scene.get("visualInstruction") or "").strip():
            errors.append(f"scene_{scene_id} has no concrete visual instruction")
        if not str(plan.get("focus") or "").strip() or not primitives:
            errors.append(f"scene_{scene_id} has no actionable visual plan")
        unknown = sorted({str(item) for item in primitives if str(item) not in SUPPORTED_BOARD_PRIMITIVES})
        if unknown:
            errors.append(f"scene_{scene_id} uses unsupported primitives={unknown}")
        scene_segments = segments.get(scene_id, [])
        if not scene_segments:
            errors.append(f"scene_{scene_id} has no narration segment")
        if scene.get("movePly") is not None and scene.get("generatedAsset") is not None:
            errors.append(f"scene_{scene_id} attaches generated asset to a move")
        move_ply = scene.get("movePly")
        move = next((item for item in job.get("moves") or [] if isinstance(item, dict) and item.get("ply") == move_ply), None)
        if isinstance(move, dict):
            claim_types = {str(claim.get("claimType") or "") for claim in move.get("claims") or [] if isinstance(claim, dict)}
            required_by_claim = {
                "horse_leg_block": "horse_leg",
                "horse_leg_open": "horse_leg",
                "elephant_eye_block": "elephant_eye",
                "elephant_eye_open": "elephant_eye",
                "river_limit": "river_limit",
                "cannon_screen": "cannon_screen",
            }
            planned = {str(item) for item in primitives}
            for claim_type, required_primitive in required_by_claim.items():
                if claim_type in claim_types and required_primitive not in planned:
                    errors.append(f"scene_{scene_id} claim {claim_type} lacks required primitive {required_primitive}")

    move_groups: dict[int, list[dict[str, Any]]] = {}
    for scene_id, scene_segments in segments.items():
        for segment in scene_segments:
            if segment.get("movePly") is not None:
                move_groups.setdefault(int(segment["movePly"]), []).append(segment)
    for ply, group in sorted(move_groups.items()):
        phases = {str(segment.get("movePhase") or "") for segment in group}
        required = {"action", "reply", "effect", "constraint"}
        if not required.issubset(phases):
            errors.append(f"movePly={ply} lacks required beat phases")
        total = sum(max(0.0, float(segment.get("endSec", 0.0)) - float(segment.get("startSec", 0.0))) for segment in group)
        action = sum(max(0.0, float(segment.get("endSec", 0.0)) - float(segment.get("startSec", 0.0))) for segment in group if segment.get("movePhase") == "action")
        if total and action / total > 0.42:
            errors.append(f"movePly={ply} action beat dominates teaching window")

    evidence = _frame_evidence(visual_qa)
    if final_artifact and visual_qa is None:
        errors.append("final render evidence is missing")
    elif final_artifact and visual_qa.get("ok") is not True:
        errors.extend([f"rendered visual QA: {error}" for error in visual_qa.get("errors") or ["visual QA failed"]])

    if errors:
        score = 0 if any("illegal" in error or "Arabic" in error for error in errors) else 45
        decision = "reject" if score == 0 or any("final render evidence" in error for error in errors) else "repair"
    else:
        score = 88
        decision = "approve"
    return {
        "contract": CRITIC_CONTRACT,
        "source": "deterministic_contract",
        "decision": decision,
        "score": score,
        "summary": "Deterministic pre-publication contract passed." if not errors else "Deterministic pre-publication contract found blocking issues.",
        "checks": {
            "legal_accuracy": {"ok": legal.get("ok") is True, "reason": "; ".join(legal.get("errors") or []) or "legal move sequence passed"},
            "spoken_visual_alignment": {"ok": not any("scene" in error or "visual" in error for error in errors), "reason": "Storyboard and visual plans are actionable." if not errors else "; ".join(errors[:3])},
            "teaching_value": {"ok": bool(job.get("narrationSegments")), "reason": "Narration segments are present." if job.get("narrationSegments") else "Narration segments are missing."},
            "beat_distinctness": {"ok": not any("beat" in error or "dominates" in error for error in errors), "reason": "Move beat contract passed." if not any("beat" in error or "dominates" in error for error in errors) else "; ".join(error for error in errors if "beat" in error or "dominates" in error)},
            "asset_integration": {"ok": all(record.get("asset") is not None for record in evidence.get("sceneEvidence", []) if record.get("asset") is not None), "reason": "Rendered asset evidence is consistent."},
        },
        "errors": errors,
        "scene_repairs": repairable,
        "evidence": evidence,
    }


def _critic_payload(job: dict[str, Any], puzzle: dict[str, Any], visual_qa: dict[str, Any] | None, deterministic: dict[str, Any]) -> dict[str, Any]:
    scenes = []
    for scene in job.get("visualStoryboard", []):
        if not isinstance(scene, dict):
            continue
        scenes.append({
            "sceneId": scene.get("index"),
            "movePly": scene.get("movePly"),
            "visualKind": scene.get("visualKind"),
            "headline": scene.get("headline"),
            "narration": scene.get("narration"),
            "visualInstruction": scene.get("visualInstruction"),
            "semanticTags": scene.get("semanticTags") or [],
            "visualPlan": scene.get("visualPlan") or {},
            "generatedAsset": scene.get("generatedAsset"),
        })
    return {
        "review_phase": "final_artifact" if visual_qa is not None else "storyboard_preflight",
        "language": job.get("language", "en"),
        "title": job.get("title"),
        "objective": job.get("objective") or puzzle.get("objective"),
        "fen": job.get("fen"),
        "moves": job.get("moves") or [],
        "narration": job.get("narration"),
        "segments": job.get("narrationSegments") or [],
        "scenes": scenes,
        "deterministicReview": deterministic,
        "renderEvidence": _frame_evidence(visual_qa),
        "claimProof": job.get("claimProof") or {},
        "researchBundle": job.get("researchBundle") or puzzle.get("researchBundle") or {},
    }


def _request_ai_review(job: dict[str, Any], puzzle: dict[str, Any], visual_qa: dict[str, Any] | None, deterministic: dict[str, Any]) -> dict[str, Any] | None:
    router = load_router()
    if router is None:
        return None
    try:
        response = router.complete_json(
            system_prompt=CREATIVE_CRITIC_INSTRUCTIONS,
            user_prompt=json.dumps(_critic_payload(job, puzzle, visual_qa, deterministic), ensure_ascii=False),
            operation=f"creative_critic:{job.get('id')}:{job.get('creativeReviewIteration', 0)}",
            chain="default",
        )
        return response if isinstance(response, dict) else None
    finally:
        router.close()


def _normalise_ai_review(raw: dict[str, Any], deterministic: dict[str, Any]) -> dict[str, Any]:
    decision = str(raw.get("decision") or "reject").strip().lower()
    if decision not in {"approve", "repair", "reject"}:
        decision = "reject"
    try:
        score = max(0, min(100, int(raw.get("score", 0))))
    except (TypeError, ValueError):
        score = 0
    repairs: list[dict[str, Any]] = []
    for repair in raw.get("scene_repairs") or []:
        if isinstance(repair, dict):
            repairs.append(dict(repair))
    result = {
        "contract": CRITIC_CONTRACT,
        "source": "ai_router",
        "decision": decision,
        "score": score,
        "summary": str(raw.get("summary") or "").strip()[:1000],
        "checks": raw.get("checks") if isinstance(raw.get("checks"), dict) else {},
        "scene_repairs": repairs,
        "deterministic": deterministic,
    }
    if deterministic.get("errors"):
        result["decision"] = "reject" if any("illegal" in error or "Arabic" in error for error in deterministic["errors"]) else "repair"
        result["score"] = min(result["score"], 79)
        result["errors"] = list(deterministic["errors"])
    return result


def _filter_unsafe_repairs(job: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    """Discard AI repair proposals that cannot pass the protected scene contract."""
    repairs = review.get("scene_repairs") or []
    deterministic = review.get("deterministic") if isinstance(review.get("deterministic"), dict) else {}
    if not repairs:
        if str(review.get("decision") or "").lower() == "repair" and not deterministic.get("errors"):
            review["decision"] = "approve"
            review["score"] = max(int(review.get("score") or 0), MIN_APPROVAL_SCORE)
            review["summary"] = "AI requested a repair without an actionable scene specification; deterministic contract passed, so no unsafe change was applied."
            review["discarded_unsafe_repairs"] = [{"errors": ["AI repair decision contained no scene_repairs"]}]
        return review
    scenes = _scene_map(job)
    safe: list[dict[str, Any]] = []
    discarded: list[dict[str, Any]] = []
    for repair in repairs:
        if not isinstance(repair, dict):
            discarded.append({"repair": repair, "errors": ["repair is not an object"]})
            continue
        try:
            scene_id = int(repair.get("sceneId"))
        except (TypeError, ValueError):
            discarded.append({"repair": repair, "errors": ["repair has no valid sceneId"]})
            continue
        scene = scenes.get(scene_id)
        if scene is None:
            discarded.append({"repair": repair, "errors": [f"repair references missing scene_{scene_id}"]})
            continue
        errors = _safe_scene_repair(deepcopy(scene), repair)
        if errors:
            discarded.append({"repair": repair, "errors": errors})
        else:
            safe.append(repair)
    review["scene_repairs"] = safe
    if discarded:
        review["discarded_unsafe_repairs"] = discarded
    if discarded and not safe and not deterministic.get("errors"):
        review["decision"] = "approve"
        review["score"] = max(int(review.get("score") or 0), MIN_APPROVAL_SCORE)
        review["summary"] = "AI repair proposals were discarded because they violated the protected visual contract; deterministic review passed."
    return review


def review_job(job: dict[str, Any], puzzle: dict[str, Any], visual_qa: dict[str, Any] | None = None, *, require_ai: bool | None = None, final_artifact: bool = False) -> dict[str, Any]:
    deterministic = _deterministic_review(job, visual_qa, final_artifact=final_artifact)
    use_ai = _require_ai() if require_ai is None else require_ai
    if use_ai:
        ai = _request_ai_review(job, puzzle, visual_qa, deterministic)
        if ai is None:
            return {
                "contract": CRITIC_CONTRACT,
                "source": "unavailable",
                "decision": "reject",
                "score": 0,
                "summary": "Required creative critic provider is unavailable.",
                "errors": ["PREPUBLISH_CRITIC_REQUIRED but AI router returned no review"],
                "scene_repairs": [],
                "deterministic": deterministic,
            }
        return _filter_unsafe_repairs(job, _normalise_ai_review(ai, deterministic))
    return deterministic


def _safe_scene_repair(scene: dict[str, Any], repair: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    forbidden = {"movePly", "movePhase", "narration", "caption", "captionText", "from", "to", "piece", "side", "fen", "moves", "generatedAsset"}
    if any(key in repair for key in forbidden):
        errors.append(f"scene_{scene.get('index')} repair attempted to change protected move/content fields")
        return errors
    if "visualKind" in repair and str(repair.get("visualKind")) not in ALL_VISUAL_KINDS:
        errors.append(f"scene_{scene.get('index')} repair uses unsupported visualKind")
    plan = repair.get("visualPlan")
    if plan is not None:
        if not isinstance(plan, dict) or str(plan.get("mode") or "") not in {"board_overlay", "reference_edit", "none"}:
            errors.append(f"scene_{scene.get('index')} repair has invalid visualPlan")
        elif str(plan.get("mode") or "") == "board_overlay":
            unknown = sorted({str(item) for item in plan.get("primitives") or [] if str(item) not in SUPPORTED_BOARD_PRIMITIVES})
            if not str(plan.get("focus") or "").strip() or not plan.get("primitives") or unknown:
                errors.append(f"scene_{scene.get('index')} repair has unsafe primitives or focus")
    if errors:
        return errors
    for key in ("headline", "visualInstruction", "visualKind", "semanticTags", "visualPlan"):
        if key in repair:
            scene[key] = deepcopy(repair[key])
    return errors


def sync_repaired_scenes(job: dict[str, Any]) -> None:
    scenes = _scene_map(job)
    for ordinal, segment in enumerate(job.get("narrationSegments", []), start=1):
        if not isinstance(segment, dict):
            continue
        scene = scenes.get(int(segment.get("sceneId", ordinal)))
        if scene is None:
            continue
        for key in ("visualKind", "headline", "visualInstruction", "semanticTags", "visualPlan", "generatedAsset"):
            if key in scene:
                segment[key] = deepcopy(scene[key])


def apply_repairs(job: dict[str, Any], review: dict[str, Any]) -> list[str]:
    scenes = _scene_map(job)
    errors: list[str] = []
    repairs = review.get("scene_repairs") or []
    if not repairs:
        return ["critic requested repair but supplied no scene_repairs"]
    for repair in repairs:
        if not isinstance(repair, dict):
            errors.append("critic supplied a non-object scene repair")
            continue
        try:
            scene_id = int(repair.get("sceneId"))
        except (TypeError, ValueError):
            errors.append("critic supplied a repair without a valid sceneId")
            continue
        scene = scenes.get(scene_id)
        if scene is None:
            errors.append(f"critic repair references missing scene_{scene_id}")
            continue
        errors.extend(_safe_scene_repair(scene, repair))
    if not errors:
        job["creativeReviewRepairCount"] = int(job.get("creativeReviewRepairCount") or 0) + len(repairs)
    return errors


def run_prepublication_review(job: dict[str, Any], puzzle: dict[str, Any], *, visual_qa: dict[str, Any] | None = None, final_artifact: bool = False) -> dict[str, Any]:
    """Run one review; the caller owns render/repair/re-render iteration."""
    iteration = int(job.get("creativeReviewIteration") or 0)
    job["creativeReviewIteration"] = iteration
    review = review_job(job, puzzle, visual_qa, final_artifact=final_artifact)
    review["iteration"] = iteration
    return review


def write_review(review: dict[str, Any], stage_dir: Path) -> None:
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / "creative-review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
