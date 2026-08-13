# Curriculum Database and Natural Narration

## Purpose

The channel runtime treats the learning plan as executable data rather than as a document that the selector may ignore. The default scheduled workflow selects the earliest English lesson whose prerequisites are published. Discovery, trend, skill-match, community, and AI-generated ideas remain supplementary content and are used only when no planned English curriculum lesson is available.

The curriculum now follows a genuine beginner path. The viewer first learns what Xiangqi is, sees the board and its special regions, learns the complete setup and coordinate language, studies each piece family with isolated legal examples, and only then reaches training games, openings, tactics, full games, comparisons, and community analysis.

## Curriculum data

The source of truth is `config/xiangqi_curriculum_en.json`. It contains 72 English lessons across the following stages:

| Stage | Scope | Playlist families |
| --- | --- | --- |
| A | What Xiangqi is, history, board orientation, piece academy, first game | Start Here, Board Setup, Piece Academy, First Games |
| B | Board geometry, river, palaces, setup, coordinates, and notation | Board Setup |
| C | General, advisor, elephant, horse, chariot, cannon, soldier, and combinations | Piece Academy |
| D | First ten moves, safety, development, mini-game, and full beginner game | First Games |
| E | Opening principles, central cannon, chariot activation, pressure, and traps | Opening Lab |
| F | Forcing moves, checks, captures, threats, cannon screen, horse eye, flying general, and pinned line | Tactics 101 |
| G | Bronze, Silver, Gold, and Master puzzle ladder | Puzzle Ladder |
| H | Middlegame plans, open lines, coordination, initiative, palace targets, and plan changes | Middlegame Strategy |
| I | Soldier, chariot, cannon, and draw endgames | Endgame Lab |
| J | Complete games with critical-move analysis | Full Games |
| K | Triple checks, palace sacrifices, repetition, and chasing cautions | Advanced Tactics and Rules |
| L | Xiangqi compared with chess, Shogi, Janggi, Go, and other decision styles | Comparison Lab |
| M | Viewer positions, beginner review, engine/human analysis, master patterns, and graduation game | Community Review, Master Patterns, Full Games |

The first foundational sequence is deliberately explicit:

| Sequence | Lesson | Visual contract |
| ---: | --- | --- |
| 1 | `What Is Xiangqi?` | A complete starting board remains still. There is no training game and no unrelated move sequence. |
| 2 | `A Short History of Xiangqi` | The starting board remains visible while the narrator explains the game’s identity and history carefully. |
| 3 | `The 9×10 Point Board` | The viewer learns intersections, files, ranks, and routes before any move is played. |
| 4 | `The River and the Two Palaces` | The river and palace regions are introduced as visual board features. |
| 5 | `Set Up All 32 Pieces` | The complete starting arrangement is shown without turning setup into a game. |
| 6 | `How Xiangqi Coordinates Work` | The coordinate language is taught on the complete arrangement. |
| 7–13 | General, advisors, elephants, horses, chariots, cannons, and soldiers | Each piece lesson uses a focused legal movement example after the learner knows the board and setup. |
| 14 | `How to Read a Xiangqi Move` | Source point, destination point, piece identity, and board arrow are connected. |
| 15 | `Xiangqi in 60 Seconds` | A short recap comes after the viewer has the required vocabulary. |
| 16 onward | Combinations, first moves, games, openings, tactics, and advanced material | Real move sequences are introduced only after the foundational contract is complete. |

Each lesson stores a stable key, sequence number, stage, playlist key, content type, difficulty, format, target duration, title, objective, hook, analysis focus, visual mode, visual focus, position template, and prerequisite lesson keys. The local SQLite schema stores these in `curriculum_lessons`; `curriculum_episode_plans` stores one English state row per lesson, including `planned`, `queued`, `processing`, `published`, `retry`, `failed`, or `blocked`, together with candidate ID, job ID, attempts, error, and publication timestamp.

Static introductory lessons use `visual_mode=static_board`, `position_template=board-only`, and `moves=[]`. This is intentional. It prevents the generic three-move template from appearing before the viewer understands what the board represents. Piece-academy lessons retain explicit move examples, and game or tactics lessons retain their multi-move instructional sequences.

The selector returns the earliest planned or retry lesson whose prerequisite keys are published. A failed lesson is retried before later lessons are unlocked. This prevents a later tactics video or a random discovery topic from silently replacing a missing foundation lesson.

## Natural move-by-move narration

For lessons that contain moves, the director contract requires a natural introduction plus per-move fields for purpose, likely opponent reply, effect of that reply, and next plan. A move segment is spoken in this form:

> Move 1. Red pawn moves from file 1, rank 7 to file 1, rank 6 to open a route. The likely reply is to contest the new line. That changes the position: the board rule changes the available plans. Next, watch the board rule in action.

The exact AI-generated purpose, reply, and effect are used when valid English. When AI is unavailable, the curriculum position template and content type provide a safe English fallback that still explains the move as a conversation between plans. The renderer does not narrate only coordinates or show an unrelated move under a detached definition.

Static foundation lessons use an intro-only script that explains the board, regions, setup, or coordinate language. The intro is split into sentence-sized narration segments for display, but the spoken text remains one continuous ordered lesson. These scripts explicitly state that no training move is being played yet, so the viewer understands why the board is still.

## Motion timing and caption behavior

The audio explanation and the board move now have two different time contracts. `startSec` and `endSec` describe the full spoken explanation window: the MoveCard and the move caption remain available while the narrator explains the purpose, opponent reply, effect, and next plan. `animationStartSec` and `animationEndSec` describe the actual board transition. The animation normally starts at the beginning of the move segment and completes in approximately 0.55–0.95 seconds, scaled slightly by travel distance. The piece therefore moves at a natural speed instead of crawling for the entire paragraph.

The board uses `animationStartSec` and `animationEndSec` for interpolation. After `animationEndSec`, the piece is already at its destination while the rest of the explanation continues. Old jobs that do not contain the new optional fields remain compatible because the renderer falls back to `startSec` and `endSec`.

| Speech element | Timing window | Visual placement |
| --- | --- | --- |
| Intro sentence | Its aligned Edge-TTS sentence window | Bottom caption box above the footer |
| Move explanation | Its aligned Edge-TTS move window | Short caption above the board and MoveCard |
| Piece transition | `animationStartSec` → `animationEndSec` | Fast natural movement, normally under one second |
| After the piece arrives | Remaining move speech window | Piece stays on the destination while analysis continues |

If Edge-TTS WordBoundary data is available, narration segment windows come from the audio cues. If it is unavailable, the timing layer distributes segments proportionally. In both cases the move speech window and caption window stay aligned, while the board animation receives its own short window.

Intro captions are now split into short sentence-sized cues instead of displaying the entire lesson transcript as one persistent block. Move captions remain concise and disappear outside their move segment. The Remotion composition renders intro captions near the bottom and move captions above the board below the MoveCard.

## YouTube catalog integration

The curriculum row supplies `playlist_key` directly to the publisher. The publisher uses that key when it exists in `config/youtube_playlists.json`; otherwise it falls back to the content-type policy. The expanded English playlist catalog includes Board Setup, First Games, Advanced Tactics, Middlegame, Rule Traps, Master Patterns, Community Review, and Shorts in addition to the existing families.

`youtube-catalog.json` includes the normalized channel, playlists, videos, video-playlist associations, the full English curriculum, and a curriculum summary. Each GitHub Actions artifact therefore contains both production state and educational progress.

## Verification

The local suite now passes 26 tests. It covers curriculum seeding, the static first lesson, prerequisite unlocking, piece lessons retaining move examples, natural narration, caption positions, fast animation windows, audio-alignment timing, universal storyboard fallback, generic move visual beats, storyboard validation, playlist overrides, publication idempotency, and fake-API retry behavior. Python compilation, workflow validation, and TypeScript typechecking pass. Remotion previews were rendered at 1080×1920 for the foundation lesson and a generic cannon tactic; the latter showed a real screen piece, move path, MoveCard, and aligned short caption without headline overlap.

## References

[1]: https://www.wxf-xiangqi.org/index.php?option=com_content&view=article&id=269&Itemid=291&lang=en "World Xiangqi Federation — World Xiangqi Rules"

[2]: https://www.wxf-xiangqi.org/images/wxf-rules/2018_World_XiangQi_Rules_English2018.pdf "World Xiangqi Rules — English PDF"

[3]: https://www.chess.com/blog/SamCopeland/how-to-play-chinese-chess "Chess.com — How To Play Chinese Chess (Xiangqi)"

## Dynamic foundation storyboard

The first lesson is no longer a static-board exception. It uses `visual_mode=foundation_storyboard` and carries a validated seven-scene storyboard. The AI visual director proposes learner-facing narration, a short caption, a headline, a permitted visual kind, and a renderer instruction. The supported visual kinds are `battlefield`, `two_armies`, `generals_goal`, `intersections`, `river_palaces`, `cannon_geometry`, and `learning_roadmap`.

The production pipeline sends the storyboard request through the same ordered AI Router used by the director. A schema-and-language gate rejects malformed, non-English, or unsupported scenes. When all providers fail, a deterministic seven-scene educational fallback still produces meaningful visual changes rather than a silent voiceover over an unchanged board. For the regenerated first episode, the approved AI storyboard is stored in the curriculum JSON so that the public rerender is reproducible and does not depend on a transient provider response.

Each scene is aligned to its Edge-TTS narration window. Remotion then applies the corresponding overlay: file/rank markers and a board frame, army tinting and direction markers, General spotlights and a goal line, glowing intersections, river and palace boundaries, an actual screen piece between cannon and target, or a roadmap beneath the board. This is intentional signaling and temporal contiguity: the picture changes at the same moment as the spoken idea.


## Universal visual storyboard standard

The visual storyboard is no longer limited to the first foundation lesson. Unless a job explicitly sets `visual_mode` to `none`, the pipeline attaches one validated visual beat to every narration segment. Foundation lessons retain their seven-scene teaching sequence; ordinary lessons, tactics, openings, endgames, complete games, comparisons, viewer challenges, skill matches, and trend breakdowns receive move paths, attack lines, defense zones, cannon-screen demonstrations, before/after markers, question reveals, game-phase markers, or result summaries according to the content type and supplied move data.

The AI Router receives the actual narration segments, move coordinates, move purpose, opponent reply, effect, content type, objective, hook, and analysis focus. It returns short scene headlines, captions, a supported `visualKind`, and a concrete visual instruction. The spoken narration is not replaced for ordinary jobs: the visual director attaches the scene to the existing speech and move window. The first foundation lesson is the intentional exception because its script is itself generated as seven visual teaching beats.

A deterministic fallback is always available. If every AI provider fails, the system derives a scene from the segment and its move: cannon moves use `cannon_screen`, other move explanations use `move_path`, tactical and opening ideas use `attack_line`, comparisons use `comparison_split`, challenges use `question_reveal`, and complete-game phases use `game_phase`. This means AI improves specificity but is not a runtime dependency for producing a valid educational video.

Before rendering or YouTube publication, `validate_visual_storyboard` checks that every scene has a supported kind, headline, and visual instruction; that the scene count matches the narration segments; that every move segment points to an existing move; and that the latest scene end does not exceed the actual Edge-TTS duration. A failure marks the job failed and prevents publication. Word-boundary timing is preferred, with MP3 duration probing as the fallback when word cues are unavailable.
