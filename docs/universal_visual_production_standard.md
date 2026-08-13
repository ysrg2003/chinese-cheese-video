# Universal Visual Production Standard

## Goal

Every future Xiangqi video is now produced as an audio-visual lesson rather than as detached narration over a passive board. The production system runs inside GitHub Actions, calls the independent AI Provider Router when available, and continues with deterministic educational fallbacks when every external AI provider fails. Manus is not required for daily execution.

## What happens for every job

After the director creates the natural English or Chinese narration and the move list, `visual_director.py` receives the actual narration segments, move coordinates, move purpose, opponent reply, effect, content type, objective, hook, and analysis focus. It asks the AI Router for one scene per narration segment. The response contains a short headline, a concise caption, a supported `visualKind`, and a concrete visual instruction. For normal move videos, the spoken narration is preserved; the storyboard is attached to the existing speech and move windows rather than replacing the script.

The Remotion composition reads the active narration segment at the current video time and renders the corresponding board-side signal. It can show a board map, army setup, a piece path, an attack line, a defense zone, a threat marker, a capture sequence, cannon-screen geometry, a before/after comparison, a game-phase highlight, a viewer question, or a result marker. The piece movement itself continues to use the independent short animation window, normally 0.55–0.95 seconds, while the MoveCard and spoken explanation remain visible for the full narration window.

## Content-specific visual behavior

| Content family | Default visual behavior |
| --- | --- |
| Foundation lesson | Seven explicit visual teaching scenes: battlefield, armies, goal, intersections, river and palaces, cannon geometry, and learning roadmap. No unexplained training game. |
| Board and setup | Board map, army tinting, setup regions, palace and river markers, and coordinate signals. |
| Piece academy | A supplied legal move path, source and destination markers, and a focused piece movement cue. |
| Openings and tactics | Attack lines, forcing-path signals, cannon-screen geometry, capture markers, and threat highlights. |
| Endgames | Defense zones, result markers, and conversion-focused board regions. |
| Complete games | Game-phase and turning-point markers attached to the existing move sequence. |
| Comparisons | Before/after and split-comparison cues while keeping the Xiangqi board readable. |
| Viewer challenges and puzzles | A question/reveal marker around the candidate point, followed by the supplied move and result. |
| Trend breakdowns and skill matches | Before/after, comparison, threat, and plan markers selected from the supplied content type and move data. |

## AI and fallback behavior

The AI Router is an enhancement layer, not a single point of failure. If it returns valid scenes in the requested language, the scenes are used. If it returns malformed JSON, an unsupported kind, the wrong number of scenes, forbidden language, or fails through all configured providers, the deterministic fallback creates a valid scene from the current segment. Cannon moves receive `cannon_screen`; other moves receive `move_path`; tactical and opening segments receive `attack_line`; comparisons receive `comparison_split`; challenges receive `question_reveal`; and complete-game segments receive `game_phase`.

The first foundation episode may use an approved storyboard stored in the curriculum JSON. That makes the public first lesson reproducible even if the provider is temporarily unavailable. Future ordinary videos do not need a prewritten storyboard in the curriculum because the generic fallback can derive one from the job data.

## Timing and publication safety

The audio path first uses Edge-TTS word-boundary timing. If word cues are unavailable, the pipeline probes the generated MP3 with `ffprobe` and uses the actual audio duration. `finalize_timing` then fits narration segments and captions to that duration. The latest scene cannot extend beyond the spoken audio window.

Before rendering or YouTube upload, `validate_visual_storyboard` checks that the storyboard exists, the scene count matches the narration segment count, every scene uses a supported visual kind and has a headline and visual instruction, every move segment references an existing move, and no scene exceeds the actual audio duration. If validation fails, `run_pipeline.py` raises an error before render/publication and marks the job failed. The workflow now has an explicit `autonomous_run` step id, so a production failure also makes GitHub Actions fail instead of appearing successful.

## Autonomous execution

GitHub Actions remains scheduled three times daily and uses English by default. The workflow explicitly sets `VISUAL_STORYBOARD_ENABLED=1`, keeps the male voices `en-US-GuyNeural` and `zh-CN-YunjianNeural`, runs the independent AI Router, renders Remotion, publishes public YouTube videos when the repository variable enables publishing, associates the correct playlist, exports the catalog, and commits the SQLite state. The next scheduled or manually dispatched production automatically uses this standard; no Manus session needs to be open.

To intentionally disable the visual layer for a special job, set `visual_mode` to `none`. This is an explicit opt-out, not the default.

## Verification completed

The implementation is in GitHub commit `4a011f0`. The local suite passes 26 tests, including generic move storyboard creation, fallback behavior, storyboard validation, audio-duration boundaries, fast move animation, YouTube idempotency, playlist association, and the existing curriculum tests. Python compilation, workflow validation, and TypeScript typecheck pass. A 1080×1920 generic cannon-tactics preview was rendered with Edge-TTS and showed a real screen piece, a cannon path, source/destination markers, MoveCard, and a short aligned caption. A second move preview showed the next move path without headline overlap.
