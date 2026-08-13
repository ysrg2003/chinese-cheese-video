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
