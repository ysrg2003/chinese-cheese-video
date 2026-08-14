# Latest visual alignment audit: The 9×10 Point Board

## Scope

This audit compares the narration and visible visual treatment in production video `ErLAZQvHUiM`, job `curriculum-en-005-the-9x10-point-board-en`, with the intended educational meaning of each sentence.

## Timeline and required visual contract

| Time | Spoken idea | Current gap | Required visual treatment |
|---|---|---|---|
| 00:00–00:03 | A move happens on the board | Mostly a general starting board | Show the complete corrected board, with a restrained locator pulse on the board intersections rather than a generic title only. |
| 00:03–00:08 | Nine files, ten ranks, ninety intersections | The scene emphasizes a single point and a title | Sequentially draw or illuminate all nine vertical files, all ten horizontal ranks, then pulse the 90 intersection points. |
| 00:08–00:14 | Pieces stand on intersections; movement follows lines | Generic circle and path lines do not clearly bind to a named piece | Select one real piece on the actual board, highlight its intersection, and draw legal path candidates along the board lines. |
| 00:14–00:21 | The river divides sides; central files connect palaces | Labels exist, but the regions do not carry enough visual weight | Shade the river band, outline both central 3×3 palaces with correct X diagonals, and highlight the three central files. |
| 00:21–00:26 | Board is a route map, not enclosed squares | Existing line emphasis is too generic | Dim square interiors and brighten the intersection network; avoid presenting a square-grid chessboard mental model. |
| 00:26–00:34 | Chariot open file, cannon screen, horse leg | A generic repeated overlay is not specific enough | Use three deterministic mini-demonstrations on legal positions: chariot rays along an open file, cannon source-screen-target with exactly one screen, and horse L-targets with a visible leg block/clear comparison. |
| 00:34–00:42 | Review points, files, ranks, and routes | Return to a plain board without a structured recap | Cycle through the four concepts with short, non-overlapping cues and reset to the legal initial position. |

## Routing decision

The system should not ask an image model to invent an entire board or infer legal Xiangqi geometry. It should use deterministic Remotion overlays for board topology, pieces, legal destinations, river, palaces, files, ranks, cannon screens, horse legs, and move paths. The external reference-edit image service should be used only for concept assets that cannot be represented accurately by overlays, and every such asset must be attached to a specific narration segment with a file hash, scene mapping, and timing window.

## Fail-closed acceptance criteria

Every narration segment must have a non-empty `visualPlan` containing a semantic purpose, visual kind, source mode, and timing. Technical terms such as `file`, `rank`, `intersection`, `river`, `palace`, `screen`, and `horse leg` must map to their corresponding deterministic visual primitives. A segment must not pass production if it only has a headline or a generic board scene while its narration contains a technical concept that requires a specific overlay.

## Source

The audit was produced from the rendered MP4, its production `job.json`, and the current Remotion scene mapping. It is an implementation baseline for the next visual-director revision.

## Semantic proof render findings — frames 1 and 2

The deterministic proof render confirms that the `Nine Files, Ten Ranks` segment visibly draws F1–F9, R1–R10, and the intersection markers on the corrected board. The `Points And Paths` frame correctly changes the headline and enters the legal-destination scene, but the sampled frame did not visibly expose the blue destination points strongly enough. This is a useful failure signal: legal-target overlays must remain visible for the whole explanatory window and must not be hidden by an over-specific `piece_movement` fallback when the board position or focus piece cannot be resolved. The next render check should verify the exact timing and, if needed, strengthen the anchor/target treatment.

## Semantic proof render findings — frames 3 and 4

The `River And Palaces` frame is now directly explanatory: the river band, both central palace boundaries, their X diagonals, and the three central files are highlighted on the canonical board. The movement-constraints frame is also materially improved: it shows an open-file ray from a chariot, a cannon line with one highlighted screen and target, and a horse-leg marker with an L-route cue. These are specific visual counterparts to the narrated terms, not generic decorative motion.

## Points and paths fix

The first points/paths sample exposed a renderer gate bug: the semantic SVG container did not activate for `piece_anchor`, `legal_destinations`, or `path_lines` alone. After adding those primitives to the container condition and selecting a deterministic red pawn focus, the final frame visibly shows the red pawn at `[0,6]` with a gold origin ring, a blue legal destination at `[0,5]`, and the connecting path. The displayed destination is produced by `legalDestinationsForPiece`, not an invented coordinate.

## Follow-up: production artifact en-006 and AI-path hardening

The first production-equivalent en-006 artifact proved that the initial semantic director worked for explicit technical sentences, but it also exposed a gap in the AI storyboard path: phrases such as “river separates territories,” “general and advisors,” “palace entry points,” and “predict which routes are open, restricted, or impossible” could inherit broad AI plans such as `river_palaces` or `intersections` without the corresponding renderer primitives.

The hardening change makes the deterministic contract authoritative after AI normalization. It maps those sentences to `territory_split`, `palace_piece_anchor`, `palace_entry_points`, and `route_constraints`, respectively, and rejects unknown `board_overlay` primitives before rendering. The Remotion layer now draws each primitive on the canonical 9×10 intersection board. A local corrected en-006 render was inspected at 2, 7, 13, 18, and 33 seconds; the river, territory tint, palace anchors, entry points, central files, and palace boundaries all appeared in the intended scenes.

## Follow-up: setup inventory hardening from en-007

The first public en-007 artifact exposed a separate AI-path mismatch: a sentence counting the piece families inherited a generic “Three Movement Constraints” visual. The deterministic contract now detects mirrored setup, inventory, and starting-home language before piece-rule keywords. It produces an `army_setup` plan with `piece_family_anchor` and `mirror_setup`, or with `river_band` when the sentence describes soldiers facing the river. The renderer draws colored rings around the actual pieces in the canonical starting FEN and a center-file mirror axis; it does not animate or invent a move. A local corrected en-007 render was inspected at 2 and 7 seconds, and the only redundant top marker was removed before commit.

## Follow-up: coordinate notation hardening from en-008

The first public en-008 artifact exposed one more AI-path mismatch: the narration gave a concrete source coordinate, destination coordinate, and replay notation habit, while the generated storyboard used `coordinate_map` labels or a generic `rule_focus` without marking the endpoints. The deterministic contract now maps these sentences to `coordinate_endpoints` and `notation_sequence`. Remotion draws the example from file 2/rank 8 to file 2/rank 5 on the actual intersections, labels `SOURCE F2 R8` and `DEST F2 R5`, and displays `IDENTIFY → START → END → LEGAL CHECK`. The path is explicitly an example notation path and does not claim that a game was played.
