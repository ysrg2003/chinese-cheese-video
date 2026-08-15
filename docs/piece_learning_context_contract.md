# Piece-Learning Context Contract

## Purpose

During the English-first Piece Academy stage, a demonstration may use supporting pieces before reaching the target piece. The narration must keep the learner oriented without turning the lesson into a second full lesson for every supporting piece.

> The system gives a short movement reminder for each supporting piece, identifies whether that piece was taught earlier or will be taught later, and then returns to the target piece.

## Scope

The contract is enabled only when `teaching_scope` is `piece_rules` or `piece_rules_review`, or when `curriculum_stage` is `C-piece-academy`. It is disabled for foundations, openings, tactics, endgames, comparisons, viewer challenges, trend breakdowns, skill matches, and full-game videos.

| Piece relationship | Required narration behavior |
|---|---|
| Target piece | State that it is the target of the current lesson and give its concise movement summary. |
| Previously taught support piece | Give a short movement reminder and say that the full piece was covered in an earlier lesson. |
| Not-yet-taught support piece | Give a short movement reminder and say that the piece will receive a separate lesson later. |
| Non-educational stage | Do not inject piece-learning references automatically. |

## Data contract

Piece lessons may provide `target_piece`, `target_piece_name_en`, and `target_piece_movement_summary_en`. The curriculum loader carries these fields into the puzzle payload. The director then derives the supporting pieces from the selected position template and compares their first teaching sequence with the current curriculum sequence.

The helper is idempotent. If director data is sanitized more than once, the same context paragraph is not prepended twice. English jobs receive the English context; the contract does not introduce Arabic. Chinese jobs retain the existing Chinese director path and do not receive English text.

## en-013 example

The current Horse lesson uses Horse and Pawn. Horse is the target and is not treated as a previously taught piece. Pawn is used as supporting material, but the Pawn lesson occurs later in the curriculum, so the narration must say, in short form, that the Pawn moves forward before the river, gains sideways movement after crossing, and will be taught separately later. The narration then returns to Horse and explains Horse Leg.

## Safety properties

The context layer does not alter FEN, move coordinates, legality, claim proof, or visual primitives. It only adds orientation text before the existing lesson narration. Causal Xiangqi statements remain subject to the mechanical claim verifier, and the existing pre-publication visual and creative gates remain active.
