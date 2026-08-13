# Curriculum-Driven Xiangqi Production Completion Report

## Executive result

Chinese Cheese Video now has an executable English-first curriculum rather than a loose collection of discovered ideas. The first eligible lesson is `en-001-what-is-xiangqi`, and the selector will unlock subsequent lessons only after the previous lesson reaches `published`.

Workflow `31662002754` completed successfully from commit `88e1710` and published the first curriculum lesson publicly:

| Field | Value |
| --- | --- |
| Lesson | `en-001-what-is-xiangqi` |
| Stage | `A-foundations` |
| Title | `What Is Xiangqi?` |
| Language | English |
| Content type | `definition` |
| Playlist key | `en-start-here` |
| YouTube URL | https://www.youtube.com/watch?v=VHOQ3xPjyg8 |
| YouTube duration | 1:19 |
| Artifact duration | 78.745 seconds |
| YouTube publication | `published` / public |
| Caption source | `move_narration_audio` |
| Curriculum status | 1 published, 71 planned |

The artifact contained 1 channel, 30 playlist definitions, 8 catalogued videos, 8 video-playlist associations, and 72 curriculum rows. The live YouTube page opened under `Xiangqi Lab | 中国象棋实验室` and displayed the public title and duration.

## Database contract

`config/xiangqi_curriculum_en.json` is the editable source of truth for 72 English lessons. Each lesson specifies a stable key, sequence number, stage, playlist, type, difficulty, format, target duration, title, objective, hook, analysis focus, board template, and prerequisites.

SQLite creates and seeds two curriculum tables automatically:

| Table | Role |
| --- | --- |
| `curriculum_lessons` | The ordered syllabus and all editorial/board metadata. |
| `curriculum_episode_plans` | One state row per lesson-language pair, with status, attempts, candidate ID, job ID, error, and publication time. |

The Postgres equivalent is available in `sql/002_curriculum_schema.sql`. The current GitHub Actions runtime remains local SQLite, which is persistent through the workflow catalog checkout/commit process.

## Selection behavior

At every unattended run, discovery still collects RSS, YouTube, pairing, evergreen, and AI ideas for the supplementary pool. However, the selector first asks the curriculum database for the earliest `planned` or `retry` English lesson whose prerequisite keys are all published. It materializes that lesson as a stable candidate and processes one curriculum lesson. This means daily execution starts with foundations and cannot jump to advanced tactics simply because an RSS item has a higher priority score.

When the 72-lesson core path is exhausted, the existing diversity selector becomes the fallback. It continues to prevent duplicate topic keys, duplicate FEN/move signatures, and consecutive type repetition.

## Natural narration

The director now separates the introduction from move explanations. Each move explanation states the move, its purpose, the likely opponent reply, the effect of that reply, and the next plan. An English fallback example is:

> Move 1. Red pawn moves from file 1, rank 7 to file 1, rank 6 to open a route. The likely reply is to contest the new line. That changes the position: the board rule changes the available plans. Next, watch the board rule in action.

AI-generated `purpose`, `opponentReply`, and `effect` fields are used when valid. If all AI providers fail, the curriculum position template and content type provide a coherent fallback rather than a static generic sentence.

## Caption and visual behavior

The full natural explanation remains in the audio. A shorter `captionText` is displayed for readability. Introduction captions carry `captionPosition=bottom` and are shown near the bottom above the footer. Move captions carry `captionPosition=board` and are shown above the board under the MoveCard. The current active caption disappears outside its segment window.

When Edge-TTS WordBoundary data exists, the same audio-derived windows are assigned to the narration segment, board move, and caption. When it does not, the timing layer distributes the segments proportionally and applies the same fallback windows to all three. This preserves the visual contract during previews and provider failures.

## Verification

The project passed 17 unit tests plus Python compilation, TypeScript typechecking, workflow validation, and local Remotion rendering. The live artifact confirmed one intro plus three move segments for the first curriculum lesson, with move windows 17.696–38.045, 38.045–57.953, and 57.953–78.745 seconds. The local preview confirmed the introduction caption at the bottom and a move caption above the board without overlap.

## References

[1]: https://www.wxf-xiangqi.org/index.php?option=com_content&view=article&id=269&Itemid=291&lang=en "World Xiangqi Federation — World Xiangqi Rules"

[2]: https://www.wxf-xiangqi.org/images/wxf-rules/2018_World_XiangQi_Rules_English2018.pdf "World Xiangqi Rules — English PDF"

[3]: https://www.chess.com/blog/SamCopeland/how-to-play-chinese-chess "Chess.com — How To Play Chinese Chess (Xiangqi)"
