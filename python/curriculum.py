from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEN = "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR r"

STATIC_VISUAL_MODES = {"static_board", "foundation_storyboard", "board_introduction", "setup_overview"}
PIECE_DISPLAY_NAMES = {
    "king": "General",
    "advisor": "Advisor",
    "bishop": "Elephant",
    "knight": "Horse",
    "rook": "Chariot",
    "cannon": "Cannon",
    "pawn": "Pawn",
}


def piece_learning_context(puzzle: dict[str, Any]) -> dict[str, Any]:
    """Return stage-scoped prerequisite references for piece-academy narration."""
    if str(puzzle.get("teaching_scope") or "") not in {"piece_rules", "piece_rules_review"} and str(puzzle.get("curriculum_stage") or "") != "C-piece-academy":
        return {"enabled": False, "target": None, "previous": [], "upcoming": [], "used": []}
    try:
        lessons = load_curriculum().get("lessons") or []
    except (OSError, json.JSONDecodeError):
        lessons = []
    by_piece: dict[str, dict[str, Any]] = {}
    for lesson in lessons:
        piece = str(lesson.get("target_piece") or "").strip().lower()
        if piece and piece not in by_piece:
            by_piece[piece] = lesson
    template = str(puzzle.get("position_template") or "")
    used_keys = []
    for move in TEMPLATES.get(template, puzzle.get("moves") or []):
        if isinstance(move, dict):
            piece = str(move.get("piece") or "").strip().lower()
            if piece and piece not in used_keys:
                used_keys.append(piece)
    target = str(puzzle.get("target_piece") or "").strip().lower()
    if target and target not in used_keys:
        used_keys.insert(0, target)
    current_order = int(puzzle.get("curriculum_sequence") or puzzle.get("curriculum_order") or 0)
    previous, upcoming = [], []
    for piece in used_keys:
        if piece == target:
            continue
        lesson = by_piece.get(piece)
        record = {
            "piece": piece,
            "name": PIECE_DISPLAY_NAMES.get(piece, str(piece).title()),
            "lesson_key": lesson.get("lesson_key") if lesson else None,
            "lesson_title": lesson.get("title") if lesson else None,
            "movement_summary": lesson.get("target_piece_movement_summary_en") if lesson else None,
        }
        lesson_order = int(lesson.get("sequence_no") or 0) if lesson else 0
        if lesson_order and current_order and lesson_order < current_order:
            previous.append(record)
        else:
            upcoming.append(record)
    target_record = {
        "piece": target,
        "name": str(puzzle.get("target_piece_name_en") or PIECE_DISPLAY_NAMES.get(target, target.title() if target else "piece")),
        "movement_summary": puzzle.get("target_piece_movement_summary_en"),
    } if target else None
    return {"enabled": True, "target": target_record, "previous": previous, "upcoming": upcoming, "used": used_keys}


def piece_learning_intro(puzzle: dict[str, Any], language: str = "en") -> str:
    """Write a concise English-first bridge without changing non-educational stages."""
    context = piece_learning_context(puzzle)
    if not context.get("enabled") or language != "en":
        return ""
    parts: list[str] = []
    for item in context.get("previous") or []:
        title = item.get("lesson_title") or f"an earlier {item.get('name')} lesson"
        summary = item.get("movement_summary") or f"the {item.get('name')} movement"
        parts.append(f"We covered the {item.get('name')} in an earlier lesson, so here is the quick reminder: {summary} The full lesson is {title}.")
    for item in context.get("upcoming") or []:
        summary = item.get("movement_summary") or f"the basic movement of the {item.get('name')}"
        parts.append(f"This example also uses a {item.get('name')}. For orientation, {summary} We will study the {item.get('name')} in a separate lesson later.")
    target = context.get("target") or {}
    if target.get("name"):
        summary = target.get("movement_summary") or f"the basic movement and rule of the {target.get('name')}"
        parts.append(f"Now we turn to the {target.get('name')}, our target piece for this lesson: {summary}")
    return " ".join(parts).strip()

TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "starting-pawn-cannon": [
        {"from": [0, 6], "to": [0, 5], "piece": "pawn", "side": "red", "label": "Open a route"},
        {"from": [0, 3], "to": [0, 4], "piece": "pawn", "side": "black", "label": "Claim a reply"},
        {"from": [1, 7], "to": [1, 4], "piece": "cannon", "side": "red", "label": "Use the new line"},
    ],
    "palace-defense": [
        {"from": [3, 9], "to": [4, 8], "piece": "advisor", "side": "red", "label": "Reinforce the palace diagonally"},
        {"from": [2, 3], "to": [2, 4], "piece": "pawn", "side": "black", "label": "Make a legal reply without facing"},
        {"from": [4, 9], "to": [3, 9], "piece": "king", "side": "red", "label": "Move safely inside the palace"},
    ],
    "horse-development": [
        {"from": [1, 9], "to": [2, 7], "piece": "knight", "side": "red", "label": "Develop the Horse"},
        {"from": [1, 0], "to": [2, 2], "piece": "knight", "side": "black", "label": "Develop the opposing Horse"},
        {"from": [2, 6], "to": [2, 5], "piece": "pawn", "side": "red", "label": "Advance the Pawn"},
    ],
    "horse-leg-block": [
        {"from": [1, 9], "to": [2, 7], "piece": "knight", "side": "red", "label": "Develop the Horse"},
        {"from": [1, 0], "to": [2, 2], "piece": "knight", "side": "black", "label": "Develop the opposing Horse"},
        {"from": [2, 6], "to": [2, 5], "piece": "pawn", "side": "red", "label": "Advance the Pawn"},
        {"from": [6, 3], "to": [6, 4], "piece": "pawn", "side": "black", "label": "Make a waiting reply"},
        {"from": [2, 5], "to": [2, 4], "piece": "pawn", "side": "red", "label": "Advance again"},
        {"from": [6, 4], "to": [6, 5], "piece": "pawn", "side": "black", "label": "Keep the reply legal"},
        {"from": [2, 4], "to": [2, 3], "piece": "pawn", "side": "red", "label": "Occupy the Horse Leg"},
    ],
    "rook-file": [
        {"from": [0, 6], "to": [0, 5], "piece": "pawn", "side": "red", "label": "Clear the file"},
        {"from": [2, 3], "to": [2, 4], "piece": "pawn", "side": "black", "label": "Make a legal waiting reply"},
        {"from": [0, 5], "to": [0, 4], "piece": "pawn", "side": "red", "label": "Clear the file further"},
        {"from": [4, 3], "to": [4, 4], "piece": "pawn", "side": "black", "label": "Keep the reply legal"},
        {"from": [0, 9], "to": [0, 5], "piece": "rook", "side": "red", "label": "Activate the chariot"},
    ],
    "cannon-screen": [
        {"from": [1, 7], "to": [2, 7], "piece": "cannon", "side": "red", "label": "Aim through the screen"},
        {"from": [2, 3], "to": [2, 4], "piece": "pawn", "side": "black", "label": "Defend the target"},
        {"from": [7, 9], "to": [6, 7], "piece": "knight", "side": "red", "label": "Add a second threat"},
    ],
    "river-soldier": [
        {"from": [4, 6], "to": [4, 5], "piece": "pawn", "side": "red", "label": "Approach the river"},
        {"from": [4, 3], "to": [4, 4], "piece": "pawn", "side": "black", "label": "Meet the advance"},
        {"from": [4, 5], "to": [4, 4], "piece": "pawn", "side": "red", "label": "Cross into new options"},
    ],
    "elephant-eye": [
        {"from": [2, 9], "to": [4, 7], "piece": "bishop", "side": "red", "label": "Guard the diagonal"},
        {"from": [2, 3], "to": [2, 4], "piece": "pawn", "side": "black", "label": "Block the elephant eye"},
        {"from": [4, 7], "to": [2, 5], "piece": "bishop", "side": "red", "label": "Choose the safe route"},
    ],
    "board-only": [],
    "cannon-rook-coordination": [
        {"from": [1, 7], "to": [1, 4], "piece": "cannon", "side": "red", "label": "Fix the defender"},
        {"from": [2, 3], "to": [2, 4], "piece": "pawn", "side": "black", "label": "Make a legal reply"},
        {"from": [0, 6], "to": [0, 5], "piece": "pawn", "side": "red", "label": "Clear the chariot file"},
        {"from": [4, 3], "to": [4, 4], "piece": "pawn", "side": "black", "label": "Keep the reply legal"},
        {"from": [0, 5], "to": [0, 4], "piece": "pawn", "side": "red", "label": "Open the file further"},
        {"from": [6, 3], "to": [6, 4], "piece": "pawn", "side": "black", "label": "Preserve a legal tempo"},
        {"from": [0, 9], "to": [0, 5], "piece": "rook", "side": "red", "label": "Exploit the open file"},
    ],
}


def load_curriculum(path: str | Path = ROOT / "config" / "xiangqi_curriculum_en.json") -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def lesson_payload(lesson: dict[str, Any]) -> dict[str, Any]:
    template = str(lesson.get("position_template") or "starting-pawn-cannon")
    visual_mode = str(lesson.get("visual_mode") or "")
    moves = [] if visual_mode in STATIC_VISUAL_MODES else [dict(move) for move in TEMPLATES.get(template, TEMPLATES["starting-pawn-cannon"])]
    return {
        "fen": DEFAULT_FEN,
        "moves": moves,
        "topic_key": str(lesson["lesson_key"]),
        "title": lesson.get("title"),
        "content_type": lesson.get("content_type", "definition"),
        "curriculum_lesson_key": str(lesson["lesson_key"]),
        "curriculum_sequence": int(lesson["sequence_no"]),
        "curriculum_stage": lesson.get("stage"),
        "playlist_key": lesson.get("playlist_key"),
        "difficulty": lesson.get("difficulty"),
        "format": lesson.get("format"),
        "target_seconds": lesson.get("target_seconds"),
        "objective": lesson.get("objective"),
        "analysis_focus": lesson.get("analysis_focus"),
        "hook": lesson.get("hook"),
        "prerequisites": lesson.get("prerequisites", []),
        "position_template": template,
        "visual_mode": visual_mode or None,
        "visual_focus": lesson.get("visual_focus"),
        "visualStoryboard": lesson.get("visual_storyboard"),
        "visualStoryboardSource": lesson.get("visual_storyboard_source"),
        "teaching_scope": lesson.get("teaching_scope"),
        "target_piece": lesson.get("target_piece"),
        "target_piece_name_en": lesson.get("target_piece_name_en"),
        "target_piece_movement_summary_en": lesson.get("target_piece_movement_summary_en"),
    }


def candidate_from_lesson(lesson: dict[str, Any]) -> dict[str, Any]:
    payload = lesson_payload(lesson)
    lesson_key = str(lesson["lesson_key"])
    fingerprint = hashlib.sha256(json.dumps({"lesson_key": lesson_key, "language": "en"}, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "id": f"curriculum-{lesson_key}",
        "fingerprint": fingerprint,
        "topic_key": lesson_key,
        "content_type": lesson.get("content_type", "definition"),
        "title": lesson["title"],
        "language": "en",
        "source_kind": "curriculum",
        "priority_score": 100000.0 - float(lesson["sequence_no"]),
        "payload": payload,
    }
