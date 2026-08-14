# Xiangqi Lab Visual Specification

**Status:** Production freeze active until a non-publishing acceptance sample passes.

## Board geometry

The board is a deterministic 9-file by 10-rank point grid. The 90 playable locations are line intersections; no piece is centered inside a square. The red side occupies the lower ranks and the black side occupies the upper ranks in the renderer coordinate system.

The river is the full-width band between ranks 5 and 6. The eight interior vertical lines stop at the river edges; they must not continue through the river. The two outer border lines may remain continuous. The river band must visibly separate the armies and must display `楚河` on the left half and `漢界` on the right half for the canonical board.

Each palace occupies files 4–6 and three ranks on its side: ranks 1–3 for black and ranks 8–10 for red. Each palace has two diagonals crossing from opposite corners to form an X. The palace is not located in the leftmost three files.

Pieces are circular discs centered exactly on intersections. The standard starting arrangement is symmetrical: back rank `rook, horse, elephant, advisor, general, advisor, elephant, horse, rook`; cannons on files 2 and 8 on the third rank from each side; soldiers on files 1, 3, 5, 7, and 9 on the fourth rank from each side. Red and black use distinct traditional glyph variants where applicable, including `帥/將`, `仕/士`, `相/象`, and `兵/卒`.

## Rendering invariants

All board coordinates used by overlays, move arrows, reference masks, thumbnails, and legal-move animation must use the same geometry constants. Any mismatch between the base board and overlay coordinates is a blocking defect. A move may animate only between valid intersections and must never create a flying-general, friendly-collision, palace, river, horse-leg, elephant-eye, or cannon-screen violation.

A clean thumbnail frame must be rendered from the deterministic board with `referenceMode=true`, no narration overlays, no generated backdrop, no captions, and no audio. The English thumbnail is the YouTube default thumbnail. The Chinese variant is an additional localized artifact for manual Studio use where the API cannot attach a second localized thumbnail slot.

## Generated visual assets

Generated or externally sourced images are optional editorial backdrops and never replace the canonical board. Every selected asset must satisfy all of the following conditions before rendering:

1. The file exists under the repository's `public/generated/<job_id>/assets/` tree.
2. The file is a valid supported image with verified dimensions and a recorded SHA-256 hash.
3. The asset is attached to exactly one non-move storyboard scene.
4. The scene has a matching narration segment with a visible window of at least 0.75 seconds.
5. The final job JSON contains a durable asset manifest with the source, dimensions, hash, scene index, and visibility interval.
6. The rendered acceptance frame visibly contains the asset; a ChatGPT history item or expiring signed URL is not sufficient evidence.

Reference-edit images must be based on a durable local reference frame and an exact same-size transparent mask. The edit may change only the masked region. It must preserve the board grid, pieces, labels, perspective, and every unmasked pixel. It must not invent a new board, Western chessboard, people, hands, watermarks, or unsupported text.

## Acceptance gates

The production freeze may be removed only after a non-publishing sample passes TypeScript compilation, the full Python test suite, the deterministic Xiangqi move validator, clean Remotion rendering with one pinned Remotion version, board-frame visual inspection, thumbnail generation, and the generated-asset contract. Until then GitHub Actions may not reconcile, discover, render, or publish content.
