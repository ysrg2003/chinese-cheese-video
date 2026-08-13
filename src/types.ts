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

export type VisualKind =
  | "battlefield"
  | "two_armies"
  | "generals_goal"
  | "intersections"
  | "river_palaces"
  | "cannon_geometry"
  | "learning_roadmap"
  | "board_overview"
  | "army_setup"
  | "piece_movement"
  | "move_path"
  | "attack_line"
  | "defense_zone"
  | "threat_marker"
  | "capture_sequence"
  | "cannon_screen"
  | "before_after"
  | "comparison_split"
  | "game_phase"
  | "question_reveal"
  | "result_summary";

export type VisualStoryboardScene = {
  index: number;
  segmentIndex?: number;
  movePly?: number | null;
  visualKind: VisualKind;
  headline: string;
  narration: string;
  caption: string;
  visualInstruction?: string;
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
  sceneId?: number;
  visualKind?: VisualStoryboardScene["visualKind"];
  headline?: string;
  visualInstruction?: string;
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
  visual_mode?: "static_board" | "foundation_storyboard" | "board_introduction" | "setup_overview" | "storyboard";
  visual_focus?: string;
  visualStoryboard?: VisualStoryboardScene[];
  visualStoryboardSource?: "ai_router" | "provided_ai" | "fallback";
};

export const BOARD_COLUMNS = 9;
export const BOARD_ROWS = 10;
