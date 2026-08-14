# Legal-overlay render findings

A local Remotion sample render was created from `python/legal_overlay_sample_job.json` at 1080×1920 for 2 seconds, without publishing or YouTube mutation.

The frame at approximately 0.45 seconds shows the concise English teaching cue `Pawn movement` at the bottom, the board headline `Pawn Legal Destinations`, and the red pawn still on its starting intersection. The origin is ringed and the legal destination indicator is attached to the board intersection rather than a square.

The frame at approximately 0.9 seconds shows the MoveCard `Move 1 • Pawn F1R7 → F1R6`, the board cue `One legal forward destination`, the fast move state, and the legal destination highlighted at the actual destination intersection. The corrected board geometry remains visible with pieces on intersections and a real river gap.

The current implementation computes destinations from the actual FEN position and filters them through piece geometry, palace/river, horse-leg, elephant-eye, cannon-screen, flying-general, and self-check constraints before drawing blue legal-target dots and a red played/capture target.

The final rerender after removing `FROM`/`TO` labels from `piece_movement` remains readable: the board headline, MoveCard, spoken-sentence cue, source ring, and legal destination highlight remain visible without the labels obscuring edge pieces. The compact labels remain available for `move_path`, `attack_line`, and tactical overlay kinds where they add context.

## Live production proof — run 31775780066

The live production selected `A Short History of Xiangqi` (`curriculum-en-003-a-short-history-of-xiangqi-en`), a no-move history lesson, so it did not exercise a move-specific legal-destination scene. Its production MP4 was inspected at two frames. At approximately 10 seconds, the frame shows the English title, the concise scene cue `Board's unique vocabulary`, a `BOARD MAP` overlay, `9 FILES`, `10 RANKS`, and the spoken-sentence cue at the bottom. At approximately 30 seconds, the frame shows `Armies, river, and palaces`, `BLACK ARMY` and `RED ARMY` overlays, the real river gap, and the spoken-sentence cue. This confirms that the in-video teaching cues remain enabled in a real public production while the separate English YouTube caption track is disabled in `localization.json` (`enabled: false`, `in_video: true`).
