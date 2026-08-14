# Published Lessons Audit and Remediation Plan

**Channel:** Xiangqi Lab | 中国象棋实验室  
**Audit date:** 2026-08-14  
**Database snapshot:** `data/chinese_cheese_video.db` after the autonomous production-state commit `b752ef1` and the legality/localization repair commit `579c3e7`  
**Scope:** Every publication row with a stored YouTube video ID, checked against the deterministic validator in [`python/xiangqi_rules.py`](../python/xiangqi_rules.py).

## Executive conclusion

The catalog contains **14 published video records**. Six are static lessons with no move sequence and are therefore safe with respect to Xiangqi move legality. Eight contain moves, and **all eight fail the deterministic legal-content gate** when their stored `fen` and `moves` payloads are replayed. The previously known en-010 video is invalid, but it is not the only affected publication.

The eight move-bearing records must not be treated as trusted educational content. The repository now validates new jobs before narration, TTS, rendering, or publication; it also re-validates stored jobs during early-return, retry, and YouTube reconciliation paths. The existing public videos still require a YouTube action because code changes cannot retroactively change already-uploaded media.

> **Important distinction:** “Static” means that the stored job has no moves and therefore has no move legality to validate. It does not claim that every non-board aspect of a static video—wording, audio, captions, or metadata—has been independently audited in this report.

## Catalog snapshot

| # | Job ID | YouTube video | Language | Status | Playlist | Stored moves | Classification |
|---:|---|---|---|---|---|---:|---|
| 1 | `news-chinese-chess-grandmaster-lei-tingjie-believes-ai--en` | [wmJ5-34N6z8](https://www.youtube.com/watch?v=wmJ5-34N6z8) | English | Published | `PLeAPpNpQbt4w` | 3 | **Invalid move-bearing** |
| 2 | `news-chinese-chess-grandmaster-lei-tingjie-believes-ai--zh` | [KkaGX4ujyfI](https://www.youtube.com/watch?v=KkaGX4ujyfI) | Chinese | Published | `PLVqPL589s1NI` | 3 | **Invalid move-bearing** |
| 3 | `news-xu-xiangyu-and-yan-tianqi-are-2026-chinese-chess-c-en` | [M7mQrRxIg-M](https://www.youtube.com/watch?v=M7mQrRxIg-M) | English | Published | `PLeAPpNpQbt4w` | 3 | **Invalid move-bearing** |
| 4 | `news-xu-xiangyu-and-yan-tianqi-are-2026-chinese-chess-c-zh` | [na82AsZBxKU](https://www.youtube.com/watch?v=na82AsZBxKU) | Chinese | Published | `PLVqPL589s1NI` | 3 | **Invalid move-bearing** |
| 5 | `evergreen-33-7-2026-08-13-en` | [6uZ1lxn-oUs](https://www.youtube.com/watch?v=6uZ1lxn-oUs) | English | Published | `PLNHV-O5_CF9M` | 3 | **Invalid move-bearing** |
| 6 | `evergreen-33-0-2026-08-13-en` | [tA3vZMgrfg8](https://www.youtube.com/watch?v=tA3vZMgrfg8) | English | Published | `PLQegM4WVOOdw` | 3 | **Invalid move-bearing** |
| 7 | `evergreen-33-1-2026-08-13-en` | [gSgVXtG9Snw](https://www.youtube.com/watch?v=gSgVXtG9Snw) | English | Published | `PLM7UBERmrr3o` | 3 | **Invalid move-bearing** |
| 8 | `curriculum-en-001-what-is-xiangqi-en` | [oolASOuPoQc](https://www.youtube.com/watch?v=oolASOuPoQc) | English | Published | `PLNHV-O5_CF9M` | 0 | **Static; safe for move legality** |
| 9 | `curriculum-en-003-a-short-history-of-xiangqi-en` | [mQERRtjjgjk](https://www.youtube.com/watch?v=mQERRtjjgjk) | English | Published | `PLNHV-O5_CF9M` | 0 | **Static; safe for move legality** |
| 10 | `curriculum-en-005-the-9x10-point-board-en` | [7DEqaNIh3HE](https://www.youtube.com/watch?v=7DEqaNIh3HE) | English | Published | `PLEIl0EhlcPZg` | 0 | **Static; safe for move legality** |
| 11 | `curriculum-en-006-the-river-and-palaces-en` | [Tg_DcCPxXuo](https://www.youtube.com/watch?v=Tg_DcCPxXuo) | English | Published | `PLEIl0EhlcPZg` | 0 | **Static; safe for move legality** |
| 12 | `curriculum-en-007-set-up-all-32-pieces-en` | [a8xHxTuBDAM](https://www.youtube.com/watch?v=a8xHxTuBDAM) | English | Published | `PLEIl0EhlcPZg` | 0 | **Static; safe for move legality** |
| 13 | `curriculum-en-008-xiangqi-coordinates-en` | [zq7vLtLHdSM](https://www.youtube.com/watch?v=zq7vLtLHdSM) | English | Published | `PLEIl0EhlcPZg` | 0 | **Static; safe for move legality** |
| 14 | `curriculum-en-010-the-general-en` | [QEdAG1azW2U](https://www.youtube.com/watch?v=QEdAG1azW2U) | English | Published | `PLQRZVvYZCWYc` | 3 | **Invalid move-bearing; incident record** |

### Counts

| Category | Count | Share of published records |
|---|---:|---:|
| Static, no stored moves | 6 | 42.9% |
| Move-bearing and validator-passing | 0 | 0.0% |
| Move-bearing and validator-failing | 8 | 57.1% |
| Total publication records | 14 | 100.0% |

## Validator findings

The validator replays each move from the stored FEN, checks the actual piece on the source point, validates side-to-move order, enforces piece geometry and blockers, rejects friendly-piece collisions, checks cannon screens, enforces palace and river restrictions, and rejects flying-general positions. The validator returns a failure at the first illegal ply; therefore `plies_checked` indicates how far the stored sequence was trusted, not how many moves were legal in the video.

### Generic legacy sequence: six affected records

The following six records share this stored sequence:

```text
Ply 1: [0, 6] -> [0, 5], declared pawn, red
Ply 2: [0, 3] -> [0, 4], declared pawn, black
Ply 3: [1, 7] -> [1, 4], declared pawn, red
```

The first two moves are red and black pawn advances. At ply 3, `[1, 7]` contains a **red cannon**, not a pawn. The validator therefore rejects the payload with `declared piece pawn does not match actual cannon`. The underlying cannon route can be legal in the starting position, but the persisted educational payload is not trustworthy because its piece identity, narration metadata, and deterministic board interpretation disagree.

Affected records are the two English/Chinese news pairs for Lei Tingjie and Xu Xiangyu/Yan Tianqi, plus `evergreen-33-7-2026-08-13-en` and `evergreen-33-0-2026-08-13-en`. Both language variants of a lesson must be remediated together; translating an invalid English move sequence does not make the Chinese artifact valid.

### Evergreen-33-1: blocked rook sequence

The stored sequence is:

```text
Ply 1: [0, 9] -> [0, 5], declared pawn, red
Ply 2: [0, 0] -> [0, 4], declared pawn, black
Ply 3: [2, 6] -> [2, 5], declared pawn, red
```

The first source point contains a red rook, not a pawn. In addition, a red pawn at `[0, 6]` blocks the rook's path toward `[0, 5]`. The sequence is invalid both as a declared-piece payload and as a rook move from the standard starting position. This record must be regenerated from a lawful move template rather than repaired by changing only its label.

### en-010 incident: flying-general and friendly collision

The stored sequence for [QEdAG1azW2U](https://www.youtube.com/watch?v=QEdAG1azW2U) is:

```text
Ply 1: red king     [4, 9] -> [4, 8]
Ply 2: black king   [4, 0] -> [4, 1]
Ply 3: red advisor  [3, 9] -> [4, 8]
```

The first two plies create the prohibited flying-general alignment: the two generals face one another on the open central file. The third ply then attempts to move the red advisor onto `[4, 8]`, a point occupied by the red general. The validator reports `destination is occupied by a friendly piece` at ply 3. The corrected curriculum template now avoids both failures by using this legal three-ply demonstration:

```text
Ply 1: red advisor [3, 9] -> [4, 8]
Ply 2: black pawn   [2, 3] -> [2, 4]
Ply 3: red king    [4, 9] -> [3, 9]
```

This corrected sequence is covered by the curriculum regression test and passes the full 48-test suite.

## Remediation status and source-code protections

The following protections are now present in the repository:

| Protection | Location | Purpose |
|---|---|---|
| Deterministic move replay | [`python/xiangqi_rules.py`](../python/xiangqi_rules.py) | Validates FEN, piece identity, side order, geometry, blockers, palace, river, cannon screens, checks, and flying-general rule. |
| Pre-render legal gate | [`python/director.py`](../python/director.py) | Rejects an invalid job before narration/TTS/render output is accepted. |
| Stored-job early-return gate | [`python/run_pipeline.py`](../python/run_pipeline.py) | Prevents an already-published invalid payload from being silently treated as complete. |
| Autonomous retry gate | [`python/automation_runner.py`](../python/automation_runner.py) | Marks permanent invalid-content failures as blocked rather than retrying the same bad payload. |
| YouTube reconcile gate | [`python/reconcile_youtube.py`](../python/reconcile_youtube.py) | Blocks invalid stored publications before playlist reconciliation or localization retry. |
| Localization legacy-path fix | [`python/youtube_publisher.py`](../python/youtube_publisher.py) | Uses the job output directory when a reconcile call has no local MP4 path, preventing the prior `Path(None)` failure. |
| Curriculum regression coverage | [`python/test_curriculum.py`](../python/test_curriculum.py), [`python/test_xiangqi_rules.py`](../python/test_xiangqi_rules.py) | Covers the corrected en-010 line and all built-in fallback variants. |

The repository test result after the repair is **48 tests passed**. The corrected `palace-defense` template also passes a direct replay against the standard starting FEN with three plies checked and zero errors.

## Required YouTube action

The eight affected videos are already public, so local quarantine alone is insufficient. There are two appropriate choices:

| Choice | Effect | Reversibility | Recommendation |
|---|---|---|---|
| Make affected videos private | Removes them from public viewing while preserving the uploaded artifact and its URL for audit or later replacement. | Reversible | **Recommended default** for evidence preservation and controlled replacement. |
| Delete affected videos | Permanently removes the uploaded artifact and its public URL. | Not reversible | Use only if the channel owner explicitly prefers permanent removal. |

No YouTube privacy or deletion action should be taken without the channel owner's explicit choice. The recommended batch is to make all eight invalid records private, then regenerate corrected English lessons and their Chinese localization artifacts. If deletion is chosen instead, delete the eight English/Chinese/news/evergreen records as a controlled batch and retain this audit plus the SQLite snapshot for evidence.

The six static curriculum lessons should remain public. They contain no stored moves and are not implicated by this move-legality audit.

## Regeneration order

Regeneration should proceed in this order:

1. Quarantine the eight invalid publication records in local state and make the corresponding YouTube videos private, or delete them if that is the explicit decision.
2. Reset the affected candidate rows to `discovered` and the affected curriculum episode rows to `retry` only after their source payloads are ready to regenerate.
3. Regenerate the corrected en-010 lesson first using the new `palace-defense` sequence.
4. Regenerate the six generic-variant records and `evergreen-33-1` from the corrected variant path. Do not copy their old job payloads, captions, or narration.
5. Run the non-publishing quality gate. It must pass legality tests, thumbnail checks, localization contract tests, and fail-closed publishing checks.
6. Run one production job at a time. Confirm that the new stored job passes the validator before publication, that the English video is public, and that Chinese audio/captions/localized metadata and the English/Chinese thumbnail assets complete without `Path(None)` or another reconcile-path error.
7. After each replacement is public, re-run the stored-job audit and update this document with the replacement video ID and the old video's final YouTube status.

## References

[1]: ../python/xiangqi_rules.py "Deterministic Xiangqi legal-move validator"
[2]: ../python/director.py "Director normalization and pre-render legal gate"
[3]: ../python/reconcile_youtube.py "YouTube reconcile legal gate"
[4]: ../python/automation_runner.py "Autonomous runner permanent-content handling"
[5]: ../python/test_xiangqi_rules.py "Xiangqi validator unit tests"
[6]: ../python/test_curriculum.py "Curriculum legality regression test"
[7]: ./video_QEdAG1azW2U_audit.md "Original en-010 incident audit"
[8]: ./production_31759446451_findings.md "Production run findings and localization failure record"
[9]: https://developers.google.com/youtube/v3/docs/videos/update "YouTube Data API videos.update reference"
