# Xiangqi Curriculum Database and Natural Narration

## Purpose

The channel runtime now treats the learning plan as executable data rather than a document that the selector may ignore. The English sequence begins with `What Is Xiangqi?` and advances through a prerequisite-aware curriculum. The default scheduled workflow selects the earliest lesson whose prerequisites are published. RSS, trend, skill-match, community, and AI ideas remain supplementary content and are used only when no planned English curriculum lesson is available.

## Curriculum data

The source of truth is `config/xiangqi_curriculum_en.json`. It contains 72 English lessons across the following stages:

| Stage | Scope | Playlist families |
| --- | --- | --- |
| A | Definition, short history, first comparison | Start Here, Comparison Lab |
| B | Board, river, palaces, setup, coordinates, notation | Board, Setup, and Notation |
| C | General, advisor, elephant, horse, chariot, cannon, soldier, combinations | Piece Academy |
| D | First ten moves, safety, development, mini-game, full beginner game | First Games |
| E | Opening principles, central cannon, chariot activation, central pressure, traps | Opening Lab |
| F | Forcing moves, checks, captures, threats, cannon screen, horse eye, flying general, pinned line | Tactics 101 |
| G | Bronze, Silver, Gold, and Master puzzle ladder | Puzzle Ladder |
| H | Middlegame plans, open lines, coordination, initiative, palace targets, plan changes | Middlegame Strategy |
| I | Soldier, chariot, cannon, and draw endgames | Endgame Lab |
| J | Complete games with critical-move analysis | Full Games |
| K | Triple checks, palace sacrifices, repetition, and chasing cautions | Advanced Tactics and Rules |
| L | Chess, Shogi, Janggi, Go, and calculation-style comparisons | Comparison Lab |
| M | Viewer positions, beginner review, engine/human analysis, master patterns, graduation game | Community Review, Master Patterns, Full Games |

Each row stores a stable lesson key, sequence number, stage, playlist key, content type, difficulty, format, target duration, title, objective, hook, analysis focus, position template, and prerequisite lesson keys. The local SQLite schema stores these in `curriculum_lessons`; `curriculum_episode_plans` stores one English state row per lesson, including `planned`, `queued`, `processing`, `published`, `retry`, `failed`, or `blocked`, along with candidate ID, job ID, attempts, error, and publication timestamp.

The first eligible row is `en-001-what-is-xiangqi`. After its English episode reaches `published`, the selector unlocks `en-002-xiangqi-in-60-seconds`, and so on. A failed lesson is returned as `retry` and is attempted again before later lessons are unlocked. This prevents a later tactics video from silently replacing a missing foundation lesson.

## Natural move-by-move narration

The director contract now requires a natural introduction plus per-move fields for purpose, likely opponent reply, effect of that reply, and next plan. A move segment is spoken in this form:

> Move 1. Red pawn moves from file 1, rank 7 to file 1, rank 6 to open a route. The likely reply is to contest the new line. That changes the position: the board rule changes the available plans. Next, watch the board rule in action.

The exact AI-generated purpose, reply, and effect are used when they are valid English. When AI is unavailable, the curriculum position template and content type provide a safe, rights-free fallback that still explains the move as part of a conversation between plans. The renderer no longer narrates only coordinates or gives a detached definition while an unrelated move is shown.

## Caption behavior

The audio segment and the board move share one time window. The spoken segment may contain the full natural explanation, while its `captionText` is a shorter readable phrase spoken within that segment. Intro captions carry `captionPosition=bottom`; move captions carry `captionPosition=board`. The Remotion composition renders the introduction caption near the bottom above the footer and renders move captions above the board below the MoveCard. The active caption disappears outside its segment window.

If Edge-TTS WordBoundary data is available, the segment windows come from the audio cues. If it is unavailable, the timing layer distributes the introduction and move segments proportionally and applies those same windows to moves and captions. This also makes `skip_tts` previews structurally faithful without allowing a full transcript to persist across the video.

## YouTube catalog integration

The curriculum row supplies `playlist_key` directly to the publisher. The publisher uses that key when it exists in `config/youtube_playlists.json`; otherwise it falls back to the older content-type policy. The expanded English playlist catalog includes Board Setup, First Games, Advanced Tactics, Middlegame, Rule Traps, Master Patterns, Community Review, and Shorts in addition to the existing families.

`youtube-catalog.json` now includes the normalized channel, playlists, videos, video-playlist associations, the full English curriculum, and a curriculum summary. This gives each GitHub Actions artifact both production state and educational progress.

## Verification

The local suite passed 17 tests, including curriculum seed and prerequisite-unlock tests, natural narration and caption-position tests, playlist override tests, publication idempotency tests, and fake-API retry tests. Python compilation, TypeScript typechecking, workflow validation, and a local Remotion render passed. The first preview showed the introduction caption at the bottom and a short move caption above the board while the previous caption was hidden.

## References

[1]: https://www.wxf-xiangqi.org/index.php?option=com_content&view=article&id=269&Itemid=291&lang=en "World Xiangqi Federation — World Xiangqi Rules"

[2]: https://www.wxf-xiangqi.org/images/wxf-rules/2018_World_XiangQi_Rules_English2018.pdf "World Xiangqi Rules — English PDF"

[3]: https://www.chess.com/blog/SamCopeland/how-to-play-chinese-chess "Chess.com — How To Play Chinese Chess (Xiangqi)"
