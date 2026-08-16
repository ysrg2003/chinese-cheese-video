from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from curriculum import DEFAULT_FEN, STATIC_VISUAL_MODES, TEMPLATES, lesson_payload, load_curriculum
from director import make_job
from xiangqi_rules import validate_move_sequence


ROOT = Path(__file__).resolve().parents[1]
CURRICULUM_PATH = ROOT / "config" / "xiangqi_curriculum_en.json"


def _error(errors: list[dict[str, Any]], code: str, **details: Any) -> None:
    errors.append({"code": code, **details})


def run_preflight() -> dict[str, Any]:
    curriculum = load_curriculum(CURRICULUM_PATH)
    lessons = curriculum.get("lessons") or []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    seen_sequences: set[int] = set()
    lesson_keys = {str(lesson.get("lesson_key") or "") for lesson in lessons}
    validated_templates: dict[str, dict[str, Any]] = {}

    for lesson in lessons:
        lesson_key = str(lesson.get("lesson_key") or "")
        sequence = int(lesson.get("sequence_no") or 0)
        template_name = str(lesson.get("position_template") or "")
        visual_mode = str(lesson.get("visual_mode") or "")
        if not lesson_key:
            _error(errors, "missing_lesson_key", sequence=sequence)
            continue
        if lesson_key in seen_keys:
            _error(errors, "duplicate_lesson_key", lesson_key=lesson_key)
        seen_keys.add(lesson_key)
        if sequence in seen_sequences:
            _error(errors, "duplicate_sequence_no", lesson_key=lesson_key, sequence_no=sequence)
        seen_sequences.add(sequence)
        for prerequisite in lesson.get("prerequisites") or []:
            if prerequisite not in lesson_keys:
                _error(errors, "missing_prerequisite", lesson_key=lesson_key, prerequisite=prerequisite)
            else:
                prerequisite_sequence = next(int(item.get("sequence_no") or 0) for item in lessons if item.get("lesson_key") == prerequisite)
                if prerequisite_sequence >= sequence:
                    _error(errors, "prerequisite_not_earlier", lesson_key=lesson_key, prerequisite=prerequisite, sequence_no=sequence)

        if visual_mode in STATIC_VISUAL_MODES:
            moves: list[dict[str, Any]] = []
        else:
            if not template_name:
                _error(errors, "missing_position_template", lesson_key=lesson_key)
                continue
            if template_name not in TEMPLATES:
                _error(errors, "unknown_position_template", lesson_key=lesson_key, position_template=template_name)
                continue
            moves = [dict(move) for move in TEMPLATES[template_name]]
            if not moves:
                _error(errors, "empty_dynamic_template", lesson_key=lesson_key, position_template=template_name)
                continue

        legal = validate_move_sequence(DEFAULT_FEN, moves)
        if not legal.get("ok"):
            _error(errors, "illegal_template", lesson_key=lesson_key, position_template=template_name, errors=legal.get("errors") or [])
            continue

        payload = lesson_payload(lesson)
        payload["researchBundle"] = {"status": "grounded", "sourceHash": "curriculum-preflight"}
        if lesson.get("target_seconds"):
            payload["durationInSeconds"] = lesson.get("target_seconds")
        try:
            job = make_job(f"preflight-{lesson_key}-en", payload, {"title": lesson.get("title"), "narration": "Preflight narration", "moves": moves})
            proof = job.get("claimProof") if isinstance(job.get("claimProof"), dict) else {}
            if proof.get("ok") is not True:
                _error(errors, "claim_proof_failed", lesson_key=lesson_key, errors=proof.get("errors") or [])
        except Exception as exc:
            _error(errors, "lesson_contract_failed", lesson_key=lesson_key, position_template=template_name, error=str(exc))

        validated_templates.setdefault(template_name or "static", {"lessons": [], "moves": len(moves)})["lessons"].append(lesson_key)

    for template_name, template_moves in TEMPLATES.items():
        legal = validate_move_sequence(DEFAULT_FEN, template_moves)
        if not legal.get("ok"):
            _error(errors, "unreferenced_template_illegal", position_template=template_name, errors=legal.get("errors") or [])

    result = {
        "contract": "xiangqi_curriculum_preflight_v1",
        "curriculum_path": str(CURRICULUM_PATH),
        "lesson_count": len(lessons),
        "template_count": len(TEMPLATES),
        "validated_template_groups": validated_templates,
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }
    return result


def main() -> int:
    result = run_preflight()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
