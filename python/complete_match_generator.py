from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

from local_store import DEFAULT_FEN, LocalStore
from systems.durable_content_state import DurableStateStore
import xiangqi_rules as rules


PROFILE_PATH = ROOT / "config" / "xiangqi_complete_match_profiles.json"


def _load_profiles(path: str | Path = PROFILE_PATH) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if int(data.get("schema_version") or 0) != 1 or data.get("domain_id") != "xiangqi":
        raise ValueError("invalid Xiangqi complete-match profile contract")
    profiles = data.get("profiles") or []
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("complete-match profiles must be a non-empty array")
    return [dict(item) for item in profiles]


def _legal_moves(board: rules.Board, side: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source, piece in sorted(board.items()):
        if piece.side != side:
            continue
        for x in range(rules.BOARD_WIDTH):
            for y in range(rules.BOARD_HEIGHT):
                target = (x, y)
                if target == source:
                    continue
                destination = board.get(target)
                if destination is not None and destination.side == side:
                    continue
                if destination is not None and destination.type == "king":
                    continue
                if not rules._piece_geometry_is_legal(board, source, target, piece, destination):
                    continue
                trial = dict(board)
                captured = rules._apply_move(trial, source, target, piece)
                if rules.is_in_check(trial, side):
                    continue
                result.append(
                    {
                        "from": list(source),
                        "to": list(target),
                        "piece": piece.type,
                        "side": side,
                        "captured": captured.type if captured else None,
                    }
                )
    return result


def _play_until_terminal(seed: int, max_plies: int = 180) -> tuple[list[dict[str, Any]], str]:
    board, side = rules.parse_fen(DEFAULT_FEN)
    rng = random.Random(seed)
    moves: list[dict[str, Any]] = []
    seen: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for ply in range(1, max_plies + 1):
        candidates = _legal_moves(board, side)
        if not candidates:
            return moves, "checkmate" if rules.is_in_check(board, side) else "stalemate"
        scored: list[tuple[float, dict[str, Any]]] = []
        for move in candidates:
            source = tuple(move["from"])
            target = tuple(move["to"])
            score = 0.0
            if move.get("captured"):
                score += 12.0 + rng.random() * 3.0
            else:
                score += rng.random() * 4.0
            score += (4 - abs(4 - target[0])) * 0.4
            score += ((9 - target[1]) if side == "red" else target[1]) * 0.05
            if (source, target) in seen:
                score -= 8.0
            if move["piece"] in {"king", "advisor"}:
                score -= 4.0
            if move["piece"] in {"rook", "cannon", "knight"}:
                score += 1.5
            scored.append((score, move))
        scored.sort(key=lambda item: (item[0], item[1]["from"], item[1]["to"]), reverse=True)
        selected = dict(scored[0][1])
        selected["ply"] = ply
        moves.append(selected)
        source = tuple(selected["from"])
        target = tuple(selected["to"])
        seen.add((source, target))
        rules._apply_move(board, source, target, board[source])
        side = "black" if side == "red" else "red"
    return moves, "max_plies_reached"


def _match_fingerprint(profile: dict[str, Any], moves: list[dict[str, Any]]) -> str:
    payload = {"profile": profile.get("id"), "seed": profile.get("seed"), "moves": moves}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _annotate_moves(moves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add concise, deterministic narration metadata without unsupported causal claims."""
    annotated: list[dict[str, Any]] = []
    for raw in moves:
        move = dict(raw)
        piece = str(move.get("piece") or "piece")
        ply = int(move.get("ply") or len(annotated) + 1)
        move.update(
            {
                "ply": ply,
                "label": f"Legal {piece} move",
                "purpose": f"develop the {piece}",
                "opponentReply": "make a legal reply",
                "effect": "the position changes",
                "claims": [
                    {
                        "claimType": "legal_move",
                        "ply": ply,
                        "position": "after",
                        "statement": f"The supplied move at ply {ply} is legal in the traced position.",
                    }
                ],
            }
        )
        annotated.append(move)
    return annotated


def generate_complete_match(*, db_path: str | Path, output_path: str | Path, profile_id: str | None = None, profile_path: str | Path = PROFILE_PATH, reason: str = "post-curriculum Xiangqi complete match") -> dict[str, Any]:
    profiles = _load_profiles(profile_path)
    profile = next((item for item in profiles if profile_id and item.get("id") == profile_id), None)
    if profile is None:
        profile = profiles[0]
    moves, end_reason = _play_until_terminal(int(profile.get("seed") or 0))
    validation = rules.validate_move_sequence(DEFAULT_FEN, moves)
    minimum = int(profile.get("min_plies") or 1)
    if end_reason not in {"checkmate", "stalemate"} or len(moves) < minimum or not validation.get("ok"):
        return {
            "status": "no_valid_candidate",
            "domain": "xiangqi",
            "reason": "profile did not produce a validated terminal game",
            "profile_id": profile.get("id"),
            "end_reason": end_reason,
            "plies": len(moves),
            "validation": validation,
        }
    fingerprint = _match_fingerprint(profile, moves)
    candidate_id = f"xiangqi-complete-{profile['id']}-{fingerprint[:12]}"
    title = str(profile.get("title_template") or "A Complete Xiangqi Game")
    target_seconds = max(120, min(600, 1.8 * len(moves)))
    moves = _annotate_moves(moves)
    job = {
        "id": candidate_id,
        "title": title,
        "language": "en",
        "content_type": "full_game",
        "format": "game",
        "source_kind": "generated_complete_match",
        "source_url": None,
        "topic_key": f"complete match {profile['id']} {fingerprint[:12]}",
        "fen": DEFAULT_FEN,
        "moves": moves,
        "match_profile": profile,
        "end_reason": end_reason,
        "target_seconds": target_seconds,
        "durationInSeconds": target_seconds,
        "visual_mode": "storyboard",
        "analysis_focus": "the next phase of the game",
        "narration": "This complete Xiangqi game follows a legal trace from the initial position to its terminal result.",
        "hook": profile.get("challenge"),
        "narration_policy": "explain the decision, opponent reply, changed position, and revised plan",
        "content_fingerprint": fingerprint,
        "generation_reason": reason,
    }
    store = LocalStore(db_path)
    gate = store.curriculum_gate("en")
    if not gate.get("complete"):
        return {
            "status": "no_candidate",
            "domain": "xiangqi",
            "reason": "curriculum_incomplete",
            "curriculum": gate,
            "profile_id": profile.get("id"),
            "end_reason": end_reason,
            "plies": len(moves),
        }
    destination = Path(output_path)
    if not destination.is_absolute():
        destination = ROOT / destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    inserted = store.add_candidate(
        {
            "id": candidate_id,
            "fingerprint": fingerprint,
            "content_type": "full_game",
            "title": title,
            "language": "en",
            "source_kind": "generated_complete_match",
            "priority_score": 25.0,
            "topic_key": job["topic_key"],
            "payload": job,
        }
    )
    DurableStateStore(db_path).record_variant(
        fingerprint=fingerprint,
        domain_id="xiangqi",
        variant_kind="complete_match",
        job_id=candidate_id,
        signature={"profile_id": profile.get("id"), "seed": profile.get("seed"), "plies": len(moves), "end_reason": end_reason},
        status="generated",
    )
    return {
        "status": "selected",
        "domain": "xiangqi",
        "source": "complete_match_generator",
        "candidate_id": candidate_id,
        "job_id": candidate_id,
        "profile_id": profile.get("id"),
        "end_reason": end_reason,
        "plies": len(moves),
        "fingerprint": fingerprint,
        "inserted": bool(inserted),
        "input": str(destination),
    }


__all__ = ["generate_complete_match"]
