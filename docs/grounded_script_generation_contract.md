# Grounded Script Generation and Xiangqi Claim Contract

## Purpose

The production system must not ask an AI model to improvise a Xiangqi lesson from an empty prompt. Before the director writes English narration or Chinese localization, the pipeline builds a research bundle and a deterministic board-state trace. The final video can be published only when both evidence layers agree.

## Required order

1. Load the curriculum or discovered lesson.
2. Retrieve the World Xiangqi Federation rules reference, the specialist Xiangqi pieces-and-moves reference, and a secondary explanatory reference. Add candidate-specific URLs when a lesson has a source URL or research URL list.
3. Optionally and, in production, by default, call Gemini Grounding with Google Search and URL Context. The response is retained as grounding metadata with query/citation evidence.
4. Save the retrieved source metadata, excerpts, timestamps, and source hash in `researchBundle`.
5. Refuse script generation if required topics have no evidence, fewer than two sources are readable, Google grounding is required but unavailable, or the source bundle cannot be hashed.
6. Ask the AI director to generate structured claims alongside purpose, opponentReply, and effect. Causal language such as “blocks,” “opens,” “cannot,” “screen,” “Horse Leg,” or “Elephant Eye” may not appear without a corresponding claim.
7. Validate every move with the legal Xiangqi validator and replay the position after every ply.
8. Validate every structured claim against the replayed position. A move can be legal while its explanation is false; legal-move validation alone is not sufficient.
9. Build the semantic storyboard from the verified claims. Horse Leg claims must create the `horse_leg` primitive; Elephant Eye claims must create `elephant_eye`; Cannon Screen claims must create `cannon_screen`; river-limit claims must create `river_limit`.
10. Run the creative critic before rendering, render the MP4, run frame-level visual QA, then run the final artifact critic. Repairs are limited to scene presentation fields and are re-rendered before any thumbnail or upload operation.

## Mechanical claim types

| Claim type | Required proof |
|---|---|
| `legal_move` | The move is accepted by the Xiangqi validator and does not leave the moving general in check. |
| `horse_leg_block` / `horse_leg_open` | The subject Horse, target destination, and intervening orthogonal Horse Leg are calculated from the exact board state. |
| `elephant_eye_block` / `elephant_eye_open` | The subject Elephant, target destination, and intervening diagonal Elephant Eye are calculated from the exact board state, including river restriction. |
| `cannon_screen` | The source and target share a rank/file and exactly one intervening piece is present for a capture. |
| `river_limit` | The verifier identifies a candidate Elephant crossing or other river-restricted destination as mechanically unavailable. |
| `flying_general` | A facing-general position is never accepted as a positive teaching example; the validator rejects it. |
| `legal_destinations` | The complete destination set is calculated from the position and compared with the director’s list. |

## Source grounding rules

The research bundle is evidence, not permission to copy prose. Source URLs, retrieval timestamps, short excerpts, and hashes are stored for audit. The deterministic board-state verifier has priority over an ambiguous source sentence for a specific position. If a source uses imprecise beginner language, the system must use the canonical term and the mechanically verified relation.

The primary terminology correction is mandatory: use **Horse Leg** for the intervening orthogonal blocker of a Horse; use **Elephant Eye** for the intervening diagonal blocker of an Elephant. `Horse Eye`, `Blocked Eye`, and `Horse’s Eye` are rejected as primary English teaching labels.

## Production environment

GitHub Actions sets:

```text
XIANGQI_RESEARCH_REQUIRED=1
GOOGLE_GROUNDING_ENABLED=1
GOOGLE_GROUNDING_REQUIRED=1
PREPUBLISH_CRITIC_REQUIRED=1
```

The model used for native Google Search grounding is configured by `GOOGLE_GROUNDING_MODEL` and defaults to `gemini-2.5-flash`. The Google grounding API key is read from the dedicated secret when present, then from the configured Gemini key bundle. Unit tests explicitly disable live grounding and use deterministic fixtures; this isolation is intentional and does not weaken production.

## Fail-closed behavior

If grounding fails, the director is unavailable, a required claim is false, a claim lacks coordinates, the semantic primitive is missing, visual QA fails, or the final critic does not approve, the pipeline stops before thumbnail creation and before `upload_video()`. A deterministic fallback is available only for isolated non-publishing tests; production refuses to publish an ungrounded fallback.

## Audit artifacts

Each production job should retain:

- `researchBundle` and `sourceHash`;
- `claimsByPly`;
- `claimProof` and its contract version;
- `creative-review.json` for storyboard and final artifact stages;
- `visual-qa.json`;
- the final pre-publish gate report.

These artifacts let an operator identify whether a future error came from source retrieval, script generation, board-state proof, semantic storyboard selection, rendering, or publication state handling.

## References

- World Xiangqi Federation: https://www.wxf-xiangqi.org/index.php?option=com_content&view=article&id=269&Itemid=291&lang=en
- World Xiangqi Rules PDF: https://www.wxf-xiangqi.org/images/wxf-rules/2018_World_XiangQi_Rules_English2018.pdf
- Xiangqi.com pieces and moves: https://www.xiangqi.com/help/pieces-and-moves
- Chess.com Xiangqi guide: https://www.chess.com/blog/SamCopeland/how-to-play-chinese-chess
- Google Gemini Grounding with Google Search: https://ai.google.dev/gemini-api/docs/google-search

