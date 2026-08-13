# Curriculum audit findings

The channel plan already defines a structured learning promise, fifteen English/Chinese playlist families, ten learning stages A–J, a 60-episode launch list, and a twelve-week release program in `docs/youtube_channel_plan.md`.

The runtime does not yet execute that plan as data. SQLite has candidate, job, publication, YouTube catalog, AI, and automation tables, but no curriculum lesson table, prerequisite relation, sequence pointer, milestone, or episode-plan state. `content_discovery.py` currently seeds only eight perpetual ideas per ISO week and mixes them with RSS, YouTube, pairing, and AI candidates. `automation_runner.py` rotates content types and filters duplicate topics/move signatures, but it does not ask for the next planned lesson or mark a lesson complete.

The target design therefore needs a seeded curriculum catalog containing: stage, playlist key, lesson order, stable lesson key, title, purpose, audience level, format, prerequisite lesson keys, required concept tags, target duration, hook, narrative focus, board position/moves, and status. A separate episode-plan table should track each lesson-language pair, attempt count, selected job ID, publication status, and completion timestamp. Trend, pairing, community, and AI candidates should remain available as controlled supplementary content without changing the next planned lesson pointer.

The requested English-first behavior means the English lesson row is the reference episode. Chinese rows can be generated independently later from the same curriculum lesson and board position, but should not be mixed into the English sequence.
