import {
  AbsoluteFill,
  Audio,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { BoardPiece, BoardPoint, Move, VideoJob, VisualStoryboardScene } from "./types";
import { activeMoveAtSecond, boardAtSecond } from "./xq";

const COLORS = {
  ink: "#211a16",
  paper: "#f6ecd7",
  red: "#b63c2f",
  black: "#302c2a",
  gold: "#c58a3a",
  line: "#7f4d2f",
  river: "#4a9ac2",
};

const UI_COPY = {
  en: { subtitle: "Fast tactical analysis in Xiangqi", move: "Move", footer: "xiangqi", seconds: "s" },
  zh: { subtitle: "中国象棋快速战术分析", move: "第", footer: "中国象棋", seconds: "秒" },
} as const;

const BOARD_PADDING = 26;
const board = { x: 70, y: 390, width: BOARD_PADDING * 2 + 8 * 104, height: BOARD_PADDING * 2 + 9 * 104 };
const cell = 104;
const grid = { x: board.x + BOARD_PADDING, y: board.y + BOARD_PADDING, width: cell * 8, height: cell * 9 };

type VisualKind = VisualStoryboardScene["visualKind"];

function pieceAsset(piece: BoardPiece): string {
  return staticFile(`assets/pieces/${piece.side}_${piece.type}.svg`);
}

function boardPoint(file: number, rank: number) {
  return { x: grid.x + file * cell, y: grid.y + rank * cell };
}

function Board({ job, second }: { job: VideoJob; second: number }) {
  const pieces = boardAtSecond(job, second);
  const active = activeMoveAtSecond(job, second);
  const activeFrom = active ? active.from : undefined;
  const activeTo = active ? active.to : undefined;

  const startingMarks: BoardPoint[] = [[1, 2], [7, 2], [1, 7], [7, 7], [0, 3], [2, 3], [4, 3], [6, 3], [8, 3], [0, 6], [2, 6], [4, 6], [6, 6], [8, 6]];
  const palace = (top: number) => <>
    <line x1={3 * cell} y1={top * cell} x2={5 * cell} y2={(top + 2) * cell} stroke={COLORS.line} strokeWidth={4} />
    <line x1={5 * cell} y1={top * cell} x2={3 * cell} y2={(top + 2) * cell} stroke={COLORS.line} strokeWidth={4} />
  </>;

  return (
    <div style={{ position: "absolute", left: board.x, top: board.y, width: board.width, height: board.height, borderRadius: 30, background: "linear-gradient(145deg, #d6a869, #b4773d)", boxShadow: "0 22px 50px rgba(44, 25, 10, 0.32)", padding: BOARD_PADDING, boxSizing: "border-box" }}>
      <svg width={grid.width} height={grid.height} viewBox={`0 0 ${grid.width} ${grid.height}`}>
        <rect x={0} y={0} width={grid.width} height={grid.height} rx={8} fill="#e7c18a" />
        <rect x={0} y={4 * cell} width={grid.width} height={cell} fill="#b47d45" opacity={0.42} />
        {Array.from({ length: 10 }).map((_, row) => (row <= 4 || row >= 5) ? <line key={`row-${row}`} x1={0} y1={row * cell} x2={grid.width} y2={row * cell} stroke={COLORS.line} strokeWidth={4} /> : null)}
        {Array.from({ length: 9 }).map((_, column) => <g key={`col-${column}`}><line x1={column * cell} y1={0} x2={column * cell} y2={4 * cell} stroke={COLORS.line} strokeWidth={4} /><line x1={column * cell} y1={5 * cell} x2={column * cell} y2={grid.height} stroke={COLORS.line} strokeWidth={4} /></g>)}
        <rect x={0} y={0} width={grid.width} height={grid.height} rx={8} fill="none" stroke={COLORS.line} strokeWidth={6} />
        {palace(0)}
        {palace(7)}
        {startingMarks.map(([column, row]) => <g key={`mark-${column}-${row}`} opacity={0.52} stroke={COLORS.line} strokeWidth={2}><line x1={column * cell - 9} y1={row * cell} x2={column * cell + 9} y2={row * cell} /><line x1={column * cell} y1={row * cell - 9} x2={column * cell} y2={row * cell + 9} /></g>)}
        <text x={2.15 * cell} y={4.5 * cell + 13} fill={COLORS.line} textAnchor="middle" fontSize={30} fontFamily="serif" fontWeight={700} opacity={0.9}>楚河</text>
        <text x={5.85 * cell} y={4.5 * cell + 13} fill={COLORS.line} textAnchor="middle" fontSize={30} fontFamily="serif" fontWeight={700} opacity={0.9}>漢界</text>
        {activeFrom && <circle cx={activeFrom[0] * cell} cy={activeFrom[1] * cell} r={34} fill="none" stroke={COLORS.gold} strokeWidth={8} opacity={0.9} />}
        {activeTo && <circle cx={activeTo[0] * cell} cy={activeTo[1] * cell} r={34} fill="none" stroke={COLORS.red} strokeWidth={8} opacity={0.9} />}
      </svg>
      {pieces.map((piece) => {
        const [column, row] = piece.position;
        return <Img key={piece.id} src={pieceAsset(piece)} style={{ position: "absolute", width: 94, height: 94, objectFit: "contain", left: BOARD_PADDING + column * cell - 47, top: BOARD_PADDING + row * cell - 47, filter: active?.to[0] === column && active?.to[1] === row ? "drop-shadow(0 0 18px rgba(255, 231, 143, .95))" : "drop-shadow(0 8px 5px rgba(67, 32, 8, .35))" }} />;
      })}
    </div>
  );
}

function Marker({ children, left, top, opacity = 1, tone = "gold" }: { children: React.ReactNode; left: number; top: number; opacity?: number; tone?: "gold" | "red" | "black" | "blue" }) {
  const palette = {
    gold: { background: "rgba(111, 70, 20, .91)", border: "#f8cf74" },
    red: { background: "rgba(148, 39, 31, .92)", border: "#ffd1b6" },
    black: { background: "rgba(31, 29, 30, .90)", border: "#d9d9d9" },
    blue: { background: "rgba(22, 81, 119, .91)", border: "#bde7ff" },
  }[tone];
  return <div style={{ position: "absolute", left, top, transform: "translate(-50%, -50%)", opacity, zIndex: 5, padding: "7px 12px", borderRadius: 999, background: palette.background, border: `2px solid ${palette.border}`, color: "#fff9ed", fontSize: 18, lineHeight: 1, fontWeight: 800, letterSpacing: 0.4, whiteSpace: "nowrap", boxShadow: "0 7px 16px rgba(45, 24, 9, .28)" }}>{children}</div>;
}

function FoundationVisuals({ job, second }: { job: VideoJob; second: number }) {
  if (job.visual_mode !== "foundation_storyboard" || !job.narrationSegments?.length) return null;
  const active = job.narrationSegments.find((segment) => segment.visualKind && second >= Number(segment.startSec ?? 0) && second < Number(segment.endSec ?? -1));
  if (!active?.visualKind) return null;
  const start = Number(active.startSec ?? 0);
  const end = Number(active.endSec ?? start + 1);
  const enterEnd = Math.min(start + 0.42, end);
  const exitStart = Math.max(enterEnd, end - 0.26);
  const opacity = interpolate(second, [start, enterEnd, exitStart, end], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const kind = active.visualKind as VisualKind;
  const headline = active.headline || job.visualStoryboard?.find((scene) => scene.index === active.sceneId)?.headline || "Xiangqi Lab";
  const redGeneral = boardPoint(4, 9);
  const blackGeneral = boardPoint(4, 0);
  const cannon = boardPoint(1, 7);
  const screen = boardPoint(1, 4);
  const target = boardPoint(1, 2);

  return (
    <>
      {!job.referenceMode && <div style={{ position: "absolute", top: 268, left: 92, right: 92, display: "flex", justifyContent: "center", zIndex: 8, opacity }}>
        <div style={{ padding: "10px 24px", borderRadius: 18, background: "rgba(33, 26, 22, .88)", color: "#fff8e9", fontSize: 27, fontWeight: 900, letterSpacing: 1.1, boxShadow: "0 10px 24px rgba(64, 35, 12, .24)" }}>{headline}</div>
      </div>}

      {kind === "battlefield" && <>
        <div style={{ position: "absolute", left: board.x + 26, top: board.y - 18, width: grid.width, display: "flex", justifyContent: "space-between", opacity, zIndex: 5 }}>
{Array.from({ length: 9 }).map((_, index) => <Marker key={index} left={index * cell} top={0} opacity={opacity}>F{index + 1}</Marker>)}</div>
        <div style={{ position: "absolute", left: board.x - 18, top: grid.y, height: grid.height, display: "flex", flexDirection: "column", justifyContent: "space-between", opacity, zIndex: 5 }}>
{Array.from({ length: 10 }).map((_, index) => <Marker key={index} left={0} top={index * cell} opacity={opacity}>R{index + 1}</Marker>)}</div>
        <div style={{ position: "absolute", left: board.x + 44, top: board.y + 44, width: board.width - 88, height: board.height - 88, border: "5px solid rgba(255, 241, 182, .92)", borderRadius: 18, boxShadow: "inset 0 0 0 7px rgba(197, 138, 58, .24)", opacity, zIndex: 3 }} />
      </>}

      {kind === "two_armies" && <>
        <div style={{ position: "absolute", left: grid.x, top: grid.y, width: grid.width, height: grid.height / 2 - 10, background: "linear-gradient(180deg, rgba(35,35,35,.48), rgba(35,35,35,.08))", opacity: opacity * .9, zIndex: 3, pointerEvents: "none" }} />
        <div style={{ position: "absolute", left: grid.x, top: grid.y + grid.height / 2 + 10, width: grid.width, height: grid.height / 2 - 10, background: "linear-gradient(0deg, rgba(182,60,47,.42), rgba(182,60,47,.06))", opacity: opacity * .9, zIndex: 3, pointerEvents: "none" }} />
        <Marker left={board.x + board.width / 2} top={board.y + 255} opacity={opacity} tone="black">BLACK ARMY ↓</Marker>
        <Marker left={board.x + board.width / 2} top={board.y + board.height - 255} opacity={opacity} tone="red">↑ RED ARMY</Marker>
      </>}

      {kind === "generals_goal" && <>
        {[{ point: blackGeneral, label: "BLACK GENERAL", tone: "black" as const }, { point: redGeneral, label: "RED GENERAL", tone: "red" as const }].map(({ point, label, tone }) => <div key={label} style={{ position: "absolute", left: point.x - 62, top: point.y - 62, width: 124, height: 124, borderRadius: 999, border: `7px solid ${tone === "red" ? "#ff876d" : "#f5e0ad"}`, boxShadow: `0 0 0 12px ${tone === "red" ? "rgba(182,60,47,.24)" : "rgba(35,35,35,.22)"}`, opacity, zIndex: 5 }} />)}
        <Marker left={blackGeneral.x} top={blackGeneral.y + 88} opacity={opacity} tone="black">BLACK GENERAL</Marker>
        <Marker left={redGeneral.x} top={redGeneral.y - 88} opacity={opacity} tone="red">RED GENERAL</Marker>
        <svg style={{ position: "absolute", inset: 0, zIndex: 4, opacity }} width="1080" height="1920"><line x1={redGeneral.x} y1={redGeneral.y - 110} x2={blackGeneral.x} y2={blackGeneral.y + 110} stroke="#f3ca62" strokeWidth="8" strokeDasharray="18 14" /><polygon points={`${blackGeneral.x},${blackGeneral.y + 84} ${blackGeneral.x - 17},${blackGeneral.y + 122} ${blackGeneral.x + 17},${blackGeneral.y + 122}`} fill="#f3ca62" /></svg>
      </>}

      {kind === "intersections" && <>
        <svg style={{ position: "absolute", inset: 0, zIndex: 4, opacity }} width="1080" height="1920">{Array.from({ length: 10 }).flatMap((_, row) => Array.from({ length: 9 }).map((__, column) => <circle key={`${column}-${row}`} cx={boardPoint(column, row).x} cy={boardPoint(column, row).y} r={row === 4 && column === 4 ? 18 : 5} fill={row === 4 && column === 4 ? "#fff2ad" : "rgba(255, 246, 210, .72)"} stroke={row === 4 && column === 4 ? COLORS.red : "none"} strokeWidth={5} />))}</svg>
        <Marker left={boardPoint(4, 4).x} top={boardPoint(4, 4).y - 64} opacity={opacity} tone="gold">INTERSECTION</Marker>
        <div style={{ position: "absolute", left: boardPoint(4, 4).x - 50, top: boardPoint(4, 4).y - 50, width: 100, height: 100, border: "4px dashed rgba(255,255,255,.75)", opacity, zIndex: 4 }} />
      </>}

      {kind === "river_palaces" && <>
        <div style={{ position: "absolute", left: grid.x, top: grid.y + 4 * cell, width: grid.width, height: cell, background: "rgba(60, 145, 194, .54)", borderTop: "4px solid #b9eaff", borderBottom: "4px solid #b9eaff", opacity, zIndex: 3 }} />
        <div style={{ position: "absolute", left: grid.x + 3 * cell, top: grid.y, width: 2 * cell, height: 2 * cell, border: "7px solid #f5ce74", borderRadius: 12, opacity, zIndex: 4 }} />
        <div style={{ position: "absolute", left: grid.x + 3 * cell, top: grid.y + 7 * cell, width: 2 * cell, height: 2 * cell, border: "7px solid #f5ce74", borderRadius: 12, opacity, zIndex: 4 }} />
        {!job.referenceMode && <>
          <Marker left={board.x + board.width / 2} top={grid.y + 4.5 * cell} opacity={opacity} tone="blue">THE RIVER</Marker>
          <Marker left={grid.x + cell} top={grid.y + 2.25 * cell} opacity={opacity}>BLACK PALACE</Marker>
          <Marker left={grid.x + cell} top={grid.y + 6.75 * cell} opacity={opacity}>RED PALACE</Marker>
        </>}
      </>}

      {kind === "cannon_geometry" && <>
        <svg style={{ position: "absolute", inset: 0, zIndex: 5, opacity }} width="1080" height="1920"><line x1={cannon.x} y1={cannon.y} x2={target.x} y2={target.y} stroke="#ff6658" strokeWidth="12" strokeLinecap="round" /><line x1={cannon.x} y1={cannon.y} x2={target.x} y2={target.y} stroke="#fff1ac" strokeWidth="4" strokeDasharray="18 12" /><circle cx={target.x} cy={target.y} r="46" fill="none" stroke="#ff6658" strokeWidth="8" /></svg>
        <Img src={staticFile("assets/pieces/black_pawn.svg")} style={{ position: "absolute", left: screen.x - 47, top: screen.y - 47, width: 94, height: 94, objectFit: "contain", opacity, zIndex: 6, filter: "drop-shadow(0 0 16px rgba(255,224,120,.95))" }} />
        <div style={{ position: "absolute", left: screen.x - 34, top: screen.y - 86, width: 68, height: 44, borderRadius: 999, background: "rgba(246, 222, 139, .97)", color: "#442214", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, fontWeight: 900, textAlign: "center", opacity, zIndex: 7, boxShadow: "0 0 0 8px rgba(255,224,120,.30)" }}>ONE SCREEN</div>
        <Marker left={cannon.x + 88} top={cannon.y + 32} opacity={opacity} tone="red">CANNON</Marker>
        <Marker left={target.x + 94} top={target.y - 20} opacity={opacity} tone="black">TARGET</Marker>
      </>}

      {kind === "learning_roadmap" && <>
        <div style={{ position: "absolute", left: 60, right: 60, top: 1474, height: 128, opacity, zIndex: 6, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          {["BOARD", "SETUP", "PIECES", "MOVES", "GAMES", "TACTICS"].map((step, index, steps) => <div key={step} style={{ display: "flex", alignItems: "center", flex: 1, minWidth: 0 }}><div style={{ flex: 1, padding: "12px 6px", borderRadius: 15, background: index < 2 ? "#b63c2f" : "#3a312b", color: "#fff9e9", fontSize: 18, fontWeight: 900, textAlign: "center", boxShadow: "0 8px 16px rgba(56,31,13,.22)" }}>{step}</div>{index < steps.length - 1 && <div style={{ margin: "0 5px", color: COLORS.red, fontWeight: 900, fontSize: 26 }}>→</div>}</div>)}
        </div>
      </>}
    </>
  );
}


function GeneratedVisualAsset({ job, second }: { job: VideoJob; second: number }) {
  if (!job.narrationSegments?.length || !job.visualStoryboard?.length) return null;
  const active = job.narrationSegments.find((segment) => segment.sceneId && second >= Number(segment.startSec ?? 0) && second < Number(segment.endSec ?? -1));
  if (!active?.sceneId) return null;
  const asset = job.visualStoryboard.find((scene) => scene.index === active.sceneId)?.generatedAsset;
  if (!asset?.src) return null;
  const start = Number(active.startSec ?? 0);
  const end = Number(active.endSec ?? start + 1);
  const revealEnd = Math.min(start + 0.45, end);
  // Keep the approved asset visible for the scene's explanatory window.
  // It remains a backdrop beneath the deterministic board and overlays.
  const fadeStart = Math.max(revealEnd, end - 0.45);
  const fadeEnd = Math.min(end, fadeStart + 0.3);
  const opacity = interpolate(second, [start, revealEnd, fadeStart, fadeEnd], [0, 0.96, 0.96, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const cameraScale = interpolate(second, [start, Math.max(start + 0.01, end)], [1.02, 1.04], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return <div style={{ position: "absolute", inset: 0, zIndex: 2, opacity, overflow: "hidden", background: COLORS.ink }}>
    <Img src={staticFile(asset.src)} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "center", transform: `scale(${cameraScale})` }} />
    <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(20,14,10,.28) 0%, rgba(20,14,10,.06) 46%, rgba(20,14,10,.46) 100%)" }} />
  </div>;
}

function StoryboardVisuals({ job, second }: { job: VideoJob; second: number }) {
  if (job.visual_mode !== "storyboard" || !job.narrationSegments?.length) return null;
  const active = job.narrationSegments.find((segment) => segment.visualKind && second >= Number(segment.startSec ?? 0) && second < Number(segment.endSec ?? -1));
  if (!active?.visualKind) return null;
  const start = Number(active.startSec ?? 0);
  const end = Number(active.endSec ?? start + 1);
  const enterEnd = Math.min(start + 0.28, end);
  const exitStart = Math.max(enterEnd, end - 0.2);
  const opacity = interpolate(second, [start, enterEnd, exitStart, end], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const kind = active.visualKind;
  const move = active.movePly ? job.moves.find((candidate) => candidate.ply === active.movePly) : undefined;
  const from = move ? boardPoint(move.from[0], move.from[1]) : boardPoint(1, 7);
  const to = move ? boardPoint(move.to[0], move.to[1]) : boardPoint(4, 4);
  const target = move ? boardPoint(move.to[0], move.to[1]) : boardPoint(4, 0);
  const headline = active.headline || "Board Idea";
  const isMoveSegment = active.kind === "move" || active.movePly !== undefined;
  const overlayLine = (color: string, dashed = false) => <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke={color} strokeWidth={10} strokeLinecap="round" strokeDasharray={dashed ? "18 14" : undefined} />;

  return <>
    {!isMoveSegment && <div style={{ position: "absolute", top: 205, left: 92, right: 92, display: "flex", justifyContent: "center", zIndex: 8, opacity }}>
      <div style={{ padding: "9px 22px", borderRadius: 16, background: "rgba(33, 26, 22, .88)", color: "#fff8e9", fontSize: 25, fontWeight: 900, letterSpacing: 0.8, boxShadow: "0 10px 22px rgba(64, 35, 12, .22)" }}>{headline}</div>
    </div>}

    {(kind === "board_overview" || kind === "army_setup" || kind === "board_identity") && <>
      <div style={{ position: "absolute", left: grid.x, top: grid.y, width: grid.width, height: grid.height, border: "5px solid rgba(255, 241, 182, .9)", borderRadius: 18, opacity, zIndex: 3 }} />
      <Marker left={board.x + board.width / 2} top={board.y - 22} opacity={opacity} tone="gold">BOARD MAP</Marker>
      {kind === "army_setup" && <><div style={{ position: "absolute", left: grid.x, top: grid.y, width: grid.width, height: grid.height / 2, background: "rgba(45,45,45,.2)", opacity, zIndex: 3 }} /><div style={{ position: "absolute", left: grid.x, top: grid.y + grid.height / 2, width: grid.width, height: grid.height / 2, background: "rgba(182,60,47,.18)", opacity, zIndex: 3 }} /><Marker left={board.x + board.width / 2} top={board.y + 170} opacity={opacity} tone="black">BLACK SETUP</Marker><Marker left={board.x + board.width / 2} top={board.y + board.height - 170} opacity={opacity} tone="red">RED SETUP</Marker></>}
      {kind === "board_identity" && <><Marker left={board.x + 95} top={board.y + 88} opacity={opacity} tone="gold">9 FILES</Marker><Marker left={board.x + board.width - 94} top={board.y + board.height - 88} opacity={opacity} tone="gold">10 RANKS</Marker><div style={{ position: "absolute", left: grid.x, top: grid.y + 4 * cell, width: grid.width, height: cell, background: "rgba(74,154,194,.28)", borderTop: "4px solid rgba(189,231,255,.9)", borderBottom: "4px solid rgba(189,231,255,.9)", opacity, zIndex: 3 }} /></>}
    </>}

    {kind === "two_armies" && <><div style={{ position: "absolute", left: grid.x, top: grid.y, width: grid.width, height: grid.height / 2 - 10, background: "linear-gradient(180deg, rgba(35,35,35,.46), rgba(35,35,35,.06))", opacity, zIndex: 3 }} /><div style={{ position: "absolute", left: grid.x, top: grid.y + grid.height / 2 + 10, width: grid.width, height: grid.height / 2 - 10, background: "linear-gradient(0deg, rgba(182,60,47,.42), rgba(182,60,47,.06))", opacity, zIndex: 3 }} /><Marker left={board.x + board.width / 2} top={board.y + 250} opacity={opacity} tone="black">BLACK ARMY ↓</Marker><Marker left={board.x + board.width / 2} top={board.y + board.height - 250} opacity={opacity} tone="red">↑ RED ARMY</Marker></>}

    {kind === "generals_goal" && <><div style={{ position: "absolute", left: boardPoint(4, 0).x - 62, top: boardPoint(4, 0).y - 62, width: 124, height: 124, borderRadius: 999, border: "7px solid #f5e0ad", boxShadow: "0 0 0 12px rgba(35,35,35,.22)", opacity, zIndex: 5 }} /><div style={{ position: "absolute", left: boardPoint(4, 9).x - 62, top: boardPoint(4, 9).y - 62, width: 124, height: 124, borderRadius: 999, border: "7px solid #ff876d", boxShadow: "0 0 0 12px rgba(182,60,47,.24)", opacity, zIndex: 5 }} /><svg style={{ position: "absolute", inset: 0, zIndex: 4, opacity }} width="1080" height="1920"><line x1={boardPoint(4, 9).x} y1={boardPoint(4, 9).y - 110} x2={boardPoint(4, 0).x} y2={boardPoint(4, 0).y + 110} stroke="#f3ca62" strokeWidth="8" strokeDasharray="18 14" /></svg><Marker left={boardPoint(4, 0).x} top={boardPoint(4, 0).y + 88} opacity={opacity} tone="black">BLACK GENERAL</Marker><Marker left={boardPoint(4, 9).x} top={boardPoint(4, 9).y - 88} opacity={opacity} tone="red">RED GENERAL</Marker></>}

    {kind === "intersections" && <><svg style={{ position: "absolute", inset: 0, zIndex: 4, opacity }} width="1080" height="1920">{Array.from({ length: 10 }).flatMap((_, row) => Array.from({ length: 9 }).map((__, column) => <circle key={`${column}-${row}`} cx={boardPoint(column, row).x} cy={boardPoint(column, row).y} r={row === 4 && column === 4 ? 18 : 5} fill={row === 4 && column === 4 ? "#fff2ad" : "rgba(255,246,210,.72)"} stroke={row === 4 && column === 4 ? COLORS.red : "none"} strokeWidth={5} />))}</svg><Marker left={boardPoint(4, 4).x} top={boardPoint(4, 4).y - 64} opacity={opacity} tone="gold">INTERSECTION</Marker></>}

    {kind === "river_palaces" && <><div style={{ position: "absolute", left: grid.x, top: grid.y + 4 * cell, width: grid.width, height: cell, background: "rgba(60,145,194,.54)", borderTop: "4px solid #b9eaff", borderBottom: "4px solid #b9eaff", opacity, zIndex: 3 }} /><div style={{ position: "absolute", left: grid.x + 3 * cell, top: grid.y, width: 2 * cell, height: 2 * cell, border: "7px solid #f5ce74", borderRadius: 12, opacity, zIndex: 4 }} /><div style={{ position: "absolute", left: grid.x + 3 * cell, top: grid.y + 7 * cell, width: 2 * cell, height: 2 * cell, border: "7px solid #f5ce74", borderRadius: 12, opacity, zIndex: 4 }} /><Marker left={board.x + board.width / 2} top={grid.y + 4.5 * cell} opacity={opacity} tone="blue">THE RIVER</Marker><Marker left={board.x + board.width / 2} top={grid.y + 2.25 * cell} opacity={opacity}>BLACK PALACE</Marker><Marker left={board.x + board.width / 2} top={grid.y + 6.75 * cell} opacity={opacity} tone="red">RED PALACE</Marker></>}

    {kind === "cannon_geometry" && <><svg style={{ position: "absolute", inset: 0, zIndex: 5, opacity }} width="1080" height="1920"><line x1={boardPoint(1, 7).x} y1={boardPoint(1, 7).y} x2={boardPoint(1, 2).x} y2={boardPoint(1, 2).y} stroke="#ff6658" strokeWidth="12" strokeLinecap="round" /><line x1={boardPoint(1, 7).x} y1={boardPoint(1, 7).y} x2={boardPoint(1, 2).x} y2={boardPoint(1, 2).y} stroke="#fff1ac" strokeWidth="4" strokeDasharray="18 12" /></svg><Img src={staticFile("assets/pieces/black_pawn.svg")} style={{ position: "absolute", left: boardPoint(1, 4).x - 47, top: boardPoint(1, 4).y - 47, width: 94, height: 94, objectFit: "contain", opacity, zIndex: 6 }} /><Marker left={boardPoint(1, 4).x} top={boardPoint(1, 4).y - 78} opacity={opacity} tone="gold">ONE SCREEN</Marker></>}

    {kind === "learning_roadmap" && <div style={{ position: "absolute", left: 60, right: 60, top: 1474, height: 128, opacity, zIndex: 6, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>{["BOARD", "SETUP", "PIECES", "MOVES", "GAMES", "TACTICS"].map((step, index, steps) => <div key={step} style={{ display: "flex", alignItems: "center", flex: 1, minWidth: 0 }}><div style={{ flex: 1, padding: "12px 6px", borderRadius: 15, background: index < 2 ? COLORS.red : COLORS.black, color: "#fff9e9", fontSize: 18, fontWeight: 900, textAlign: "center", boxShadow: "0 8px 16px rgba(56,31,13,.22)" }}>{step}</div>{index < steps.length - 1 && <div style={{ margin: "0 5px", color: COLORS.red, fontWeight: 900, fontSize: 26 }}>→</div>}</div>)}</div>}

    {kind === "history_timeline" && <div style={{ position: "absolute", top: 330, left: 92, right: 92, height: 46, display: "flex", alignItems: "center", justifyContent: "space-between", opacity, zIndex: 7 }}><div style={{ position: "absolute", left: 40, right: 40, height: 6, background: "linear-gradient(90deg, #8f6230, #f5ce74, #b63c2f)", borderRadius: 999 }} />{["ORIGINS", "FORMED", "TODAY"].map((label, index) => <div key={label} style={{ position: "relative", display: "flex", flexDirection: "column", alignItems: "center", gap: 7 }}><div style={{ width: 22, height: 22, borderRadius: 999, background: index === 2 ? COLORS.red : COLORS.gold, border: "4px solid #fff7e5", boxShadow: "0 4px 12px rgba(54,31,12,.32)" }} /><span style={{ color: COLORS.ink, fontSize: 17, fontWeight: 900, letterSpacing: 1 }}>{label}</span></div>)}</div>}

    {kind === "cultural_heritage" && <><div style={{ position: "absolute", left: boardPoint(4, 4).x - 180, top: boardPoint(4, 4).y - 180, width: 360, height: 360, borderRadius: 999, border: "10px double rgba(197,138,58,.92)", boxShadow: "inset 0 0 0 18px rgba(197,138,58,.16), 0 0 0 18px rgba(182,60,47,.09)", opacity, zIndex: 3 }} /><Marker left={boardPoint(4, 4).x} top={boardPoint(4, 4).y} opacity={opacity} tone="gold">TWO ARMIES</Marker></>}

    {kind === "coordinate_map" && <><div style={{ position: "absolute", left: grid.x, top: board.y - 18, width: grid.width, display: "flex", justifyContent: "space-between", opacity, zIndex: 5 }}>{Array.from({ length: 9 }).map((_, index) => <Marker key={index} left={index * cell} top={0} opacity={opacity}>F{index + 1}</Marker>)}</div><div style={{ position: "absolute", left: board.x - 18, top: grid.y, height: grid.height, display: "flex", flexDirection: "column", justifyContent: "space-between", opacity, zIndex: 5 }}>{Array.from({ length: 10 }).map((_, index) => <Marker key={index} left={0} top={index * cell} opacity={opacity}>R{index + 1}</Marker>)}</div><div style={{ position: "absolute", left: boardPoint(4, 4).x - 42, top: boardPoint(4, 4).y - 42, width: 84, height: 84, borderRadius: 999, border: "7px solid #f5ce74", opacity, zIndex: 5 }} /></>}

    {kind === "rule_focus" && <><div style={{ position: "absolute", left: boardPoint(4, 4).x - 110, top: boardPoint(4, 4).y - 110, width: 220, height: 220, borderRadius: 999, border: "10px solid #4a9ac2", boxShadow: "0 0 0 18px rgba(74,154,194,.18)", opacity, zIndex: 4 }} /><svg style={{ position: "absolute", inset: 0, zIndex: 5, opacity }} width="1080" height="1920"><line x1={boardPoint(4, 4).x - 175} y1={boardPoint(4, 4).y + 175} x2={boardPoint(4, 4).x - 80} y2={boardPoint(4, 4).y + 80} stroke="#56a76c" strokeWidth="11" strokeLinecap="round" /><line x1={boardPoint(4, 4).x + 175} y1={boardPoint(4, 4).y - 175} x2={boardPoint(4, 4).x + 80} y2={boardPoint(4, 4).y - 80} stroke="#e95b4c" strokeWidth="11" strokeLinecap="round" /><line x1={boardPoint(4, 4).x + 150} y1={boardPoint(4, 4).y - 205} x2={boardPoint(4, 4).x + 205} y2={boardPoint(4, 4).y - 150} stroke="#e95b4c" strokeWidth="11" strokeLinecap="round" /><line x1={boardPoint(4, 4).x + 205} y1={boardPoint(4, 4).y - 205} x2={boardPoint(4, 4).x + 150} y2={boardPoint(4, 4).y - 150} stroke="#e95b4c" strokeWidth="11" strokeLinecap="round" /></svg><Marker left={boardPoint(4, 4).x} top={boardPoint(4, 4).y - 138} opacity={opacity} tone="blue">RULE</Marker></>}

    {kind === "piece_spotlight" && <><div style={{ position: "absolute", left: boardPoint(4, 2).x - 78, top: boardPoint(4, 2).y - 78, width: 156, height: 156, borderRadius: 999, border: "9px solid #f5ce74", boxShadow: "0 0 0 16px rgba(245,206,116,.18)", opacity, zIndex: 5 }} /><div style={{ position: "absolute", left: boardPoint(4, 7).x - 78, top: boardPoint(4, 7).y - 78, width: 156, height: 156, borderRadius: 999, border: "9px solid #ff876d", boxShadow: "0 0 0 16px rgba(182,60,47,.18)", opacity, zIndex: 5 }} /><Marker left={boardPoint(4, 2).x} top={boardPoint(4, 2).y - 112} opacity={opacity} tone="black">BLACK PIECE</Marker><Marker left={boardPoint(4, 7).x} top={boardPoint(4, 7).y + 112} opacity={opacity} tone="red">RED PIECE</Marker></>}

    {(kind === "piece_movement" || kind === "move_path" || kind === "attack_line" || kind === "capture_sequence" || kind === "cannon_screen") && <>
      {kind === "piece_movement" && !move ? <><svg style={{ position: "absolute", inset: 0, zIndex: 5, opacity }} width="1080" height="1920"><line x1={boardPoint(0, 5).x} y1={boardPoint(0, 5).y} x2={boardPoint(8, 5).x} y2={boardPoint(8, 5).y} stroke="#e0a63c" strokeWidth="10" strokeLinecap="round" /><line x1={boardPoint(1, 7).x} y1={boardPoint(1, 7).y} x2={boardPoint(1, 2).x} y2={boardPoint(1, 2).y} stroke="#ef6655" strokeWidth="10" strokeDasharray="16 12" strokeLinecap="round" /><polyline points={`${boardPoint(6, 7).x},${boardPoint(6, 7).y} ${boardPoint(6, 5).x},${boardPoint(6, 5).y} ${boardPoint(7, 5).x},${boardPoint(7, 5).y}`} fill="none" stroke="#4a9ac2" strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" /></svg><div style={{ position: "absolute", left: boardPoint(1, 4).x - 42, top: boardPoint(1, 4).y - 42, width: 84, height: 84, borderRadius: 999, border: "8px solid #f5ce74", boxShadow: "0 0 0 12px rgba(245,206,116,.20)", opacity, zIndex: 6 }} /><Marker left={boardPoint(4, 5).x} top={boardPoint(4, 5).y - 58} opacity={opacity} tone="gold">ROOK LINE</Marker><Marker left={boardPoint(1, 4).x} top={boardPoint(1, 4).y - 82} opacity={opacity} tone="red">CANNON SCREEN</Marker><Marker left={boardPoint(7, 5).x} top={boardPoint(7, 5).y - 54} opacity={opacity} tone="blue">HORSE LEG</Marker></> : <><svg style={{ position: "absolute", inset: 0, zIndex: 5, opacity }} width="1080" height="1920">
        {overlayLine("#e0a63c", kind === "move_path")}
        <polygon points={`${to.x},${to.y} ${to.x - 18},${to.y - 34} ${to.x + 18},${to.y - 34}`} fill="#e0a63c" />
        {kind === "capture_sequence" && <circle cx={target.x} cy={target.y} r={58} fill="none" stroke="#ef6655" strokeWidth="9" />}
      </svg>
      {move && <Marker left={from.x} top={from.y - 62} opacity={opacity} tone="gold">FROM</Marker>}
      {move && <Marker left={to.x} top={to.y + 62} opacity={opacity} tone="red">TO</Marker>}
      {kind === "cannon_screen" && <><Img src={staticFile("assets/pieces/black_pawn.svg")} style={{ position: "absolute", left: boardPoint(1, 4).x - 47, top: boardPoint(1, 4).y - 47, width: 94, height: 94, objectFit: "contain", opacity, zIndex: 6 }} /><Marker left={boardPoint(1, 4).x} top={boardPoint(1, 4).y - 78} opacity={opacity} tone="gold">SCREEN</Marker></>}</>}
    </>}

    {kind === "defense_zone" && <>
      <div style={{ position: "absolute", left: to.x - 100, top: to.y - 100, width: 200, height: 200, borderRadius: 999, border: "9px solid #4a9ac2", boxShadow: "0 0 0 16px rgba(74,154,194,.2)", opacity, zIndex: 5 }} />
      <Marker left={to.x} top={to.y - 132} opacity={opacity} tone="blue">SAFE ZONE</Marker>
    </>}

    {kind === "threat_marker" && <>
      <div style={{ position: "absolute", left: target.x - 78, top: target.y - 78, width: 156, height: 156, borderRadius: 999, border: "10px solid #e95b4c", boxShadow: "0 0 0 18px rgba(233,91,76,.18)", opacity, zIndex: 5 }} />
      <Marker left={target.x} top={target.y - 112} opacity={opacity} tone="red">THREAT</Marker>
    </>}

    {(kind === "before_after" || kind === "comparison_split") && <>
      <div style={{ position: "absolute", left: board.x + 48, top: board.y + 48, width: board.width - 96, height: board.height - 96, border: "5px dashed rgba(255,241,182,.85)", borderRadius: 20, opacity, zIndex: 4 }} />
      <Marker left={board.x + 180} top={board.y + board.height - 34} opacity={opacity} tone="black">BEFORE</Marker>
      <Marker left={board.x + board.width - 180} top={board.y + board.height - 34} opacity={opacity} tone="red">AFTER</Marker>
    </>}

    {kind === "game_phase" && <>
      <div style={{ position: "absolute", left: board.x + 30, top: grid.y + 4 * cell - 30, width: grid.width, height: cell + 60, background: "rgba(197,138,58,.22)", borderTop: "5px solid rgba(255,241,182,.9)", borderBottom: "5px solid rgba(255,241,182,.9)", opacity, zIndex: 3 }} />
      <Marker left={board.x + board.width / 2} top={board.y + board.height / 2} opacity={opacity} tone="gold">TURNING POINT</Marker>
    </>}

    {kind === "question_reveal" && <>
      <div style={{ position: "absolute", left: target.x - 72, top: target.y - 72, width: 144, height: 144, borderRadius: 999, border: "8px dashed #f5ce74", opacity, zIndex: 5 }} />
      <Marker left={target.x} top={target.y - 108} opacity={opacity} tone="gold">YOUR TURN?</Marker>
    </>}

    {kind === "result_summary" && <>
      <div style={{ position: "absolute", left: target.x - 88, top: target.y - 88, width: 176, height: 176, borderRadius: 999, border: "10px solid #56a76c", boxShadow: "0 0 0 18px rgba(86,167,108,.2)", opacity, zIndex: 5 }} />
      <Marker left={target.x} top={target.y - 120} opacity={opacity} tone="blue">RESULT</Marker>
    </>}
  </>;
}

function Caption({ job, second }: { job: VideoJob; second: number }) {
  if (job.language === "en" && job.captions_source === "english_captions_disabled_in_video") return null;
  const cue = job.captions.find((item) => second >= item.startSec && second < item.endSec);
  if (!cue) return null;
  const isIntro = cue.captionPosition === "bottom" || cue.kind === "intro";
  return <div style={{ position: "absolute", top: isIntro ? undefined : 342, bottom: isIntro ? 112 : undefined, left: isIntro ? 82 : 104, right: isIntro ? 82 : 104, minHeight: isIntro ? 54 : 42, maxHeight: isIntro ? 170 : 72, display: "flex", alignItems: "center", justifyContent: "center", textAlign: "center", padding: isIntro ? "12px 22px" : "8px 18px", borderRadius: 16, background: "rgba(31, 22, 17, .82)", color: "#fff8e9", fontFamily: job.language === "zh" ? "Noto Sans CJK SC, Noto Sans SC, Arial, sans-serif" : "Arial, sans-serif", fontSize: isIntro ? 24 : 22, lineHeight: 1.18, fontWeight: 700, direction: "ltr", overflow: "hidden", whiteSpace: "normal", zIndex: 10 }}>{cue.text}</div>;
}

function pointLabel(point: [number, number]): string { return `F${point[0] + 1}R${point[1] + 1}`; }
function pieceLabel(piece: Move["piece"]): string { return { pawn: "Pawn", rook: "Rook", knight: "Horse", bishop: "Elephant", advisor: "Advisor", king: "General", cannon: "Cannon" }[piece]; }

function MoveCard({ move, second, language }: { move?: Move; second: number; language: VideoJob["language"] }) {
  const opacity = move ? interpolate(second, [move.startSec - 0.25, move.startSec, move.endSec, move.endSec + 0.35], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 0;
  if (!move) return null;
  const copy = UI_COPY[language];
  const moveText = `${pieceLabel(move.piece)} ${pointLabel(move.from)}→${pointLabel(move.to)}`;
  return <div style={{ position: "absolute", top: 258, left: 74, right: 74, display: "flex", justifyContent: "center", opacity, direction: "ltr", zIndex: 11 }}><div style={{ background: COLORS.red, color: "#fff9ed", borderRadius: 22, padding: "10px 26px", fontSize: 28, lineHeight: 1.15, fontWeight: 800, boxShadow: "0 12px 24px rgba(92, 20, 14, .25)" }}><span>{language === "zh" ? `${copy.move}${move.ply}` : `${copy.move} ${move.ply}`} • {moveText}</span><span style={{ display: "block", marginTop: 4, fontSize: 20, fontWeight: 600, opacity: 0.92 }}>{move.label}</span></div></div>;
}

export const XiangqiComposition: React.FC<VideoJob> = (job) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const second = frame / fps;
  const active = activeMoveAtSecond(job, second);
  const copy = UI_COPY[job.language];
  const introOpacity = interpolate(frame, [0, 18, 42], [0, 1, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const titleScale = interpolate(frame, [0, 36], [0.92, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const subtitle = job.visual_mode === "foundation_storyboard" ? "See the board before the first move" : job.visual_mode === "storyboard" ? "" : copy.subtitle;

  return     <AbsoluteFill style={{ background: COLORS.paper, color: COLORS.ink, fontFamily: "Arial, sans-serif" }}>
    <AbsoluteFill style={{ background: "radial-gradient(circle at 50% 10%, #fff8e8 0%, #f5e6ca 48%, #e2c18d 100%)" }} />
    {!job.referenceMode && <div style={{ position: "absolute", top: 72, left: 72, right: 72, textAlign: "center", direction: "ltr", opacity: introOpacity, transform: `scale(${titleScale})`, zIndex: 12 }}>
      <div style={{ fontSize: 28, letterSpacing: 7, color: COLORS.red, fontWeight: 800 }}>CHINESE CHEESE VIDEO</div>
      <div style={{ marginTop: 16, fontSize: 58, fontWeight: 900, lineHeight: 1.15 }}>{job.title}</div>
      {subtitle ? <div style={{ marginTop: 14, fontSize: 26, color: "#76543b", fontFamily: job.language === "zh" ? "Noto Sans CJK SC, Noto Sans SC, Arial, sans-serif" : "Arial, sans-serif" }}>{subtitle}</div> : null}
    </div>}
    <Board job={job} second={second} />
    <GeneratedVisualAsset job={job} second={second} />
    <FoundationVisuals job={job} second={second} />
    <StoryboardVisuals job={job} second={second} />
    <MoveCard move={active} second={second} language={job.language} />
    {!job.referenceMode && <Caption job={job} second={second} />}
    {!job.referenceMode && job.audioSrc ? <Audio src={staticFile(job.audioSrc)} volume={1} /> : null}
    {!job.referenceMode && <div style={{ position: "absolute", left: 76, right: 76, bottom: 52, display: "flex", justifyContent: "space-between", color: "#795a3e", fontSize: 23, direction: "ltr", zIndex: 12 }}><span>{copy.footer} • {job.language.toUpperCase()}</span><span>{Math.max(0, Math.ceil(job.durationInSeconds - second))}{copy.seconds}</span></div>}
  </AbsoluteFill>;
};
