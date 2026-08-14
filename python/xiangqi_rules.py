from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

BOARD_WIDTH = 9
BOARD_HEIGHT = 10


class IllegalPositionError(ValueError):
    """Raised when a FEN position cannot be used as a Xiangqi position."""


class IllegalMoveError(ValueError):
    """Raised when a proposed Xiangqi move is illegal."""


@dataclass(frozen=True)
class Piece:
    side: str
    type: str


Point = tuple[int, int]
Board = dict[Point, Piece]


FEN_TYPES = {
    "k": "king",
    "g": "king",
    "a": "advisor",
    "s": "advisor",
    "e": "bishop",
    "b": "bishop",
    "h": "knight",
    "n": "knight",
    "r": "rook",
    "c": "cannon",
    "p": "pawn",
}

PIECE_ALIASES = {
    "king": "king", "general": "king", "k": "king", "将": "king", "將": "king", "帅": "king", "帥": "king",
    "advisor": "advisor", "guard": "advisor", "a": "advisor", "s": "advisor", "士": "advisor", "仕": "advisor",
    "bishop": "bishop", "elephant": "bishop", "e": "bishop", "b": "bishop", "象": "bishop", "相": "bishop",
    "knight": "knight", "horse": "knight", "h": "knight", "n": "knight", "马": "knight", "馬": "knight", "傌": "knight",
    "rook": "rook", "chariot": "rook", "r": "rook", "车": "rook", "車": "rook", "俥": "rook",
    "cannon": "cannon", "c": "cannon", "炮": "cannon", "砲": "cannon",
    "pawn": "pawn", "soldier": "pawn", "p": "pawn", "兵": "pawn", "卒": "pawn",
}


def normalize_side(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"red", "r", "white", "w", "红", "紅"}:
        return "red"
    if text in {"black", "b", "斜", "黑"}:
        return "black"
    raise IllegalMoveError(f"unsupported side: {value!r}")


def normalize_piece_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in PIECE_ALIASES:
        return PIECE_ALIASES[text]
    # Chinese aliases are case-independent only in the lookup above.
    raw = str(value or "").strip()
    if raw in PIECE_ALIASES:
        return PIECE_ALIASES[raw]
    raise IllegalMoveError(f"unsupported piece type: {value!r}")


def _inside(point: Point) -> bool:
    return 0 <= point[0] < BOARD_WIDTH and 0 <= point[1] < BOARD_HEIGHT


def _point(value: Any, field: str) -> Point:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise IllegalMoveError(f"{field} must be [column, row]")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        raise IllegalMoveError(f"{field} coordinates must be integers")
    point = (int(value[0]), int(value[1]))
    if not _inside(point):
        raise IllegalMoveError(f"{field} {list(point)} is outside the 9x10 board")
    return point


def _side_from_fen(token: str) -> str:
    text = token.strip().lower()
    if text in {"r", "red", "w", "white"}:
        return "red"
    if text in {"b", "black"}:
        return "black"
    raise IllegalPositionError(f"unsupported FEN side-to-move token: {token!r}")


def parse_fen(fen: str) -> tuple[Board, str]:
    parts = str(fen or "").strip().split()
    if not parts:
        raise IllegalPositionError("FEN is empty")
    ranks = parts[0].split("/")
    if len(ranks) != BOARD_HEIGHT:
        raise IllegalPositionError(f"FEN must contain 10 ranks; received {len(ranks)}")
    side_to_move = _side_from_fen(parts[1] if len(parts) > 1 else "r")
    board: Board = {}
    for row, rank in enumerate(ranks):
        column = 0
        for token in rank:
            if token.isdigit():
                column += int(token)
                continue
            if token.lower() not in FEN_TYPES:
                raise IllegalPositionError(f"unsupported FEN piece token {token!r} at row {row}")
            if column >= BOARD_WIDTH:
                raise IllegalPositionError(f"FEN rank {row} exceeds 9 columns")
            side = "red" if token.isupper() else "black"
            board[(column, row)] = Piece(side, FEN_TYPES[token.lower()])
            column += 1
        if column != BOARD_WIDTH:
            raise IllegalPositionError(f"FEN rank {row} has {column} columns; expected 9")
    _validate_position_invariants(board)
    return board, side_to_move


def _palace(side: str, point: Point) -> bool:
    x, y = point
    return 3 <= x <= 5 and ((side == "black" and 0 <= y <= 2) or (side == "red" and 7 <= y <= 9))


def _home_half(side: str, point: Point) -> bool:
    return point[1] <= 4 if side == "black" else point[1] >= 5


def _line_points(source: Point, target: Point) -> list[Point]:
    sx, sy = source
    tx, ty = target
    dx = 0 if sx == tx else (1 if tx > sx else -1)
    dy = 0 if sy == ty else (1 if ty > sy else -1)
    points: list[Point] = []
    x, y = sx + dx, sy + dy
    while (x, y) != target:
        points.append((x, y))
        x += dx
        y += dy
    return points


def _between_count(board: Board, source: Point, target: Point) -> int:
    return sum(1 for point in _line_points(source, target) if point in board)


def _line_clear(board: Board, source: Point, target: Point) -> bool:
    return _between_count(board, source, target) == 0


def _find_king(board: Board, side: str) -> Point:
    kings = [point for point, piece in board.items() if piece.side == side and piece.type == "king"]
    if len(kings) != 1:
        raise IllegalPositionError(f"position must contain exactly one {side} general; found {len(kings)}")
    return kings[0]


def _validate_position_invariants(board: Board) -> None:
    _find_king(board, "red")
    _find_king(board, "black")
    for point, piece in board.items():
        if piece.type in {"king", "advisor"} and not _palace(piece.side, point):
            raise IllegalPositionError(f"{piece.side} {piece.type} at {point} is outside its palace")
        if piece.type == "bishop" and not _home_half(piece.side, point):
            raise IllegalPositionError(f"{piece.side} elephant at {point} has crossed the river")
    red_king = _find_king(board, "red")
    black_king = _find_king(board, "black")
    if red_king[0] == black_king[0] and _line_clear(board, red_king, black_king):
        raise IllegalPositionError("the two generals face each other on an empty file")


def _attacks_square(board: Board, source: Point, target: Point, piece: Piece) -> bool:
    sx, sy = source
    tx, ty = target
    dx, dy = tx - sx, ty - sy
    adx, ady = abs(dx), abs(dy)
    if piece.type == "king":
        # A general attacks one adjacent orthogonal point. The only long-range
        # exception is the vertical flying-general line on the same file.
        return adx + ady == 1 or (sx == tx and _line_clear(board, source, target))
    if piece.type == "advisor":
        return adx == 1 and ady == 1 and _palace(piece.side, target)
    if piece.type == "bishop":
        if adx != 2 or ady != 2 or not _home_half(piece.side, target):
            return False
        return (sx + dx // 2, sy + dy // 2) not in board
    if piece.type == "knight":
        if (adx, ady) not in {(1, 2), (2, 1)}:
            return False
        leg = (sx + (dx // 2 if adx == 2 else 0), sy + (dy // 2 if ady == 2 else 0))
        return leg not in board
    if piece.type == "rook":
        return (sx == tx or sy == ty) and _line_clear(board, source, target)
    if piece.type == "cannon":
        return (sx == tx or sy == ty) and _between_count(board, source, target) == 1
    if piece.type == "pawn":
        forward = -1 if piece.side == "red" else 1
        if dx == 0 and dy == forward:
            return True
        crossed = sy <= 4 if piece.side == "red" else sy >= 5
        return crossed and adx == 1 and dy == 0
    return False


def is_in_check(board: Board, side: str) -> bool:
    king = _find_king(board, side)
    enemy = "black" if side == "red" else "red"
    return any(piece.side == enemy and _attacks_square(board, source, king, piece) for source, piece in board.items())


def _piece_geometry_is_legal(board: Board, source: Point, target: Point, piece: Piece, destination: Piece | None) -> bool:
    sx, sy = source
    tx, ty = target
    dx, dy = tx - sx, ty - sy
    adx, ady = abs(dx), abs(dy)
    if piece.type == "king":
        return adx + ady == 1 and _palace(piece.side, target)
    if piece.type == "advisor":
        return adx == 1 and ady == 1 and _palace(piece.side, source) and _palace(piece.side, target)
    if piece.type == "bishop":
        return adx == 2 and ady == 2 and _home_half(piece.side, target) and (sx + dx // 2, sy + dy // 2) not in board
    if piece.type == "knight":
        if (adx, ady) not in {(1, 2), (2, 1)}:
            return False
        leg = (sx + (dx // 2 if adx == 2 else 0), sy + (dy // 2 if ady == 2 else 0))
        return leg not in board
    if piece.type == "rook":
        return (sx == tx or sy == ty) and _line_clear(board, source, target)
    if piece.type == "cannon":
        if sx != tx and sy != ty:
            return False
        screens = _between_count(board, source, target)
        return screens == (1 if destination is not None else 0)
    if piece.type == "pawn":
        forward = -1 if piece.side == "red" else 1
        if dx == 0 and dy == forward:
            return True
        crossed = sy <= 4 if piece.side == "red" else sy >= 5
        return crossed and adx == 1 and dy == 0
    return False


def _apply_move(board: Board, source: Point, target: Point, piece: Piece) -> Piece | None:
    captured = board.pop(target, None)
    board.pop(source)
    board[target] = piece
    return captured


def validate_move_sequence(fen: str, moves: list[Mapping[str, Any]] | None) -> dict[str, Any]:
    board, side_to_move = parse_fen(fen)
    canonical_moves: list[dict[str, Any]] = []
    errors: list[str] = []
    raw_moves = list(moves or [])
    for index, raw in enumerate(raw_moves, start=1):
        if not isinstance(raw, Mapping):
            errors.append(f"ply {index}: move must be an object")
            break
        try:
            ply = int(raw.get("ply", index))
            if ply != index:
                raise IllegalMoveError(f"expected ply {index}, received {ply}")
            source = _point(raw.get("from"), "from")
            target = _point(raw.get("to"), "to")
            piece = board.get(source)
            if piece is None:
                raise IllegalMoveError(f"no piece at source {list(source)}")
            declared_side = normalize_side(raw.get("side", piece.side))
            if declared_side != piece.side:
                raise IllegalMoveError(f"declared side {declared_side} does not match source piece side {piece.side}")
            if piece.side != side_to_move:
                raise IllegalMoveError(f"it is {side_to_move}'s turn, not {piece.side}'s")
            declared_type = normalize_piece_type(raw.get("piece", piece.type))
            if declared_type != piece.type:
                raise IllegalMoveError(f"declared piece {declared_type} does not match actual {piece.type}")
            destination = board.get(target)
            if destination is not None and destination.side == piece.side:
                raise IllegalMoveError("destination is occupied by a friendly piece")
            if destination is not None and destination.type == "king":
                raise IllegalMoveError("a general is not captured directly; represent check or checkmate instead")
            if not _piece_geometry_is_legal(board, source, target, piece, destination):
                raise IllegalMoveError(f"{piece.type} geometry or blocker rule rejects {list(source)}->{list(target)}")
            captured = _apply_move(board, source, target, piece)
            if is_in_check(board, piece.side):
                board.pop(target, None)
                board[source] = piece
                if captured is not None:
                    board[target] = captured
                raise IllegalMoveError("move leaves the moving side's general in check")
            canonical_moves.append({
                "ply": ply,
                "from": list(source),
                "to": list(target),
                "piece": piece.type,
                "side": piece.side,
                "captured": captured.type if captured else None,
            })
            side_to_move = "black" if side_to_move == "red" else "red"
        except (IllegalMoveError, IllegalPositionError) as exc:
            errors.append(f"ply {index}: {exc}")
            break
    return {
        "ok": not errors,
        "errors": errors,
        "plies_checked": len(canonical_moves),
        "moves": canonical_moves,
        "side_to_move_after": side_to_move,
    }


def assert_legal_move_sequence(fen: str, moves: list[Mapping[str, Any]] | None) -> dict[str, Any]:
    result = validate_move_sequence(fen, moves)
    if not result["ok"]:
        raise IllegalMoveError("; ".join(result["errors"]))
    return result
