from __future__ import annotations

import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ai_router_bridge import load_router

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
    if any(token in value for token in ("youtube", "oauth", "invalid_grant", "quotaexceeded", "publication")):
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
    evidence = {
        "schema": "xiangqi_failure_evidence_v1",
        "job_id": job_id,
        "candidate_id": candidate_id,
        "attempt": int(attempt),
        "stage": str(stage or "unknown"),
        "failure_class": classify_failure(error_text, stage),
        "error": _bounded_text(error_text, 8000),
        "candidate_payload": copy.deepcopy(candidate_payload),
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
    diagnosis = {
        "schema": DIAGNOSIS_SCHEMA,
        "repairable": bool(raw.get("repairable", False)),
        "failure_class": str(raw.get("failure_class") or evidence.get("failure_class") or "unknown"),
        "root_cause": _bounded_text(raw.get("root_cause"), 2000),
        "diagnosis": _bounded_text(raw.get("diagnosis"), 3000),
        "affected_stage": str(raw.get("affected_stage") or evidence.get("stage") or "unknown"),
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


def propose_repair_plan(evidence: dict[str, Any], diagnosis: dict[str, Any], router_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    payload = {"schema": REPAIR_SCHEMA, "allowed_patch_types": sorted(ALLOWED_PATCH_TYPES), "diagnosis": diagnosis, "evidence": evidence}
    raw = _router_complete_json(REPAIR_INSTRUCTIONS, payload, f"self_repair:plan:{evidence.get('job_id')}:{evidence.get('attempt')}", router_factory)
    if raw is None:
        return {"schema": REPAIR_SCHEMA, "disposition": "quarantine", "failure_class": diagnosis.get("failure_class", "unknown"), "patch_type": "no_safe_repair", "resume_stage": diagnosis.get("affected_stage", "director"), "reason": "AI repair planner unavailable"}
    plan = dict(raw)
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
        plan = {"schema": REPAIR_SCHEMA, "disposition": "quarantine", "failure_class": diagnosis.get("failure_class", "unknown"), "patch_type": "no_safe_repair", "resume_stage": diagnosis.get("affected_stage", "director"), "reason": diagnosis.get("root_cause") or "diagnosis marked failure as non-repairable"}
        checkpoint = write_checkpoint(Path(output_root) / "jobs" / job_id, evidence, diagnosis, plan, "quarantined")
        return {"status": "quarantined", "evidence": evidence, "diagnosis": diagnosis, "plan": plan, "checkpoint": str(checkpoint)}
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
