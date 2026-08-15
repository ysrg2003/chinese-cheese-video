# Pre-Publication Creative Critic Contract

## Purpose

The Xiangqi production system now contains a bounded pre-publication creative review layer. Its purpose is to catch a video that is technically renderable but pedagogically weak, visually generic, or semantically disconnected from its narration before any thumbnail upload, YouTube upload, playlist mutation, or localization side effect.

The critic is not allowed to repair a published video. It runs only inside `run_pipeline.py` before `publish_video()` and before every other YouTube side effect.

## Review phases

### 1. Storyboard preflight

The first review reads the final director job, narration, narration segments, move phases, visual storyboard, semantic tags, visual plans, allowed primitives, generated-asset declarations, FEN, and move list. It checks whether the planned video makes the spoken idea visible, whether every move has action/reply/effect/constraint teaching phases, and whether the legal move contract remains intact.

If the critic requests a repair, it may change only a scene's headline, visual instruction, visual kind, semantic tags, or renderer-supported visual plan. It may not change narration, caption text, FEN, move coordinates, move phase, piece type, side, generated asset identity, or any legal-game data. The repaired scene is copied back into the actual `narrationSegments` consumed by Remotion, so a repair cannot remain metadata-only.

### 2. Rendered-artifact review

After Remotion renders the MP4, the existing `visual_qa.py` extracts evidence from every narration window. The critic then evaluates the final job together with the visual QA result, scene fingerprints, asset side-strip witnesses, visual primitives, and QA errors. Approval requires both `visualQA.ok == true` and a critic score of at least 82.

A failed visual QA result cannot be overridden by an AI approval. It either receives a safe scene repair followed by a complete re-render, or the pipeline stops before thumbnail generation and publication.

## Decision contract

The AI critic returns `approve`, `repair`, or `reject` plus a score, check-level explanations, and scene-specific repairs. The deterministic contract always runs first. If it finds an illegal move, Arabic content, unsupported primitives, missing beat phases, action-beat dominance, missing visual plans, or missing final render evidence, an AI response cannot override the defect.

The GitHub Actions environment sets `PREPUBLISH_CRITIC_REQUIRED=1`. If the AI router is unavailable, the pipeline fails closed instead of silently accepting a deterministic-only review. The repair budget is bounded by `PREPUBLISH_CRITIC_MAX_ITERATIONS=2`; after the budget is exhausted, no upload occurs.

## What the critic prevents

The contract prevents narration-only scenes, generic decorative motion, repeated static frames with different labels, duplicated move-path treatment across all beats, unsupported board primitives, generated assets attached to move scenes, illegal moves, altered board geometry, Arabic leakage, and publication of a rendered artifact that did not pass final visual evidence.

The critic does not invent moves or alter Xiangqi geometry. The canonical Remotion board remains authoritative. External visual assets remain optional localized reference edits and can never replace the deterministic board, pieces, river, palace, coordinates, or move overlays.

## Publication boundary

The pipeline order is:

1. Generate director data and legal moves.
2. Generate the semantic storyboard and optional localized reference edits.
3. Generate audio and align narration windows.
4. Run storyboard preflight critic.
5. Render the MP4.
6. Run rendered visual QA.
7. Run final artifact critic.
8. Repair and re-render only within the bounded budget when required.
9. Generate and validate the English thumbnail.
10. Run the existing localization and thumbnail pre-publish gates.
11. Call `publish_video()` only after every gate is complete.

No post-publication correction is part of this critic. Post-upload operations may only reconcile an already-public video identity; they cannot replace the final artifact or create a duplicate upload.

## Operational limits

The layer is intentionally bounded. It uses the existing ordered AI provider router, writes `creative-review.json` into the job artifact, and records the iteration history. A review failure is observable and actionable rather than an invisible fallback. This preserves autonomous operation while avoiding unbounded regeneration, API-key exhaustion, or repeated publication attempts.
