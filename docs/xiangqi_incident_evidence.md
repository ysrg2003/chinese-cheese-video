# Xiangqi move-validity incident evidence

## Scope

This is an internal evidence note for the Xiangqi production reliability fix. It does not contain credentials or user session data.

## Confirmed code paths

`python/director.py` asks the AI director to return arbitrary `from`, `to`, `piece`, and `side` values, but it does not validate those values against a Xiangqi position. If the AI provider fails, `_fallback()` uses hard-coded `DEFAULT_MOVE_VARIANTS` and `_parse_move_token()` converts every string token into a pawn move regardless of the actual piece on the FEN board.

Examples of fallback strings that are not legal pawn moves include `1,7-1,4`, `0,9-0,5`, and `3,9-4,8`. The first two are multi-square or geometrically incompatible with a pawn; the third is treated as a pawn even though the starting square is not a legal pawn origin for that movement. These fallbacks are therefore unsafe as instructional Xiangqi examples.

`python/run_pipeline.py` calls `make_job()`, optional storyboard validation, audio generation, Remotion rendering, and YouTube publication. There is no deterministic Xiangqi legal-move validator between `make_job()` and `render_job()`, and no validator before `publish_video()`.

The current system can therefore produce a fluent English narration for a move that is illegal, and the narration builder can describe it as a legal rule or defensive plan. Caption/audio synchronization does not solve this semantic correctness failure.

## Required fail-closed behavior

A job containing any illegal move, an incorrect side-to-move transition, a blocked path violation, a palace/river restriction violation, a flying-general exposure, an invalid capture, or a mismatch between the narrated piece and the actual board piece must fail before TTS, render, upload, or YouTube publication. Static educational lessons with no moves must still pass a board-layout validator and must not invent moves in narration.

The authoritative board state must be replayed from the supplied FEN after every ply. Every move must be checked against the exact piece at its source point, the destination occupancy, path blockers, side to move, palace boundaries, river crossing rules, horse-leg and elephant-eye blockers, cannon screen count, soldier direction, and the flying-general constraint.
