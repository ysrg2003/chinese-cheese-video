# Curriculum Completion and Foundation/Motion Fix Report

## Executive result

Chinese Cheese Video now has an executable English-first curriculum rather than a loose collection of discovered ideas. The project has been corrected after visual review so the beginner path starts with understanding the game and the battlefield. The first lesson is now an intro-only board lesson, not an unexplained training game. Later lessons introduce the board, river, palaces, setup, coordinates, and piece movement before the channel asks the viewer to follow a real move sequence.

The first curriculum lesson previously published publicly remains available here:

[What Is Xiangqi?](https://www.youtube.com/watch?v=VHOQ3xPjyg8)

That earlier production proved the YouTube publication path, playlist association, public privacy setting, and curriculum state update. The current code changes correct the content contract for subsequent production and also correct the board-animation timing.

| Area | Current behavior |
| --- | --- |
| Default language | English. Chinese remains supported. Arabic is not generated in either video language path. |
| First lesson visual mode | `static_board`, with a complete starting position and no training moves. |
| First lesson purpose | Explain what Xiangqi is, how the win condition works, why the board is special, and what the course will teach next. |
| Foundation order | Game concept and history, board geometry, river and palaces, all 32 pieces, coordinates, piece movement examples, notation, then games and tactics. |
| Move animation | A fast `animationStartSec` → `animationEndSec` transition, normally about 0.55–0.95 seconds. |
| Move explanation | The longer `startSec` → `endSec` speech window remains available for purpose, opponent reply, effect, and next plan. |
| Intro caption | Sentence-sized bottom cues instead of one long transcript block. |
| Move caption | Short board-positioned cue that ends with the move explanation segment. |

## Database and curriculum contract

`config/xiangqi_curriculum_en.json` is the editable source of truth for 72 English lessons. Each lesson specifies a stable key, sequence number, stage, playlist, content type, difficulty, format, target duration, title, objective, hook, analysis focus, visual mode, visual focus, board template, and prerequisites.

The ordered foundation now begins as follows:

| Sequence | Lesson | Contract |
| ---: | --- | --- |
| 1 | `What Is Xiangqi?` | Static complete board. No training sequence. |
| 2 | `A Short History of Xiangqi` | Static board while the game’s identity and history are introduced carefully. |
| 3 | `The 9×10 Point Board` | Static board geometry lesson covering intersections, files, ranks, and routes. |
| 4 | `The River and the Two Palaces` | Static visual explanation of the river and palace regions. |
| 5 | `Set Up All 32 Pieces` | Static complete starting arrangement and piece families. |
| 6 | `How Xiangqi Coordinates Work` | Static coordinate language on the starting arrangement. |
| 7–13 | General through soldiers | Focused legal movement examples for each piece family. |
| 14 | `How to Read a Xiangqi Move` | Connects piece, source point, destination point, and board arrow. |
| 15 | `Xiangqi in 60 Seconds` | A recap after the vocabulary and board map have been taught. |
| 16 onward | Combinations, first games, openings, tactics, endgames, comparisons, and community analysis | Full instructional move sequences are now appropriate. |

SQLite creates and seeds `curriculum_lessons` and `curriculum_episode_plans` automatically. The seed operation updates lesson metadata and prerequisites without changing completed publication rows. The selector returns the earliest `planned` or `retry` lesson whose prerequisites are published. A failed lesson is retried before a later lesson is unlocked.

Static foundation lessons use `visual_mode=static_board`, `position_template=board-only`, and `moves=[]`. This is the explicit guard against the previous defect in which a generic three-move template appeared before the viewer had learned the board or the pieces. The piece-academy lessons retain concrete move examples, so the viewer still sees how each piece actually moves after the setup has been explained.

## Why the first video no longer plays an unexplained training game

The first lesson now speaks directly to a new viewer. It defines Xiangqi, introduces the two armies and the checkmate goal, explains that pieces stand on intersections rather than inside squares, names the river, palaces, open lines, and cannon geometry, and states the learning sequence. The board remains still while this information is delivered. There is no arbitrary pawn push, no opponent reply, and no unfinished practice game in the first orientation lesson.

The next foundation lessons make the visual vocabulary explicit. The board lesson shows the 9×10 point geometry, the river-and-palaces lesson identifies the special regions, and the setup lesson shows all 32 pieces in their mirrored starting arrangement. The piece academy then uses isolated examples for the general, advisors, elephants, horses, chariots, cannons, and soldiers. Only after those steps does the curriculum introduce first moves, mini-games, and complete games.

## Natural narration and fast movement

For lessons that contain moves, the director separates the introduction from move explanations. Each move explanation states the piece and route, its purpose, the likely opponent reply, the effect of that reply, and the next plan. An English fallback example is:

> Move 1. Red pawn moves from file 1, rank 7 to file 1, rank 6 to open a route. The likely reply is to contest the new line. That changes the position: the board rule changes the available plans. Next, watch the board rule in action.

The exact AI-generated `purpose`, `opponentReply`, and `effect` fields are used when valid. If all AI providers fail, the curriculum position template and content type provide a coherent English fallback rather than a detached generic sentence.

The previous renderer used one interval for both movement and speech, causing a piece to crawl across the board while the entire explanation was spoken. That coupling is removed. `startSec` and `endSec` remain the full narration window, while `animationStartSec` and `animationEndSec` control only the board transition. The animation starts when the move segment begins and normally completes in under one second. The piece then stays on its destination while the narrator continues explaining the position.

Old jobs without the optional animation fields remain compatible because Remotion falls back to the existing speech window. New jobs receive the fields from both ordinary retiming and Edge-TTS segment alignment.

## Caption behavior

Intro narration is split into sentence-sized segments. Each intro sentence receives a bottom caption cue, so a long transcript no longer remains on screen as one large block. Move narration retains the short `captionText` above the board under the MoveCard. Both caption types disappear outside their aligned segment windows.

When Edge-TTS WordBoundary data exists, the segment windows come from the audio cues. When it does not, the timing layer distributes the segments proportionally. In both cases the speech window and caption window remain aligned, while the piece transition receives its own short animation window.

## Verification

The project now passes 20 unit tests. The tests cover curriculum seeding, the static first lesson, prerequisite unlocking, piece lessons retaining teaching moves, natural narration, caption positions, fast animation windows, audio-alignment timing, playlist overrides, publication idempotency, and fake-API retry behavior. Python compilation and TypeScript typechecking pass.

A 1080×1920 Remotion preview of the corrected first lesson showed the official title `What Is Xiangqi?`, a complete still starting board, no MoveCard, no unrelated training sequence, and a short bottom caption. A second piece-lesson preview showed the General reaching its destination quickly while the MoveCard and explanatory caption remained active for the rest of the spoken segment. The findings are recorded in `output/verification/foundation_visual_findings.md` locally and the implementation is ready for the next unattended workflow run.

## References

[1]: https://www.wxf-xiangqi.org/index.php?option=com_content&view=article&id=269&Itemid=291&lang=en "World Xiangqi Federation — World Xiangqi Rules"

[2]: https://www.wxf-xiangqi.org/images/wxf-rules/2018_World_XiangQi_Rules_English2018.pdf "World Xiangqi Rules — English PDF"

[3]: https://www.chess.com/blog/SamCopeland/how-to-play-chinese-chess "Chess.com — How To Play Chinese Chess (Xiangqi)"

## Dynamic storyboard rerender

After the originally published first video was deleted, the lesson was redesigned as a seven-scene foundation storyboard rather than being regenerated as a still-board narration. The AI visual director produced and validated the English scene script. The scenes cover the battlefield, two armies, the checkmate goal, intersections, river and palaces, cannon geometry, and the learning roadmap.

The visual director is now part of the unattended pipeline. It uses the existing ordered AI Router and accepts only supported visual kinds, English learner-facing narration, short captions, and concrete renderer instructions. A deterministic fallback preserves the same educational structure if all external providers fail. The approved storyboard is stored in the curriculum data for reproducible rerendering of this first lesson.

The full local render used `en-US-GuyNeural`, produced a 55-second 1080×1920 MP4, and aligned the seven scene windows to Edge-TTS timing. The visual review confirmed that the board changes with each idea: the coordinate markers sit outside the board, the two armies receive separate visual emphasis, the Generals are spotlighted for the checkmate goal, intersections are marked, the river and palaces are outlined, a real screen piece appears between cannon and target, and the roadmap appears at the end.
