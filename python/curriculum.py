from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEN = "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR r"

TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "starting-pawn-cannon": [
        {"from": [0, 6], "to": [0, 5], "piece": "pawn", "side": "red", "label": "Open a route"},
        {"from": [0, 3], "to": [0, 4], "piece": "pawn", "side": "black", "label": "Claim a reply"},
        {"from": [1, 7], "to": [1, 4], "piece": "cannon", "side": "red", "label": "Use the new line"},
    ],
    "palace-defense": [
        {"from": [4, 9], "to": [4, 8], "piece": "king", "side": "red", "label": "Protect the palace"},
        {"from": [4, 0], "to": [4, 1], "piece": "king", "side": "black", "label": "Answer the line"},
        {"from": [3, 9], "to": [4, 8], "piece": "advisor", "side": "red", "label": "Close the escape square"},
    ],
    "horse-development": [
        {"from": [1, 9], "to": [2, 7], "piece": "knight", "side": "red", "label": "Develop the horse"},
        {"from": [1, 0], "to": [2, 2], "piece": "knight", "side": "black", "label": "Mirror the pressure"},
        {"from": [2, 6], "to": [2, 5], "piece": "pawn", "side": "red", "label": "Control the horse eye"},
    ],
    "rook-file": [
        {"from": [0, 6], "to": [0, 5], "piece": "pawn", "side": "red", "label": "Clear the file"},
        {"from": [0, 0], "to": [0, 4], "piece": "rook", "side": "black", "label": "Contest the file"},
        {"from": [0, 9], "to": [0, 5], "piece": "rook", "side": "red", "label": "Activate the chariot"},
    ],
    "cannon-screen": [
        {"from": [1, 7], "to": [1, 4], "piece": "cannon", "side": "red", "label": "Aim through the screen"},
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
    "cannon-rook-coordination": [
        {"from": [1, 7], "to": [1, 4], "piece": "cannon", "side": "red", "label": "Fix the defender"},
        {"from": [0, 0], "to": [0, 4], "piece": "rook", "side": "black", "label": "Seek counterplay"},
        {"from": [0, 9], "to": [0, 5], "piece": "rook", "side": "red", "label": "Exploit the open file"},
    ],
}


def load_curriculum(path: str | Path = ROOT / "config" / "xiangqi_curriculum_en.json") -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def lesson_payload(lesson: dict[str, Any]) -> dict[str, Any]:
    template = str(lesson.get("position_template") or "starting-pawn-cannon")
    moves = [dict(move) for move in TEMPLATES.get(template, TEMPLATES["starting-pawn-cannon"])]
    return {
        "fen": DEFAULT_FEN,
        "moves": moves,
        "topic_key": str(lesson["lesson_key"]),
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
