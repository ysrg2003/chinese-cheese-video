from __future__ import annotations

import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ai_router_bridge import load_router
from visual_director import ALL_VISUAL_KINDS, SUPPORTED_BOARD_PRIMITIVES

REPAIR_SCHEMA = "xiangqi_self_repair_v1"
DIAGNOSIS_SCHEMA = "xiangqi_self_diagnosis_v1"
ALLOWED_FAILURE_CLASSES = {
    "content_claim",
    "content_move",
    "content_schema",
    "visual_storyboard",
    "visual_asset",
    "tts_audio",
    "render",
    "research_grounding",
    "publication",
    "transient",
    "unknown",
}
ALLOWED_PATCH_TYPES = {"director_patch", "visual_scene_patch", "retry_stage", "no_safe_repair"}
ALLOWED_RESUME_STAGES = {"director", "storyboard", "visual_assets", "tts", "render", "publication"}
ALLOWED_MOVE_FIELDS = {"purpose", "opponentReply", "effect", "label", "claims"}
ALLOWED_TOP_LEVEL_FIELDS = {"title", "narration", "analysis_focus", "objective"}
FORBIDDEN_PATCH_KEYS = {
    "fen",
    "from",
    "to",
    "piece",
    "side",
    "youtube",
    "publication",
    "playlist",
    "privacy",
    "secrets",
    "disable_gate",
    "skip_validation",
    "skip_research",
}

DIAGNOSIS_INSTRUCTIONS = """
You are the Xiangqi Lab production failure diagnostician.
Return JSON only. Do not return Markdown, Arabic, code, or a patch.
Analyze the supplied evidence, identify the root cause, and classify whether a
bounded automatic repair is safe. Never recommend disabling a gate, changing
YouTube publication state, changing credentials, or editing source code.
Use one failure_class from the supplied schema and one affected_stage.
""".strip()

REPAIR_INSTRUCTIONS = """
You are the Xiangqi Lab self-repair planner.
Return JSON only. Do not return Markdown, Arabic, code, or text outside JSON.
Use the diagnosis and evidence to create the smallest safe repair plan.
A plan may patch only allowlisted director content fields, apply a protected
visual-scene repair, retry a transient stage, or declare no_safe_repair.
Never change FEN, coordinates, piece identity, side, YouTube metadata, privacy,
credentials, source code, workflow files, or any validation/research gate.
Every changed Xiangqi causal statement must have a structured mechanically
verifiable claim; otherwise use neutral legal wording and legal_move claims.
""".strip()


class SelfRepairError(RuntimeError):
    pass


def _json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded_text(value: Any, limit: int = 4000) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _contains_arabic(value: Any) -> bool:
    return any("\u0600" <= char <= "\u06ff" for char in str(value or ""))


def classify_failure(error_text: str, stage: str = "") -> str:
    value = f"{stage} {error_text}".lower()
    if any(token in value for token in ("youtube", "oauth", "invalid_grant", "quotaexceeded", "youtube publication")):
        return "publication"
    if any(token in value for token in ("research grounding", "grounding", "source timeout")):
        return "research_grounding"
    if any(token in value for token in ("claim", "causal", "legal-move", "illegal", "declared piece", "fen")):
        return "content_claim" if any(token in value for token in ("claim", "causal")) else "content_move"
    if any(token in value for token in ("storyboard", "visual plan", "beat")):
        return "visual_storyboard"
    if any(token in value for token in ("visual asset", "generated asset", "chatgpt_visual")):
        return "visual_asset"
    if any(token in value for token in ("tts", "edge-tts", "voice.mp3", "audio")):
        return "tts_audio"
    if any(token in value for token in ("remotion", "rendered", "render")):
        return "render"
    if any(token in value for token in ("timeout", "temporarily", "429", "500", "502", "503", "504", "connection reset")):
        return "transient"
    return "unknown"


def collect_failure_evidence(
    *,
    job_id: str,
    candidate_id: str,
    attempt: int,
    stage: str,
    error_text: str,
    candidate_payload: dict[str, Any],
    output_root: str | Path,
) -> dict[str, Any]:
    root = Path(output_root)
    job_dir = root / "jobs" / job_id
    files: list[dict[str, Any]] = []
    for path in sorted(job_dir.glob("**/*")) if job_dir.exists() else []:
        if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            files.append({"path": str(path.relative_to(root)), "size": path.stat().st_size, "sha256": _file_hash(path)})
        except OSError:
            continue
    review_context: dict[str, Any] = {}
    job_context: dict[str, Any] = {}
    review_path = job_dir / "creative-review.json"
    job_path = job_dir / "job.json"
    for path, target in ((review_path, "review_context"), (job_path, "job_context")):
        if path.exists():
            try:
                parsed = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    if target == "review_context":
                        review_context = {
                            "decision": parsed.get("decision"),
                            "checks": parsed.get("checks"),
                            "errors": parsed.get("errors"),
                            "discarded_unsafe_repairs": parsed.get("discarded_unsafe_repairs"),
                        }
                    else:
                        moves_by_ply = {str(move.get("ply")): move for move in parsed.get("moves", []) if isinstance(move, dict)}
                        job_context = {
                            "scenes": [
                                {
                                    "index": scene.get("index"),
                                    "movePly": scene.get("movePly"),
                                    "visualKind": scene.get("visualKind"),
                                    "visualPlan": scene.get("visualPlan"),
                                    "movePhase": next((segment.get("movePhase") for segment in parsed.get("narrationSegments", []) if isinstance(segment, dict) and segment.get("sceneId") == scene.get("index")), None),
                                    "move": moves_by_ply.get(str(scene.get("movePly"))),
                                }
                                for scene in parsed.get("visualStoryboard", []) if isinstance(scene, dict)
                            ]
                        }
            except (OSError, json.JSONDecodeError):
                continue
    evidence = {
        "schema": "xiangqi_failure_evidence_v1",
        "job_id": job_id,
        "candidate_id": candidate_id,
        "attempt": int(attempt),
        "stage": str(stage or "unknown"),
        "failure_class": classify_failure(error_text, stage),
        "error": _bounded_text(error_text, 8000),
        "candidate_payload": copy.deepcopy(candidate_payload),
        "review_context": review_context,
        "job_context": job_context,
        "files": files,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    evidence["evidence_sha256"] = _json_hash(evidence)
    return evidence


def _router_complete_json(system_prompt: str, user_payload: dict[str, Any], operation: str, router_factory: Callable[[], Any] | None = None) -> dict[str, Any] | None:
    router = (router_factory or load_router)()
    if router is None:
        return None
    try:
        response = router.complete_json(
            chain=os.getenv("AI_ROUTER_CHAIN", "default"),
            system_prompt=system_prompt,
            user_prompt=json.dumps(user_payload, ensure_ascii=False),
            operation=operation,
        )
        return response if isinstance(response, dict) else None
    finally:
        router.close()


def diagnose_failure(evidence: dict[str, Any], router_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    payload = {"schema": DIAGNOSIS_SCHEMA, "allowed_failure_classes": sorted(ALLOWED_FAILURE_CLASSES), "evidence": evidence}
    raw = _router_complete_json(DIAGNOSIS_INSTRUCTIONS, payload, f"self_repair:diagnose:{evidence.get('job_id')}:{evidence.get('attempt')}", router_factory)
    if raw is None:
        return {"schema": DIAGNOSIS_SCHEMA, "repairable": False, "failure_class": evidence.get("failure_class", "unknown"), "root_cause": "AI diagnosis provider unavailable", "affected_stage": evidence.get("stage", "unknown"), "source": "unavailable"}
    evidence_stage = str(evidence.get("stage") or "unknown")
    diagnosis = {
        "schema": DIAGNOSIS_SCHEMA,
        "repairable": bool(raw.get("repairable", False)),
        "failure_class": str(raw.get("failure_class") or evidence.get("failure_class") or "unknown"),
        "root_cause": _bounded_text(raw.get("root_cause"), 2000),
        "diagnosis": _bounded_text(raw.get("diagnosis"), 3000),
        "affected_stage": evidence_stage if evidence_stage in ALLOWED_RESUME_STAGES else str(raw.get("affected_stage") or "unknown"),
        "source": "ai_router",
    }
    if diagnosis["failure_class"] not in ALLOWED_FAILURE_CLASSES:
        diagnosis["failure_class"] = "unknown"
        diagnosis["repairable"] = False
    if diagnosis["affected_stage"] not in ALLOWED_RESUME_STAGES:
        diagnosis["affected_stage"] = evidence.get("stage") if evidence.get("stage") in ALLOWED_RESUME_STAGES else "director"
    diagnosis["diagnosis_sha256"] = _json_hash(diagnosis)
    return diagnosis


def _has_forbidden_key(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in FORBIDDEN_PATCH_KEYS:
                return str(key)
            found = _has_forbidden_key(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _has_forbidden_key(child)
            if found:
                return found
    return None


def validate_plan(plan: dict[str, Any], diagnosis: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if str(plan.get("schema") or "") != REPAIR_SCHEMA:
        errors.append("repair plan schema is invalid")
    if str(plan.get("disposition") or "") not in {"apply_patch", "retry", "quarantine"}:
        errors.append("repair plan disposition is invalid")
    failure_class = str(plan.get("failure_class") or "unknown")
    if failure_class not in ALLOWED_FAILURE_CLASSES:
        errors.append("repair plan failure_class is invalid")
    if diagnosis.get("failure_class") and failure_class != str(diagnosis.get("failure_class")):
        errors.append("repair plan failure_class does not match diagnosis")
    patch_type = str(plan.get("patch_type") or "no_safe_repair")
    if patch_type not in ALLOWED_PATCH_TYPES:
        errors.append("repair plan patch_type is invalid")
    disposition = str(plan.get("disposition") or "")
    if patch_type in {"director_patch", "visual_scene_patch"} and disposition != "apply_patch":
        errors.append("content or visual patches require disposition=apply_patch")
    if patch_type == "retry_stage" and disposition not in {"retry", "apply_patch"}:
        errors.append("retry_stage requires a retry disposition")
    resume_stage = str(plan.get("resume_stage") or diagnosis.get("affected_stage") or "director")
    if resume_stage not in ALLOWED_RESUME_STAGES:
        errors.append("repair plan resume_stage is invalid")
    if _contains_arabic(plan):
        errors.append("repair plan contains Arabic text")
    forbidden = _has_forbidden_key(plan.get("patch"))
    if forbidden:
        errors.append(f"repair plan contains forbidden key={forbidden}")
    if patch_type in {"director_patch", "visual_scene_patch"} and not isinstance(plan.get("patch"), dict):
        errors.append("patch object is required")
    if patch_type == "visual_scene_patch":
        patch = plan.get("patch") if isinstance(plan.get("patch"), dict) else {}
        if not isinstance(patch.get("scene_repairs"), list) or not patch.get("scene_repairs"):
            errors.append("visual_scene_patch requires a non-empty scene_repairs list")
    if patch_type == "director_patch":
        patch = plan.get("patch") if isinstance(plan.get("patch"), dict) else {}
        move_fields = patch.get("replace_move_fields", {})
        if not isinstance(move_fields, dict):
            errors.append("replace_move_fields must be an object")
        for ply, fields in move_fields.items() if isinstance(move_fields, dict) else []:
            if not str(ply).isdigit() or not isinstance(fields, dict):
                errors.append("move patch keys must be numeric ply objects")
                continue
            unknown = sorted(set(fields) - ALLOWED_MOVE_FIELDS)
            if unknown:
                errors.append(f"move patch contains unsupported fields={unknown}")
            if "claims" in fields and not isinstance(fields["claims"], list):
                errors.append(f"move patch claims must be a list at ply={ply}")
        top_fields = patch.get("replace_top_level_fields", {})
        if not isinstance(top_fields, dict):
            errors.append("replace_top_level_fields must be an object")
        elif sorted(set(top_fields) - ALLOWED_TOP_LEVEL_FIELDS):
            errors.append("top-level patch contains unsupported fields")
    if diagnosis.get("failure_class") == "publication":
        errors.append("publication failures cannot be repaired by the content self-repair lane")
    return not errors, errors


def _safe_scene_repairs_from_evidence(evidence: dict[str, Any], diagnosis: dict[str, Any]) -> list[dict[str, Any]]:
    review = evidence.get("review_context") if isinstance(evidence.get("review_context"), dict) else {}
    discarded = review.get("discarded_unsafe_repairs") if isinstance(review.get("discarded_unsafe_repairs"), list) else []
    contexts = {str(scene.get("index")): scene for scene in (evidence.get("job_context", {}).get("scenes", []) if isinstance(evidence.get("job_context"), dict) else []) if isinstance(scene, dict)}
    repairs: list[dict[str, Any]] = []
    phase_defaults = {
        "action": ("move_path", ["piece_anchor", "legal_destinations"]),
        "reply": ("threat_marker", ["piece_anchor", "threat_marker"]),
        "effect": ("before_after", ["played_destination", "effect_after"]),
        "constraint": ("rule_focus", ["rule_focus", "constraint_boundary"]),
    }
    primitive_aliases = {
        "line_highlight": "attack_line",
        "path_highlight": "path_lines",
        "square_highlight": "square_contrast",
        "influence_zone": "defense_zone",
        "show_all_legal_moves": "legal_destinations",
        "highlight_file": "central_files",
        "file_brighten": "central_files",
    }
    for item in discarded:
        if not isinstance(item, dict) or not isinstance(item.get("repair"), dict):
            continue
        raw = dict(item["repair"])
        scene_id = raw.get("sceneId")
        if scene_id is None:
            continue
        context = contexts.get(str(scene_id), {})
        phase = str(context.get("movePhase") or "action")
        default_kind, default_primitives = phase_defaults.get(phase, ("board_overview", ["concept_focus"]))
        visual_kind = str(raw.get("visualKind") or context.get("visualKind") or default_kind)
        if visual_kind not in ALL_VISUAL_KINDS:
            visual_kind = default_kind
        source_plan = raw.get("visualPlan") if isinstance(raw.get("visualPlan"), dict) else {}
        context_plan = context.get("visualPlan") if isinstance(context.get("visualPlan"), dict) else {}
        primitives = [primitive_aliases.get(str(value), str(value)) for value in source_plan.get("primitives", [])]
        primitives = [value for value in primitives if value in SUPPORTED_BOARD_PRIMITIVES]
        if not primitives:
            primitives = list(default_primitives)
        plan = {
            "mode": "board_overlay",
            "focus": str(source_plan.get("focus") or context_plan.get("focus") or f"scene {scene_id} teaching focus"),
            "primitives": list(dict.fromkeys(primitives)),
        }
        move = context.get("move") if isinstance(context.get("move"), dict) else {}
        piece = str(move.get("piece") or "")
        side = str(move.get("side") or "")
        if piece in {"king", "advisor", "bishop", "knight", "rook", "cannon", "pawn"}:
            plan["focusPiece"] = piece
        if side in {"red", "black"}:
            plan["focusSide"] = side
        repairs.append({
            "sceneId": scene_id,
            "headline": str(raw.get("headline") or context.get("visualKind") or "Focused Xiangqi visual"),
            "visualInstruction": str(raw.get("visualInstruction") or "Highlight the specific board relationship named by the narration."),
            "visualKind": visual_kind,
            "semanticTags": raw.get("semanticTags") if isinstance(raw.get("semanticTags"), list) and raw.get("semanticTags") else [phase, "self_repaired"],
            "visualPlan": plan,
        })
    return repairs


def _normalise_repair_plan_response(raw: dict[str, Any], diagnosis: dict[str, Any], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    """Convert common AI wrapper shapes into the protected v1 repair contract."""
    if isinstance(raw.get("repair_plan"), list) and evidence is not None:
        contexts = {str(scene.get("index")): scene for scene in (evidence.get("job_context", {}).get("scenes", []) if isinstance(evidence.get("job_context"), dict) else []) if isinstance(scene, dict)}
        grouped: dict[str, dict[str, Any]] = {}
        for item in raw.get("repair_plan") or []:
            if not isinstance(item, dict) or str(item.get("patch_type") or "") != "director_patch":
                continue
            scene_id = item.get("scene_id")
            field_path = str(item.get("field_path") or "")
            if scene_id is None or not field_path.startswith("visualPlan."):
                continue
            field = field_path.split(".", 1)[1]
            if field not in {"focus", "focusPiece", "focusSide", "region", "focusLine"}:
                continue
            key = str(scene_id)
            context = contexts.get(key, {})
            base_plan = copy.deepcopy(context.get("visualPlan")) if isinstance(context.get("visualPlan"), dict) else {"mode": "board_overlay", "focus": f"scene {scene_id} teaching focus", "primitives": ["concept_focus"]}
            base_plan[field] = item.get("value")
            grouped[key] = {"sceneId": scene_id, "visualPlan": base_plan}
        if grouped:
            return {
                "schema": REPAIR_SCHEMA,
                "disposition": "apply_patch",
                "failure_class": "visual_storyboard",
                "patch_type": "visual_scene_patch",
                "resume_stage": "storyboard",
                "patch": {"scene_repairs": list(grouped.values())},
                "source": "field_path_visual_adapter",
            }
    if isinstance(raw.get("plan"), list):
        scene_repairs: list[dict[str, Any]] = []
        director_patches: list[dict[str, Any]] = []
        for item in raw.get("plan") or []:
            if not isinstance(item, dict):
                continue
            action = str(item.get("action") or "").lower()
            patch = item.get("patch") if isinstance(item.get("patch"), dict) else {}
            if action in {"patch_director", "patch_scene", "visual_scene_patch"}:
                repair = dict(patch)
                if item.get("scene_id") is not None and repair.get("sceneId") is None:
                    repair["sceneId"] = item.get("scene_id")
                if repair.get("sceneId") is not None:
                    scene_repairs.append(repair)
                else:
                    director_patches.append(repair)
        if scene_repairs and not director_patches:
            return {
                "schema": REPAIR_SCHEMA,
                "disposition": "apply_patch",
                "failure_class": str(raw.get("failure_class") or diagnosis.get("failure_class") or "visual_storyboard"),
                "patch_type": "visual_scene_patch",
                "resume_stage": str(raw.get("resume_stage") or diagnosis.get("affected_stage") or "storyboard"),
                "patch": {"scene_repairs": scene_repairs},
            }
        if director_patches and not scene_repairs:
            return {
                "schema": REPAIR_SCHEMA,
                "disposition": "apply_patch",
                "failure_class": str(raw.get("failure_class") or diagnosis.get("failure_class") or "content_schema"),
                "patch_type": "director_patch",
                "resume_stage": str(raw.get("resume_stage") or diagnosis.get("affected_stage") or "director"),
                "patch": {"replace_top_level_fields": director_patches[0]},
            }
    if str(raw.get("patch_type") or "") == "no_safe_repair" and str(diagnosis.get("failure_class") or "") == "visual_storyboard" and evidence is not None:
        safe_repairs = _safe_scene_repairs_from_evidence(evidence, diagnosis)
        if safe_repairs:
            return {
                "schema": REPAIR_SCHEMA,
                "disposition": "apply_patch",
                "failure_class": "visual_storyboard",
                "patch_type": "visual_scene_patch",
                "resume_stage": "storyboard",
                "patch": {"scene_repairs": safe_repairs},
                "source": "bounded_visual_contract_adapter",
            }
    return dict(raw)


def propose_repair_plan(evidence: dict[str, Any], diagnosis: dict[str, Any], router_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    payload = {
        "schema": REPAIR_SCHEMA,
        "allowed_patch_types": sorted(ALLOWED_PATCH_TYPES),
        "allowed_visual_kinds": sorted(ALL_VISUAL_KINDS),
        "allowed_board_primitives": sorted(SUPPORTED_BOARD_PRIMITIVES),
        "protected_scene_fields": ["movePly", "movePhase", "narration", "caption", "from", "to", "piece", "side", "fen", "moves", "generatedAsset"],
        "diagnosis": diagnosis,
        "evidence": evidence,
    }
    raw = _router_complete_json(REPAIR_INSTRUCTIONS, payload, f"self_repair:plan:{evidence.get('job_id')}:{evidence.get('attempt')}", router_factory)
    if raw is None:
        return {"schema": REPAIR_SCHEMA, "disposition": "quarantine", "failure_class": diagnosis.get("failure_class", "unknown"), "patch_type": "no_safe_repair", "resume_stage": diagnosis.get("affected_stage", "director"), "reason": "AI repair planner unavailable"}
    plan = _normalise_repair_plan_response(raw, diagnosis, evidence)
    plan.setdefault("schema", REPAIR_SCHEMA)
    plan.setdefault("failure_class", diagnosis.get("failure_class", "unknown"))
    plan.setdefault("resume_stage", diagnosis.get("affected_stage", "director"))
    plan.setdefault("patch_type", "no_safe_repair")
    valid, errors = validate_plan(plan, diagnosis)
    if not valid:
        return {"schema": REPAIR_SCHEMA, "disposition": "quarantine", "failure_class": diagnosis.get("failure_class", "unknown"), "patch_type": "no_safe_repair", "resume_stage": "director", "reason": "; ".join(errors), "invalid_plan": plan}
    plan["plan_sha256"] = _json_hash(plan)
    return plan


def apply_director_patch(director_data: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    patched = copy.deepcopy(director_data)
    patch = plan.get("patch") if isinstance(plan.get("patch"), dict) else {}
    top = patch.get("replace_top_level_fields") if isinstance(patch.get("replace_top_level_fields"), dict) else {}
    for key, value in top.items():
        patched[key] = _bounded_text(value, 5000)
    move_map = {str(move.get("ply")): move for move in patched.get("moves", []) if isinstance(move, dict) and move.get("ply") is not None}
    replacements = patch.get("replace_move_fields") if isinstance(patch.get("replace_move_fields"), dict) else {}
    for ply, fields in replacements.items():
        move = move_map.get(str(ply))
        if move is None:
            raise SelfRepairError(f"repair references missing move ply={ply}")
        for key, value in fields.items():
            if key == "claims":
                move[key] = copy.deepcopy(value)
            else:
                move[key] = _bounded_text(value, 1200)
    return patched


def write_checkpoint(root: str | Path, evidence: dict[str, Any], diagnosis: dict[str, Any], plan: dict[str, Any], status: str) -> Path:
    path = Path(root) / "repair" / f"attempt-{int(evidence.get('attempt') or 0):02d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": REPAIR_SCHEMA, "status": status, "evidence": evidence, "diagnosis": diagnosis, "plan": plan, "checkpoint_sha256": _json_hash({"status": status, "evidence": evidence, "diagnosis": diagnosis, "plan": plan})}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def repair_failure(
    *,
    job_id: str,
    candidate_id: str,
    attempt: int,
    stage: str,
    error_text: str,
    candidate_payload: dict[str, Any],
    director_data: dict[str, Any] | None,
    output_root: str | Path,
    router_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    evidence = collect_failure_evidence(job_id=job_id, candidate_id=candidate_id, attempt=attempt, stage=stage, error_text=error_text, candidate_payload=candidate_payload, output_root=output_root)
    diagnosis = diagnose_failure(evidence, router_factory)
    if diagnosis.get("failure_class") == "publication":
        plan = {"schema": REPAIR_SCHEMA, "disposition": "quarantine", "failure_class": "publication", "patch_type": "no_safe_repair", "resume_stage": "publication", "reason": "Publication failures belong to YouTube reconciliation, not content self-repair."}
        checkpoint = write_checkpoint(Path(output_root) / "jobs" / job_id, evidence, diagnosis, plan, "quarantined")
        return {"status": "quarantined", "evidence": evidence, "diagnosis": diagnosis, "plan": plan, "checkpoint": str(checkpoint)}
    if not diagnosis.get("repairable"):
        diagnosis["planner_override"] = "A second repair-planning pass is required for bounded content, storyboard, asset, TTS, and render failures; do not stop solely on the first diagnosis."
    plan = propose_repair_plan(evidence, diagnosis, router_factory)
    valid, errors = validate_plan(plan, diagnosis)
    if not valid or plan.get("patch_type") == "no_safe_repair":
        plan = dict(plan)
        plan["reason"] = "; ".join(errors) if errors else str(plan.get("reason") or "no safe repair")
        checkpoint = write_checkpoint(Path(output_root) / "jobs" / job_id, evidence, diagnosis, plan, "quarantined")
        return {"status": "quarantined", "evidence": evidence, "diagnosis": diagnosis, "plan": plan, "checkpoint": str(checkpoint)}
    if plan.get("patch_type") == "director_patch":
        if director_data is None:
            plan["reason"] = "director data is unavailable for a director patch"
            checkpoint = write_checkpoint(Path(output_root) / "jobs" / job_id, evidence, diagnosis, plan, "quarantined")
            return {"status": "quarantined", "evidence": evidence, "diagnosis": diagnosis, "plan": plan, "checkpoint": str(checkpoint)}
        patched = apply_director_patch(director_data, plan)
        override_path = Path(output_root) / "jobs" / job_id / "repair" / "director-override.json"
        override_path.parent.mkdir(parents=True, exist_ok=True)
        override_path.write_text(json.dumps(patched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        plan["override_path"] = str(override_path)
        checkpoint = write_checkpoint(Path(output_root) / "jobs" / job_id, evidence, diagnosis, plan, "patched")
        return {"status": "patched", "override_path": str(override_path), "override_kind": "director", "evidence": evidence, "diagnosis": diagnosis, "plan": plan, "checkpoint": str(checkpoint)}
    if plan.get("patch_type") == "visual_scene_patch":
        patch = plan.get("patch") if isinstance(plan.get("patch"), dict) else {}
        override_path = Path(output_root) / "jobs" / job_id / "repair" / "scene-repair.json"
        override_path.parent.mkdir(parents=True, exist_ok=True)
        override_path.write_text(json.dumps({"scene_repairs": patch.get("scene_repairs", [])}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        plan["override_path"] = str(override_path)
        checkpoint = write_checkpoint(Path(output_root) / "jobs" / job_id, evidence, diagnosis, plan, "patched")
        return {"status": "patched", "override_path": str(override_path), "override_kind": "scene", "evidence": evidence, "diagnosis": diagnosis, "plan": plan, "checkpoint": str(checkpoint)}
    checkpoint = write_checkpoint(Path(output_root) / "jobs" / job_id, evidence, diagnosis, plan, "retry_stage")
    return {"status": "retry_stage", "evidence": evidence, "diagnosis": diagnosis, "plan": plan, "checkpoint": str(checkpoint)}
