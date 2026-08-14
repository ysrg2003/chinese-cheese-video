import type { BoardPiece, BoardPoint, Move, PieceType, Side, VideoJob } from "./types";

const FEN_TYPES: Record<string, PieceType> = {
  k: "king",
  a: "advisor",
  e: "bishop",
  b: "bishop",
  h: "knight",
  n: "knight",
  r: "rook",
  c: "cannon",
  p: "pawn",
};

export function parseFen(fen: string): BoardPiece[] {
  const placement = fen.trim().split(" ")[0];
  const ranks = placement.split("/");
  if (ranks.length !== 10) {
    throw new Error(`Xiangqi FEN must contain 10 ranks; received ${ranks.length}`);
  }

  const pieces: BoardPiece[] = [];
  ranks.forEach((rank, row) => {
    let column = 0;
    for (const token of rank) {
      if (/\d/.test(token)) {
        column += Number(token);
        continue;
      }
      const type = FEN_TYPES[token.toLowerCase()];
      if (!type || column > 8) {
        throw new Error(`Unsupported FEN token "${token}" in rank ${row}`);
      }
      const side: Side = token === token.toUpperCase() ? "red" : "black";
      pieces.push({
        id: `${side}-${type}-${row}-${column}`,
        side,
        type,
        position: [column, row],
      });
      column += 1;
    }
    if (column !== 9) {
      throw new Error(`FEN rank ${row} has ${column} columns; expected 9`);
    }
  });
  return pieces;
}

function samePoint(a: BoardPoint, b: BoardPoint): boolean {
  return a[0] === b[0] && a[1] === b[1];
}

function findAt(pieces: BoardPiece[], point: BoardPoint): BoardPiece | undefined {
  return pieces.find((piece) => samePoint(piece.position, point));
}

function applyCompletedMove(pieces: BoardPiece[], move: Move): void {
  const moving = findAt(pieces, move.from);
  if (!moving) return;
  const captured = findAt(pieces, move.to);
  if (captured && captured.id !== moving.id) {
    pieces.splice(pieces.indexOf(captured), 1);
  }
  moving.position = [...move.to];
}

export function boardAtSecond(job: VideoJob, second: number): BoardPiece[] {
  const pieces = parseFen(job.fen).map((piece) => ({ ...piece, position: [...piece.position] as BoardPoint }));
  const sortedMoves = [...job.moves].sort((a, b) => a.ply - b.ply);

  for (const move of sortedMoves) {
    if (second < move.startSec) break;
    const moving = findAt(pieces, move.from);
    if (!moving) continue;
    if (second >= move.endSec) {
      applyCompletedMove(pieces, move);
      continue;
    }
    const animationStart = move.animationStartSec ?? move.startSec;
    const animationEnd = Math.max(animationStart + 0.05, move.animationEndSec ?? move.endSec);
    if (second < animationStart) break;
    if (second >= animationEnd) {
      applyCompletedMove(pieces, move);
      continue;
    }
    const progress = Math.max(0, Math.min(1, (second - animationStart) / Math.max(0.001, animationEnd - animationStart)));
    const captured = findAt(pieces, move.to);
    if (captured && captured.id !== moving.id && progress > 0.65) {
      pieces.splice(pieces.indexOf(captured), 1);
    }
    moving.position = [
      move.from[0] + (move.to[0] - move.from[0]) * progress,
      move.from[1] + (move.to[1] - move.from[1]) * progress,
    ];
    break;
  }
  return pieces;
}

export function activeMoveAtSecond(job: VideoJob, second: number): Move | undefined {
  return job.moves.find((move) => second >= move.startSec && second <= move.endSec);
}

const DIRECTIONS: BoardPoint[] = [[1, 0], [-1, 0], [0, 1], [0, -1]];

function inBoard(point: BoardPoint): boolean {
  return point[0] >= 0 && point[0] < 9 && point[1] >= 0 && point[1] < 10;
}

function inPalace(side: Side, point: BoardPoint): boolean {
  const [file, rank] = point;
  return file >= 3 && file <= 5 && (side === "red" ? rank >= 7 : rank <= 2);
}

function canLand(pieces: BoardPiece[], piece: BoardPiece, point: BoardPoint): boolean {
  const occupant = findAt(pieces, point);
  return !occupant || occupant.side !== piece.side;
}

function pathClear(pieces: BoardPiece[], from: BoardPoint, to: BoardPoint): boolean {
  const fileStep = Math.sign(to[0] - from[0]);
  const rankStep = Math.sign(to[1] - from[1]);
  let file = from[0] + fileStep;
  let rank = from[1] + rankStep;
  while (file !== to[0] || rank !== to[1]) {
    if (findAt(pieces, [file, rank])) return false;
    file += fileStep;
    rank += rankStep;
  }
  return true;
}

function pseudoDestinations(piece: BoardPiece, pieces: BoardPiece[]): BoardPoint[] {
  const [file, rank] = piece.position;
  const candidates: BoardPoint[] = [];
  const add = (point: BoardPoint) => {
    if (inBoard(point) && canLand(pieces, piece, point)) candidates.push(point);
  };

  if (piece.type === "king") {
    for (const [df, dr] of DIRECTIONS) {
      const target: BoardPoint = [file + df, rank + dr];
      if (inPalace(piece.side, target)) add(target);
    }
    return candidates;
  }

  if (piece.type === "advisor") {
    for (const [df, dr] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) {
      const target: BoardPoint = [file + df, rank + dr];
      if (inPalace(piece.side, target)) add(target);
    }
    return candidates;
  }

  if (piece.type === "bishop") {
    for (const [df, dr] of [[2, 2], [2, -2], [-2, 2], [-2, -2]]) {
      const target: BoardPoint = [file + df, rank + dr];
      const eye: BoardPoint = [file + df / 2, rank + dr / 2];
      const remainsHome = piece.side === "red" ? target[1] >= 5 : target[1] <= 4;
      if (remainsHome && inBoard(target) && !findAt(pieces, eye)) add(target);
    }
    return candidates;
  }

  if (piece.type === "knight") {
    for (const [df, dr, lf, lr] of [[1, 2, 0, 1], [1, -2, 0, -1], [-1, 2, 0, 1], [-1, -2, 0, -1], [2, 1, 1, 0], [2, -1, 1, 0], [-2, 1, -1, 0], [-2, -1, -1, 0]]) {
      const leg: BoardPoint = [file + lf, rank + lr];
      const target: BoardPoint = [file + df, rank + dr];
      if (inBoard(target) && !findAt(pieces, leg)) add(target);
    }
    return candidates;
  }

  if (piece.type === "pawn") {
    const forward = piece.side === "red" ? -1 : 1;
    add([file, rank + forward]);
    const crossedRiver = piece.side === "red" ? rank <= 4 : rank >= 5;
    if (crossedRiver) {
      add([file - 1, rank]);
      add([file + 1, rank]);
    }
    return candidates;
  }

  for (const [df, dr] of DIRECTIONS) {
    let target: BoardPoint = [file + df, rank + dr];
    let screens = 0;
    while (inBoard(target)) {
      const occupant = findAt(pieces, target);
      if (piece.type === "cannon") {
        if (screens === 0) {
          if (!occupant) candidates.push(target);
          else screens = 1;
        } else if (occupant) {
          if (occupant.side !== piece.side) candidates.push(target);
          break;
        }
      } else if (!occupant) {
        candidates.push(target);
      } else {
        if (occupant.side !== piece.side) candidates.push(target);
        break;
      }
      target = [target[0] + df, target[1] + dr];
    }
  }
  return candidates.filter((point) => canLand(pieces, piece, point));
}

function generalOf(pieces: BoardPiece[], side: Side): BoardPiece | undefined {
  return pieces.find((piece) => piece.type === "king" && piece.side === side);
}

function generalsFace(pieces: BoardPiece[]): boolean {
  const red = generalOf(pieces, "red");
  const black = generalOf(pieces, "black");
  return Boolean(red && black && red.position[0] === black.position[0] && pathClear(pieces, red.position, black.position));
}

function isInCheck(pieces: BoardPiece[], side: Side): boolean {
  const general = generalOf(pieces, side);
  if (!general) return true;
  if (generalsFace(pieces)) return true;
  const opponent = side === "red" ? "black" : "red";
  return pieces.some((piece) => piece.side === opponent && pseudoDestinations(piece, pieces).some((target) => samePoint(target, general.position)));
}

function applyCandidate(pieces: BoardPiece[], piece: BoardPiece, target: BoardPoint): BoardPiece[] {
  const next = pieces.filter((candidate) => !samePoint(candidate.position, target)).map((candidate) => ({ ...candidate, position: [...candidate.position] as BoardPoint }));
  const moving = next.find((candidate) => candidate.id === piece.id);
  if (moving) moving.position = [...target];
  return next;
}

export function legalDestinationsForPiece(pieces: BoardPiece[], origin: BoardPoint): BoardPoint[] {
  const piece = findAt(pieces, origin);
  if (!piece) return [];
  return pseudoDestinations(piece, pieces)
    .filter((target, index, all) => all.findIndex((candidate) => samePoint(candidate, target)) === index)
    .filter((target) => !isInCheck(applyCandidate(pieces, piece, target), piece.side));
}
