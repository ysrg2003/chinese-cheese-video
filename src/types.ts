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
  animationStartSec?: number;
  animationEndSec?: number;
  label: string;
  spokenText?: string;
  captionText?: string;
  purpose?: string;
  opponentReply?: string;
  effect?: string;
  captured?: PieceType;
};

export type CaptionCue = {
  startSec: number;
  endSec: number;
  text: string;
  kind?: "intro" | "move" | "speech";
  movePly?: number;
  captionPosition?: "bottom" | "board";
  source?: string;
};

export type NarrationSegment = {
  kind: "intro" | "move";
  text: string;
  captionText?: string;
  captionPosition?: "bottom" | "board";
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
  objective?: string;
  analysis_focus?: string;
  curriculum_lesson_key?: string;
  curriculum_sequence?: number;
  curriculum_stage?: string;
  difficulty?: string;
  format?: string;
  playlist_key?: string;
  visual_mode?: "static_board" | "board_introduction" | "setup_overview";
  visual_focus?: string;
};

export const BOARD_COLUMNS = 9;
export const BOARD_ROWS = 10;
