export type Side = "red" | "black";

export type PieceType =
  | "king"
  | "advisor"
  | "bishop"
  | "knight"
  | "rook"
  | "cannon"
  | "pawn";

export type BoardPoint = [number, number];

export type BoardPiece = {
  id: string;
  side: Side;
  type: PieceType;
  position: BoardPoint;
};

export type Move = {
  ply: number;
  from: BoardPoint;
  to: BoardPoint;
  piece: PieceType;
  side: Side;
  startSec: number;
  endSec: number;
  label: string;
  spokenText?: string;
  captured?: PieceType;
};

export type CaptionCue = {
  startSec: number;
  endSec: number;
  text: string;
  kind?: "intro" | "move" | "speech";
  movePly?: number;
  source?: string;
};

export type NarrationSegment = {
  kind: "intro" | "move";
  text: string;
  movePly?: number;
  startSec?: number;
  endSec?: number;
  source?: string;
};

export type VideoJob = {
  id: string;
  title: string;
  language: "en" | "zh";
  fen: string;
  narration: string;
  moves: Move[];
  captions: CaptionCue[];
  narrationSegments?: NarrationSegment[];
  captions_source?: string;
  audioSrc: string;
  durationInSeconds: number;
  theme?: "wood" | "paper";
};

export const BOARD_COLUMNS = 9;
export const BOARD_ROWS = 10;
