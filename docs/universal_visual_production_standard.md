# Universal Visual Production Standard

## Goal

Every future Xiangqi video is now produced as an audio-visual lesson rather than as detached narration over a passive board. The production system runs inside GitHub Actions, calls the independent AI Provider Router when available, and continues with deterministic educational fallbacks when every external AI provider fails. Manus is not required for daily execution.

## What happens for every job

After the director creates the natural English or Chinese narration and the move list, `visual_director.py` receives the actual narration segments, move coordinates, move purpose, opponent reply, effect, content type, objective, hook, and analysis focus. It asks the AI Router for one scene per narration segment. The response contains a short headline, a concise caption, a supported `visualKind`, and a concrete visual instruction. For normal move videos, the spoken narration is preserved; the storyboard is attached to the existing speech and move windows rather than replacing the script.

The Remotion composition reads the active narration segment at the current video time and renders the corresponding board-side signal. It can show a board map, army setup, a piece path, an attack line, a defense zone, a threat marker, a capture sequence, cannon-screen geometry, a before/after comparison, a game-phase highlight, a viewer question, or a result marker. The piece movement itself continues to use the independent short animation window, normally 0.55–0.95 seconds, while the MoveCard and spoken explanation remain visible for the full narration window.

## What a storyboard is — and is not

A **storyboard** in this system is a small, structured JSON production plan. It binds each spoken segment to exactly one renderer-supported visual change. A scene records its segment index, optional move ply, short headline, caption, `visualKind`, and concrete `visualInstruction`. It is **not an image-generation request**, not a collection of AI-generated still images, and not a request to a text-to-image model.

The AI Router receives only a compact text-and-data request: the video language, lesson identifier and objective, content type, hook or analysis focus, narration segments, and supplied move coordinates where they exist. It returns JSON only. Remotion then draws the core teaching layer directly from the existing Xiangqi board, SVG piece assets, labels, paths, rings, regions, timeline, and teaching markers.

> A valid storyboard is an **editing specification**, not artwork: “while this sentence is spoken, highlight this board concept in this supported way.”

## Optional generated editorial assets

A second, independent stage may add **zero to two generated visual assets** to a job. `visual_assets.py` sends the completed storyboard and spoken context to the AI Router again, but this time as a constrained **asset planner**. The planner may select only a non-move scene that genuinely benefits from a contextual establishing shot, such as a historical-scroll image for an origin story or a cultural detail for a game-identity lesson. It returns a short JSON plan with a scene index, approved role, and a tightly constrained English image prompt.

The selected prompt is sent to the authenticated `chatgpt-api` visual-assets service. The service queues the request, receives a ChatGPT-generated image, verifies its image bytes, and exposes it for immediate download. The pipeline validates the file type, byte size, dimensions, and SHA-256; saves it under `public/generated/<job-id>/assets/`; then records the relative source in the corresponding storyboard scene. The image is rendered by Remotion as a short, subtle 9:16 editorial establishing shot with a slow camera drift and quick fade-out.

| Invariant | Enforcement |
| --- | --- |
| The Xiangqi board is the teaching authority | Generated assets are an optional contextual layer that clears before detailed instruction. |
| Moves, legal rules, squares, captures, and tactics stay exact | The asset planner cannot select a move scene or move-related visual kind. Remotion continues to draw those from supplied move data. |
| No repeated stock scene is forced | The AI planner may select **zero** assets when a deterministic board signal is more appropriate. |
| An unavailable image service never blocks publication | Failure is recorded inside `visualAssets`; the job continues with the existing board storyboard and fallback. |
| Generated assets cannot bypass the validator | `validate_visual_storyboard` rejects an asset attached to a move scene, an unsafe source path, or an unsupported asset role. |

The service is authenticated with `CHATGPT_VISUAL_API_KEY`, stored as a GitHub Actions Secret; its URL and image limits are configurable through `CHATGPT_VISUAL_API_BASE`, `VISUAL_ASSET_ENABLED`, `VISUAL_ASSET_MAX_PER_VIDEO`, and `VISUAL_ASSET_TIMEOUT_SECONDS`. The remote ChatGPT session is stored only as the Hugging Face Space Secret `CHATGPT_COOKIES_NETSCAPE`; it must never appear in source control, workflow artifacts, or logs.

## Content-specific visual behavior

| Content family | Default visual behavior |
| --- | --- |
| Foundation lesson | Seven explicit visual teaching scenes: battlefield, armies, goal, intersections, river and palaces, cannon geometry, and learning roadmap. No unexplained training game. |
| History and game identity | Board overview first, then cultural/timeline context, two-army framing, board identity, and a learning roadmap. |
| Definitions, board and setup | Board map first, followed by army tinting, setup regions, palace and river markers, intersection and coordinate signals when named by the speech. |
| Rules and piece academy | A rule-focus cue or piece spotlight, then a supplied legal move path, source/destination markers, and focused movement geometry where a move exists. |
| Openings and tactics | Attack lines, forcing-path signals, cannon-screen geometry, capture markers, and threat highlights. |
| Endgames | Defense zones, result markers, and conversion-focused board regions. |
| Complete games | Game-phase and turning-point markers attached to the existing move sequence. |
| Comparisons | Before/after and split-comparison cues while keeping the Xiangqi board readable. |
| Viewer challenges and puzzles | A question/reveal marker around the candidate point, followed by the supplied move and result. |
| Trend breakdowns and skill matches | Before/after, comparison, threat, and plan markers selected from the supplied content type and move data. |

## AI and fallback behavior

The AI Router is an enhancement layer, not a single point of failure. If it returns valid scenes in the requested language, the scenes are used. If it returns malformed JSON, an unsupported kind, the wrong number of scenes, forbidden language, or fails through all configured providers, the deterministic fallback creates a valid scene from the current segment. Cannon moves receive `cannon_screen`; other moves receive `move_path`; tactical and opening segments receive `attack_line`; comparisons receive `comparison_split`; challenges receive `question_reveal`; and complete-game segments receive `game_phase`.

For **non-move lessons**, fallback is topic-aware rather than a repeated generic comparison. A historical or introductory lesson opens with `board_overview`; text mentioning the river or palaces receives `river_palaces`; armies receive `two_armies`; cannon concepts receive `cannon_geometry`; coordinates and intersections receive their corresponding overlays; rules receive `rule_focus`; pieces receive `piece_spotlight`; and a concluding learning transition receives `learning_roadmap`. Unspecified history segments can use the dedicated timeline or cultural-heritage overlays. This gives every spoken idea a distinct, renderer-backed instructional change even when all providers are unavailable.

The first foundation episode may use an approved storyboard stored in the curriculum JSON. That makes the public first lesson reproducible even if the provider is temporarily unavailable. Future ordinary videos do not need a prewritten storyboard in the curriculum because the generic fallback can derive one from the job data.

## Timing and publication safety

The audio path first uses Edge-TTS word-boundary timing. If word cues are unavailable, the pipeline probes the generated MP3 with `ffprobe` and uses the actual audio duration. `finalize_timing` then fits narration segments and captions to that duration. The latest scene cannot extend beyond the spoken audio window.

Before rendering or YouTube upload, `validate_visual_storyboard` checks that the storyboard exists, the scene count matches the narration segment count, every scene uses a supported visual kind and has a headline and visual instruction, every move segment references an existing move, and no scene exceeds the actual audio duration. It also blocks the retired generic fallback headline `What Changes Next`, repeated adjacent static fallback kinds, an unsafe generated-asset path, an unsupported asset role, or a generated asset attached to a move scene. If validation fails, `run_pipeline.py` raises an error before render/publication and marks the job failed. The workflow now has an explicit `autonomous_run` step id, so a production failure also makes GitHub Actions fail instead of appearing successful.

## Autonomous execution

GitHub Actions remains scheduled three times daily and uses English by default. The workflow explicitly sets `VISUAL_STORYBOARD_ENABLED=1`, keeps the male voices `en-US-GuyNeural` and `zh-CN-YunjianNeural`, runs the independent AI Router, renders Remotion, publishes public YouTube videos when the repository variable enables publishing, associates the correct playlist, exports the catalog, and commits the SQLite state. The next scheduled or manually dispatched production automatically uses this standard; no Manus session needs to be open.

To intentionally disable the visual layer for a special job, set `visual_mode` to `none`. This is an explicit opt-out, not the default.

## Verification completed

The core visual-standard implementation began in GitHub commit `4a011f0`; the optional asset layer extends it with `visual_assets.py`, protected service credentials, image validation, and Remotion integration. The local suite now passes 32 tests, including generic move storyboard creation, fallback behavior, asset-plan filtering, image-byte validation, generated-asset move protection, storyboard validation, audio-duration boundaries, fast move animation, YouTube idempotency, playlist association, and curriculum tests. Python compilation and TypeScript typecheck pass. A live visual-assets smoke test completed through the deployed service and returned a 941×1672 PNG historical establishing image. A 1080×1920 Remotion composite confirmed that the generated asset sits below the title, captions, and board overlays, then clears before the deterministic Xiangqi teaching scene.
