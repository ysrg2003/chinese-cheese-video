import type { VideoJob } from "./types";

export const sampleJob: VideoJob = {
  id: "sample",
  title: "The Quiet Trap on the Left Wing",
  language: "en",
  fen: "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR r",
  narration: "The first pawn push looks harmless, but it opens a tactical file for the cannon. When the natural reply arrives, the quiet pressure turns into a direct threat.",
  moves: [
    { ply: 1, from: [0, 6], to: [0, 5], piece: "pawn", side: "red", startSec: 2.2, endSec: 3.1, label: "Advance the pawn" },
    { ply: 2, from: [0, 3], to: [0, 4], piece: "pawn", side: "black", startSec: 4.1, endSec: 5.0, label: "The counter-push" },
    { ply: 3, from: [1, 7], to: [1, 4], piece: "cannon", side: "red", startSec: 6.0, endSec: 7.2, label: "The cannon takes the file" },
  ],
  captions: [
    { startSec: 0.2, endSec: 2.1, text: "The idea starts with a move that looks ordinary." },
    { startSec: 2.2, endSec: 3.8, text: "The pawn push opens a file for the cannon." },
    { startSec: 4.0, endSec: 5.8, text: "The natural reply leaves a tactical weakness." },
    { startSec: 5.9, endSec: 8.0, text: "Now the decisive idea appears." },
  ],
  audioSrc: "",
  durationInSeconds: 14,
  theme: "wood",
};
