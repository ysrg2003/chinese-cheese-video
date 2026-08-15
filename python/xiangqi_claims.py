from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping

from xiangqi_rules import (
    Board,
    Piece,
    _apply_move,
    _piece_geometry_is_legal,
    is_in_check,
    parse_fen,
    validate_move_sequence,
)


CLAIM_CONTRACT = "xiangqi_claim_proof_v1"
CLAIM_TYPES = {
    "legal_move",
    "horse_leg_block",
    "horse_leg_open",
    "elephant_eye_block",
    "elephant_eye_open",
    "cannon_screen",
    "river_limit",
    "flying_general",
    "legal_destinations",
}
_SUSPICIOUS_CAUSAL_LANGUAGE = re.compile(
    r"\b(block|blocked|blocks|blocking|leg|eye|screen|mount|cross(?:es|ed|ing)?|cannot|can't|prevents?|opens?|opened|unblocks?)\b",
    re.IGNORECASE,
)


def _point(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        return int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return None


def _copy_board(board: Board) -> Board:
    return dict(board)


def _apply_trace_move(board: Board, move: Mapping[str, Any]) -> Piece | None:
    source = _point(move.get("from"))
    target = _point(move.get("to"))
    if source is None or target is None or source not in board:
        raise ValueError(f"cannot trace move {move}")
    piece = board[source]
    return _apply_move(board, source, target, piece)


def _piece_at(board: Board, value: Any) -> Piece | None:
    point = _point(value)
    return board.get(point) if point is not None else None


def _horse_options(board: Board, source: tuple[int, int]) -> list[dict[str, Any]]:
    piece = board.get(source)
    if not piece or piece.type != "knight":
        return []
    options: list[dict[str, Any]] = []
    for dx, dy in ((1, 2), (1, -2), (-1, 2), (-1, -2), (2, 1), (2, -1), (-2, 1), (-2, -1)):
        target = (source[0] + dx, source[1] + dy)
        if not (0 <= target[0] <= 8 and 0 <= target[1] <= 9):
            continue
        leg = (source[0] + (dx // 2 if abs(dx) == 2 else 0), source[1] + (dy // 2 if abs(dy) == 2 else 0))
        destination = board.get(target)
        blocked = leg in board or (destination is not None and destination.side == piece.side)
        options.append({"target": list(target), "leg": list(leg), "blocked": blocked, "legOccupied": leg in board})
    return options


def _elephant_options(board: Board, source: tuple[int, int]) -> list[dict[str, Any]]:
    piece = board.get(source)
    if not piece or piece.type != "bishop":
        return []
    options: list[dict[str, Any]] = []
    for dx, dy in ((2, 2), (2, -2), (-2, 2), (-2, -2)):
        target = (source[0] + dx, source[1] + dy)
        if not (0 <= target[0] <= 8 and 0 <= target[1] <= 9):
            continue
        eye = (source[0] + dx // 2, source[1] + dy // 2)
        destination = board.get(target)
        beyond_river = target[1] <= 4 if piece.side == "red" else target[1] >= 5
        blocked = eye in board or beyond_river or (destination is not None and destination.side == piece.side)
        options.append({"target": list(target), "eye": list(eye), "blocked": blocked, "eyeOccupied": eye in board, "beyondRiver": beyond_river})
    return options


def _legal_destinations(board: Board, source: tuple[int, int]) -> list[list[int]]:
    piece = board.get(source)
    if not piece:
        return []
    destinations: list[list[int]] = []
    for x in range(9):
        for y in range(10):
            target = (x, y)
            destination = board.get(target)
            if destination is not None and destination.side == piece.side:
                continue
            if destination is not None and destination.type == "king":
                continue
            if not _piece_geometry_is_legal(board, source, target, piece, destination):
                continue
            candidate = _copy_board(board)
            captured = _apply_move(candidate, source, target, piece)
            if is_in_check(candidate, piece.side):
                # Restore is unnecessary because candidate is discarded.
                _ = captured
                continue
            destinations.append([x, y])
    return destinations


def _snapshot(board: Board) -> dict[str, Any]:
    pieces = [
        {"at": [point[0], point[1]], "side": piece.side, "type": piece.type}
        for point, piece in sorted(board.items())
    ]
    horses = []
    elephants = []
    for point, piece in sorted(board.items()):
        if piece.type == "knight":
            horses.append({"at": list(point), "side": piece.side, "options": _horse_options(board, point)})
        elif piece.type == "bishop":
            elephants.append({"at": list(point), "side": piece.side, "options": _elephant_options(board, point)})
    return {"pieces": pieces, "horses": horses, "elephants": elephants}


def build_position_trace(fen: str, moves: list[Mapping[str, Any]] | None) -> dict[str, Any]:
    legal = validate_move_sequence(fen, moves or [])
    if not legal.get("ok"):
        return {"ok": False, "errors": list(legal.get("errors") or []), "plies": []}
    board, _ = parse_fen(fen)
    plies: list[dict[str, Any]] = []
    for move in legal.get("moves") or []:
        before_board = _copy_board(board)
        source = _point(move.get("from"))
        target = _point(move.get("to"))
        if source is None or target is None:
            return {"ok": False, "errors": [f"trace has invalid coordinates at ply {move.get('ply')}"], "plies": plies}
        moving_piece = board.get(source)
        if moving_piece is None:
            return {"ok": False, "errors": [f"trace has no piece at source at ply {move.get('ply')}"], "plies": plies}
        captured = _apply_trace_move(board, move)
        plies.append({
            "ply": int(move.get("ply")),
            "move": dict(move),
            "before": _snapshot(before_board),
            "after": _snapshot(board),
            "beforeBoard": before_board,
            "afterBoard": _copy_board(board),
            "sourcePiece": {"side": moving_piece.side, "type": moving_piece.type},
            "captured": captured.type if captured else None,
        })
    return {"ok": True, "errors": [], "plies": plies}


def _find_option(options: list[dict[str, Any]], target: list[int] | None, key: str) -> dict[str, Any] | None:
    for option in options:
        if target is None or option.get("target") == target:
            return option
    return None


def _relation_delta(before: dict[str, Any], after: dict[str, Any], piece_type: str) -> dict[str, Any]:
    key = "horses" if piece_type == "knight" else "elephants"
    before_map = {tuple(item["at"]): item for item in before.get(key, [])}
    after_map = {tuple(item["at"]): item for item in after.get(key, [])}
    return {"before": before_map, "after": after_map}


def _claim_for_ply(trace: dict[str, Any], claim: Mapping[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    try:
        ply = int(claim.get("ply"))
    except (TypeError, ValueError):
        return False, "claim has no valid ply", {}
    entry = next((item for item in trace.get("plies", []) if item.get("ply") == ply), None)
    if entry is None:
        return False, f"claim references missing ply={ply}", {}
    claim_type = str(claim.get("claimType") or "").strip()
    if claim_type not in CLAIM_TYPES:
        return False, f"unsupported claimType={claim_type}", {}
    position = str(claim.get("position") or "after").lower()
    board = entry["beforeBoard"] if position == "before" else entry["afterBoard"]
    subject_at = _point((claim.get("subject") or {}).get("at") if isinstance(claim.get("subject"), dict) else claim.get("subjectAt"))
    if claim_type == "legal_move":
        return True, "legal move is present in validated trace", {"claimType": claim_type, "ply": ply, "verified": True}
    if subject_at is None:
        return False, f"{claim_type} claim has no subject.at", {}
    subject_piece = board.get(subject_at)
    expected_type = {"horse_leg_block": "knight", "horse_leg_open": "knight", "elephant_eye_block": "bishop", "elephant_eye_open": "bishop", "cannon_screen": "cannon", "river_limit": "bishop"}.get(claim_type)
    if expected_type and (subject_piece is None or subject_piece.type != expected_type):
        return False, f"{claim_type} subject {list(subject_at)} is not a {expected_type}", {}
    if claim_type in {"horse_leg_block", "horse_leg_open"}:
        options = _horse_options(board, subject_at)
        option = _find_option(options, claim.get("target"), "leg")
        if option is None:
            return False, "horse claim target is not a geometric Horse destination", {}
        blocker = _point((claim.get("blocker") or {}).get("at") if isinstance(claim.get("blocker"), dict) else claim.get("blockerAt"))
        if claim_type == "horse_leg_block":
            if not option.get("blocked") or (blocker is not None and blocker != tuple(option["leg"])):
                return False, f"Horse Leg is not blocked at {option['leg']}", {"option": option}
        else:
            if option.get("blocked"):
                return False, f"Horse Leg is blocked at {option['leg']}; claim says open", {"option": option}
        return True, f"Horse Leg relation verified at {option['leg']}", {"claimType": claim_type, "ply": ply, "subjectAt": list(subject_at), "option": option, "verified": True}
    if claim_type in {"elephant_eye_block", "elephant_eye_open"}:
        options = _elephant_options(board, subject_at)
        option = _find_option(options, claim.get("target"), "eye")
        if option is None:
            return False, "Elephant Eye claim target is not a geometric Elephant destination", {}
        if claim_type == "elephant_eye_block" and not option.get("blocked"):
            return False, f"Elephant path is not blocked at {option['eye']}", {"option": option}
        if claim_type == "elephant_eye_open" and option.get("blocked"):
            return False, f"Elephant path is blocked at {option['eye']}", {"option": option}
        return True, f"Elephant Eye relation verified at {option['eye']}", {"claimType": claim_type, "ply": ply, "subjectAt": list(subject_at), "option": option, "verified": True}
    if claim_type == "cannon_screen":
        target = _point(claim.get("target"))
        if target is None or subject_at[0] != target[0] and subject_at[1] != target[1]:
            return False, "Cannon Screen claim target is not on the cannon line", {}
        between = []
        sx, sy = subject_at
        tx, ty = target
        step_x = 0 if sx == tx else (1 if tx > sx else -1)
        step_y = 0 if sy == ty else (1 if ty > sy else -1)
        x, y = sx + step_x, sy + step_y
        while (x, y) != target:
            if (x, y) in board:
                between.append([x, y])
            x += step_x
            y += step_y
        expected = claim.get("expectedScreens")
        if expected is not None and len(between) != int(expected):
            return False, f"Cannon line has {len(between)} screens, expected {expected}", {"screens": between}
        if len(between) != 1:
            return False, f"Cannon capture requires exactly one screen, found {len(between)}", {"screens": between}
        return True, "Cannon Screen relation verified", {"claimType": claim_type, "ply": ply, "subjectAt": list(subject_at), "target": list(target), "screens": between, "verified": True}
    if claim_type == "river_limit":
        if subject_piece is None or subject_piece.type != "bishop":
            return False, "river_limit subject is not an Elephant", {}
        targets = _legal_destinations(board, subject_at)
        illegal_crossing = [target for target in (claim.get("targetCandidates") or []) if target not in targets]
        if not illegal_crossing:
            return False, "river_limit claim has no mechanically rejected crossing target", {"legalDestinations": targets}
        return True, "Elephant river limit verified", {"claimType": claim_type, "ply": ply, "subjectAt": list(subject_at), "rejectedTargets": illegal_crossing, "verified": True}
    if claim_type == "flying_general":
        kings = [item["at"] for item in entry["after"].get("pieces", []) if item.get("type") == "king"]
        if len(kings) != 2 or kings[0][0] != kings[1][0]:
            return False, "Generals do not share a file after this ply", {}
        return False, "A facing-general position is illegal and cannot be used as a positive teaching claim", {}
    if claim_type == "legal_destinations":
        destinations = _legal_destinations(board, subject_at)
        claimed = claim.get("destinations") or []
        if sorted(destinations) != sorted(claimed):
            return False, "claimed legal destinations differ from mechanical destinations", {"actual": destinations, "claimed": claimed}
        return True, "legal destinations verified", {"claimType": claim_type, "ply": ply, "subjectAt": list(subject_at), "destinations": destinations, "verified": True}
    return False, f"claim type {claim_type} was not evaluated", {}


def verify_claims(fen: str, moves: list[Mapping[str, Any]] | None, claims_by_ply: Mapping[int, list[Mapping[str, Any]]] | None) -> dict[str, Any]:
    trace = build_position_trace(fen, moves)
    if not trace.get("ok"):
        return {"ok": False, "errors": list(trace.get("errors") or []), "proofs": [], "contract": CLAIM_CONTRACT}
    errors: list[str] = []
    proofs: list[dict[str, Any]] = []
    for ply, claims in (claims_by_ply or {}).items():
        if not isinstance(claims, list) or not claims:
            errors.append(f"ply={ply} has no claims")
            continue
        for claim in claims:
            if not isinstance(claim, Mapping):
                errors.append(f"ply={ply} contains non-object claim")
                continue
            ok, reason, proof = _claim_for_ply(trace, claim)
            if not ok:
                errors.append(f"ply={ply}: {reason}")
            else:
                proofs.append(proof)
    return {"ok": not errors, "errors": errors, "proofs": proofs, "contract": CLAIM_CONTRACT, "trace": [{"ply": item["ply"], "before": item["before"], "after": item["after"]} for item in trace.get("plies", [])]}


def build_verified_claims(fen: str, moves: list[Mapping[str, Any]] | None) -> tuple[dict[int, list[dict[str, Any]]], dict[str, Any]]:
    trace = build_position_trace(fen, moves)
    if not trace.get("ok"):
        raise ValueError("Cannot build Xiangqi claim proof: " + "; ".join(trace.get("errors") or []))
    claims: dict[int, list[dict[str, Any]]] = {}
    for entry in trace.get("plies", []):
        ply = int(entry["ply"])
        move = entry["move"]
        claims[ply] = [{
            "claimType": "legal_move",
            "ply": ply,
            "position": "after",
            "statement": f"The supplied move {move.get('from')} to {move.get('to')} is legal in the traced position.",
        }]
        source = _point(move.get("to"))
        if source is not None:
            destinations = _legal_destinations(entry["afterBoard"], source)
            claims[ply].append({
                "claimType": "legal_destinations",
                "ply": ply,
                "position": "after",
                "subject": {"at": list(source)},
                "destinations": destinations,
                "statement": f"The moved piece has {len(destinations)} mechanically legal destinations after the move.",
            })
    verified = verify_claims(fen, moves, claims)
    if not verified.get("ok"):
        raise ValueError("Generated Xiangqi claim proof failed: " + "; ".join(verified.get("errors") or []))
    return claims, verified


def suspicious_claim_language(move: Mapping[str, Any]) -> bool:
    text = " ".join(str(move.get(field) or "") for field in ("purpose", "opponentReply", "effect", "label"))
    return bool(_SUSPICIOUS_CAUSAL_LANGUAGE.search(text))
