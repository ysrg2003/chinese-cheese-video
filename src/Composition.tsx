import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { BoardPiece, Move, VideoJob } from "./types";
import { activeMoveAtSecond, boardAtSecond } from "./xq";

const COLORS = {
  ink: "#211a16",
  paper: "#f6ecd7",
  paperDark: "#e3c79d",
  red: "#b63c2f",
  black: "#302c2a",
  gold: "#c58a3a",
  line: "#7f4d2f",
};

const UI_COPY = {
  en: {
    subtitle: "Fast tactical analysis in Xiangqi",
    move: "Move",
    footer: "xiangqi",
    seconds: "s",
  },
  zh: {
    subtitle: "中国象棋快速战术分析",
    move: "第",
    footer: "中国象棋",
    seconds: "秒",
  },
} as const;

const board = {
  x: 70,
  y: 390,
  width: 940,
  height: 1040,
};

const cell = 104;
const grid = {
  x: board.x + 2,
  y: board.y + 2,
  width: cell * 8,
  height: cell * 9,
};

function pieceAsset(piece: BoardPiece): string {
  const fileName = `${piece.side}_${piece.type}.svg`;
  return staticFile(`assets/pieces/${fileName}`);
}

function Board({ job, second }: { job: VideoJob; second: number }) {
  const pieces = boardAtSecond(job, second);
  const active = activeMoveAtSecond(job, second);
  const activeFrom = active ? active.from : undefined;
  const activeTo = active ? active.to : undefined;

  return (
    <div
      style={{
        position: "absolute",
        left: board.x,
        top: board.y,
        width: board.width,
        height: board.height,
        borderRadius: 30,
        background: "linear-gradient(145deg, #d6a869, #b4773d)",
        boxShadow: "0 22px 50px rgba(44, 25, 10, 0.32)",
        padding: 26,
        boxSizing: "border-box",
      }}
    >
      <svg width={grid.width + 4} height={grid.height + 4} viewBox={`0 0 ${grid.width + 4} ${grid.height + 4}`}>
        <rect x={0} y={0} width={grid.width + 4} height={grid.height + 4} rx={10} fill="#e7c18a" />
        {Array.from({ length: 10 }).map((_, row) => (
          <line
            key={`row-${row}`}
            x1={2}
            y1={2 + row * cell}
            x2={grid.width + 2}
            y2={2 + row * cell}
            stroke={COLORS.line}
            strokeWidth={4}
          />
        ))}
        {Array.from({ length: 9 }).map((_, column) => (
          <line
            key={`col-${column}`}
            x1={2 + column * cell}
            y1={2}
            x2={2 + column * cell}
            y2={grid.height + 2}
            stroke={COLORS.line}
            strokeWidth={4}
          />
        ))}
        <line x1={2} y1={2} x2={2 + 2 * cell} y2={2 + 2 * cell} stroke={COLORS.line} strokeWidth={4} />
        <line x1={2 + 2 * cell} y1={2} x2={2} y2={2 + 2 * cell} stroke={COLORS.line} strokeWidth={4} />
        <line x1={2} y1={2 + 7 * cell} x2={2 + 2 * cell} y2={2 + 9 * cell} stroke={COLORS.line} strokeWidth={4} />
        <line x1={2 + 2 * cell} y1={2 + 7 * cell} x2={2} y2={2 + 9 * cell} stroke={COLORS.line} strokeWidth={4} />
        <text x={grid.width / 2} y={5 * cell + 12} fill={COLORS.line} textAnchor="middle" fontSize={34} fontFamily="serif" opacity={0.74}>
          楚 河　　　　　　 漢 界
        </text>
        {activeFrom && (
          <circle cx={2 + activeFrom[0] * cell} cy={2 + activeFrom[1] * cell} r={32} fill="none" stroke={COLORS.gold} strokeWidth={8} opacity={0.9} />
        )}
        {activeTo && (
          <circle cx={2 + activeTo[0] * cell} cy={2 + activeTo[1] * cell} r={32} fill="none" stroke={COLORS.red} strokeWidth={8} opacity={0.9} />
        )}
      </svg>
      {pieces.map((piece) => {
        const [column, row] = piece.position;
        return (
          <Img
            key={piece.id}
            src={pieceAsset(piece)}
            style={{
              position: "absolute",
              width: 94,
              height: 94,
              objectFit: "contain",
              left: 26 + column * cell - 47,
              top: 26 + row * cell - 47,
              filter: active?.to[0] === column && active?.to[1] === row ? "drop-shadow(0 0 18px rgba(255, 231, 143, .95))" : "drop-shadow(0 8px 5px rgba(67, 32, 8, .35))",
            }}
          />
        );
      })}
    </div>
  );
}

function Caption({ job, second }: { job: VideoJob; second: number }) {
  const cue = job.captions.find((item) => second >= item.startSec && second < item.endSec);
  if (!cue) return null;
  const isIntro = cue.captionPosition === "bottom" || cue.kind === "intro";
  return (
    <div
      style={{
        position: "absolute",
        top: isIntro ? undefined : 342,
        bottom: isIntro ? 112 : undefined,
        left: isIntro ? 82 : 104,
        right: isIntro ? 82 : 104,
        minHeight: isIntro ? 54 : 42,
        maxHeight: isIntro ? 170 : 72,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: isIntro ? "12px 22px" : "8px 18px",
        borderRadius: 16,
        background: isIntro ? "rgba(31, 22, 17, .78)" : "rgba(31, 22, 17, .82)",
        color: "#fff8e9",
        fontFamily: job.language === "zh" ? "Noto Sans CJK SC, Noto Sans SC, Arial, sans-serif" : "Arial, sans-serif",
        fontSize: isIntro ? 24 : 22,
        lineHeight: 1.18,
        fontWeight: 700,
        direction: "ltr",
        overflow: "hidden",
        whiteSpace: "normal",
      }}
    >
      {cue.text}
    </div>
  );
}

function pointLabel(point: [number, number]): string {
  return `F${point[0] + 1}R${point[1] + 1}`;
}

function pieceLabel(piece: Move["piece"]): string {
  return {
    pawn: "Pawn",
    rook: "Rook",
    knight: "Horse",
    bishop: "Elephant",
    advisor: "Advisor",
    king: "General",
    cannon: "Cannon",
  }[piece];
}

function MoveCard({ move, second, language }: { move?: Move; second: number; language: VideoJob["language"] }) {
  const opacity = move ? interpolate(second, [move.startSec - 0.25, move.startSec, move.endSec, move.endSec + 0.35], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 0;
  if (!move) return null;
  const copy = UI_COPY[language];
  const moveText = `${pieceLabel(move.piece)} ${pointLabel(move.from)}→${pointLabel(move.to)}`;
  return (
    <div
      style={{
        position: "absolute",
        top: 258,
        left: 74,
        right: 74,
        display: "flex",
        justifyContent: "center",
        opacity,
        direction: "ltr",
      }}
    >
      <div style={{ background: COLORS.red, color: "#fff9ed", borderRadius: 22, padding: "10px 26px", fontSize: 28, lineHeight: 1.15, fontWeight: 800, boxShadow: "0 12px 24px rgba(92, 20, 14, .25)" }}>
        <span>{language === "zh" ? `${copy.move}${move.ply}` : `${copy.move} ${move.ply}`} • {moveText}</span>
        <span style={{ display: "block", marginTop: 4, fontSize: 20, fontWeight: 600, opacity: 0.92 }}>{move.label}</span>
      </div>
    </div>
  );
}

export const XiangqiComposition: React.FC<VideoJob> = (job) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const second = frame / fps;
  const active = activeMoveAtSecond(job, second);
  const copy = UI_COPY[job.language];
  const introOpacity = interpolate(frame, [0, 18, 42], [0, 1, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const titleScale = interpolate(frame, [0, 36], [0.92, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ background: COLORS.paper, color: COLORS.ink, fontFamily: "Arial, sans-serif" }}>
      <AbsoluteFill style={{ background: "radial-gradient(circle at 50% 10%, #fff8e8 0%, #f5e6ca 48%, #e2c18d 100%)" }} />
      <div style={{ position: "absolute", top: 72, left: 72, right: 72, textAlign: "center", direction: "ltr", opacity: introOpacity, transform: `scale(${titleScale})` }}>
        <div style={{ fontSize: 28, letterSpacing: 7, color: COLORS.red, fontWeight: 800 }}>CHINESE CHEESE VIDEO</div>
        <div style={{ marginTop: 16, fontSize: 58, fontWeight: 900, lineHeight: 1.15 }}>{job.title}</div>
        <div style={{ marginTop: 14, fontSize: 26, color: "#76543b", fontFamily: job.language === "zh" ? "Noto Sans CJK SC, Noto Sans SC, Arial, sans-serif" : "Arial, sans-serif" }}>{copy.subtitle}</div>
      </div>
      <Board job={job} second={second} />
      <MoveCard move={active} second={second} language={job.language} />
      <Caption job={job} second={second} />
      {job.audioSrc ? <Audio src={staticFile(job.audioSrc)} volume={1} /> : null}
      <div style={{ position: "absolute", left: 76, right: 76, bottom: 52, display: "flex", justifyContent: "space-between", color: "#795a3e", fontSize: 23, direction: "ltr" }}>
        <span>{copy.footer} • {job.language.toUpperCase()}</span>
        <span>{Math.max(0, Math.ceil(job.durationInSeconds - second))}{copy.seconds}</span>
      </div>
    </AbsoluteFill>
  );
};
