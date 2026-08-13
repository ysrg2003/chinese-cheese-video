# English Content Diversity Completion Report

## What caused the repetition

The original pipeline prevented duplicate candidate fingerprints, but its fingerprint was tied primarily to the candidate record. It did not compare the semantic topic, the spoken script, or the board sequence against already published videos. RSS candidates were also created with the same demonstration FEN and the same three moves, while the director fallback used one generic narration for every content type. As a result, different source headlines could produce videos that looked and sounded like the same lesson.

The live catalog contained four initial language variants across two RSS topics, all classified as `trend_breakdown`: the Lei Tingjie/AI topic and the Xu Xiangyu/Yan Tianqi topic, each published in English and Chinese. The English videos were therefore not four independent planned English episodes; they were two English trend episodes plus two Chinese-language variants of the same two source ideas. The problem was real, and the previous duplicate guard was insufficient.

## Fixes now deployed

The English selector now uses four independent protections:

| Protection | Behavior |
| --- | --- |
| Topic fingerprint | Normalizes the story title, strips common publisher suffixes, and stores `topic_key`; the same story from another RSS or YouTube source is rejected. |
| Content rotation | Selects from the channel program in a deliberate order instead of always choosing the highest-priority RSS item. Recent content types are penalized, and consecutive trend episodes are avoided when other categories exist. |
| Board-sequence signature | Compares FEN plus moves with sequences already stored in `video_jobs`; the same board sequence is not selected again. Legacy candidates carrying the old demo sequence receive a deterministic topic-based variant before selection. |
| Type-specific creative fallback | If the AI director is unavailable or returns a generic fallback, each content type receives its own narration, moves, and editorial purpose. Definitions, rules, openings, tactics, endgames, full games, puzzles, comparisons, skill matches, viewer challenges, and trends no longer share one narration. |

The fallback system now supplies distinct English narration templates for all eleven content types. RSS topics receive topic-specific narration, while evergreen, pairing, puzzle, comparison, opening, endgame, and challenge candidates receive their own educational structure. The same stable topic hash selects one of five board-move variants, so the board animation also changes instead of repeating the demonstration sequence.

GitHub Actions now defaults to English only for both scheduled runs and manual dispatch. Chinese remains supported as an explicit input, but it is no longer generated automatically while the English channel program is being validated.

## Partial-upload recovery

The diversity validation initially selected the planned definition episode correctly, but YouTube returned a transient `playlistNotFound` while associating its already-uploaded public video. The video ID `6uZ1lxn-oUs` was preserved. The publisher was hardened to recognize numeric or string HTTP 404 statuses, clear a stale playlist ID before recovery, create or resolve a fresh playlist, and retry association. A new reconciliation step now runs before every production cycle and reuses pending public video IDs without uploading them again.

The following run confirmed that reconciliation worked:

| Item | Result |
| --- | --- |
| Existing public video | `6uZ1lxn-oUs` was reused; no duplicate upload was created. |
| Reconcile result | `selected=1`, `published=1`, `failed=0`. |
| Reconciled playlist | `en-start-here`, playlist ID `PLNHV-O5_CF9M`. |
| New production result | A different `opening` episode was rendered and published. |

## Live validation

Workflow `31657457440` completed successfully from the deployed repository. It ran English only, completed reconciliation, rendered one new episode, exported the normalized catalog, uploaded the artifact, and committed the SQLite state.

| Language | Content type | Public video | Playlist | Observed duration |
| --- | --- | --- | --- | --- |
| English | Definition, reconciled existing upload | [6uZ1lxn-oUs](https://www.youtube.com/watch?v=6uZ1lxn-oUs) | [EN — Start Here](https://www.youtube.com/playlist?list=PLNHV-O5_CF9M) | 0:18 |
| English | Opening, new episode | [tA3vZMgrfg8](https://www.youtube.com/watch?v=tA3vZMgrfg8) | [EN — Opening Lab](https://www.youtube.com/playlist?list=PLQegM4WVOOdw) | 0:15 |

The new episode has the narration: “A strong Xiangqi opening is a plan, not a memorized move list. Develop with purpose, protect the critical line, and watch how the first exchanges shape the middlegame.” Its artifact record is `content_type=opening`, `status=published`, `playlist_key=en-openings`, and `captions_source=narration_fallback`. The next dry selection preview over the live artifact chose, in order, a tactics episode, a skill-match episode, an advanced puzzle, a full game, and a viewer challenge, each with a distinct topic key and board sequence.

## What happens next automatically

The next scheduled English run will begin by reconciling any prior public upload that lacks a playlist association. It will then discover new candidates, exclude published topic keys, exclude already used FEN/move sequences, avoid recent content types where alternatives exist, select one fresh English episode, render it, publish it publicly, place it in the matching English playlist, and export the catalog and SQLite snapshot.

The old duplicate-looking public videos have not been deleted automatically. Deleting public videos is destructive and was not necessary to fix the production system. They remain in the channel history, while all future English episodes follow the diversity protections above.

## Tests and repository state

The local regression suite passed 12 tests covering topic normalization, duplicate-topic rejection, type-specific fallback, caption behavior, SQLite catalog state, upload idempotency, stale-playlist recovery, and publication retry. Python compilation and workflow validation passed. The latest deployed commit is `d2e7ef7` on `master` in `ysrg2003/chinese-cheese-video`.
