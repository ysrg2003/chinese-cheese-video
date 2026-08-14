# Visual Asset Insertion Contract

## Purpose

The Xiangqi channel must not publish a video merely because a storyboard JSON file exists or because a corrected still frame was produced in a later inspection. Every narrated segment must have a concrete visual treatment that is present in the MP4 that will be uploaded.

## Two valid visual routes

The renderer uses two complementary routes. A **deterministic board treatment** is the default for anything that must remain legally exact: board geometry, files, ranks, intersections, river, palaces, piece-family anchors, legal destinations, source/destination points, move paths, cannon screens, horse legs, and route constraints. These are drawn by Remotion on the canonical 9×10 intersection board. They are not optional decoration and they must be selected by the semantic contract.

A **reference-edit asset** is reserved for scenes where a localized material, color, historical, or cultural treatment adds explanatory value without changing the board state. The pipeline uploads an exact Remotion reference plus a same-size mask, requests an edit only inside the mask, stores the result under the job's durable `public/generated/<job_id>/assets/` directory, attaches its source and role to the scene, and renders it below the deterministic board and overlays.

The corrected `Piece Families And Homes` frame from en-007 belongs to the first route. It is a deterministic Remotion frame with `piece_family_anchor` and `mirror_setup`, not a standalone AI image. Its earlier absence from the public video happened because the frame was created after publication and there was no render-artifact gate to force a replacement before upload.

## Required lifecycle

Every production job follows this sequence:

1. The AI director receives the narration segments and proposes one scene for each spoken segment.
2. The deterministic semantic contract normalizes the proposal. It chooses renderer-supported primitives for known Xiangqi concepts and rejects unsupported primitives.
3. If a reference edit is appropriate, the planner selects only an eligible static scene and the image service returns a durable file with a SHA-256 hash.
4. The scene, its `visualPlan`, its timing window, and any `generatedAsset` are written to `job.json`.
5. Remotion renders the MP4 using that exact job. `GeneratedVisualAsset` is resolved from the durable source path; the board remains canonical.
6. `visual_qa.py` extracts a frame from every narration window in the final MP4. It checks the real duration, frame size, non-blank output, actionable plan, distinct static-scene fingerprints, and reference-asset side-strip visibility.
7. The result is written to `visual_qa/visual-qa.json` and `job.json`. If the result is not `ok: true`, production stops before thumbnail generation and before YouTube upload.
8. `publish_video()` repeats the final boundary check for every new storyboard upload. It refuses to call `upload_video()` unless `job.visualQA.ok` is true. Existing playlist-association retries are not treated as new uploads.

## Acceptance criteria

| Requirement | Blocking evidence |
| --- | --- |
| Each narration segment has a visual beat | One extracted frame record per `sceneId` with `startSec`, `endSec`, `visualKind`, and `primitives` |
| The visual plan is actionable | Non-empty `visualPlan.focus` and renderer-supported `visualPlan.primitives` |
| The MP4 is real and usable | `ffprobe` duration succeeds; each sampled frame is 1080×1920 and non-blank |
| Static scenes are not metadata-only | Adjacent static scenes with different plans cannot have identical frame fingerprints |
| A generated/reference asset is actually used | Durable source exists and its frame side-strip similarity meets the witness threshold |
| YouTube upload is protected | `publish_video()` requires `visualQA.ok == true` for a new storyboard upload |

The quality-gate workflow runs the same CLI against a rendered semantic proof. The production workflow also runs the gate inside `run_pipeline.py`, so scheduled execution does not depend on a Manus review or a manually opened image.

## Publication-state contract

Visual QA and rendering can succeed while a later YouTube mutation fails. The publisher therefore treats post-upload operations as resumable state transitions. If `upload_video()` has returned a video ID and a later playlist, caption, metadata, or thumbnail operation fails, the publisher preserves that video ID and playlist identity in SQLite and returns a resumable status such as `uploaded_playlist_pending`, `published_localization_pending`, or `published_thumbnail_pending`.

A thumbnail rate-limit response from `thumbnails.set` is specifically classified as `published_thumbnail_pending`. The next reconciliation run selects that row and calls `publish_video(None, ..., existing_publication=...)`; `_reusable_existing_video_id()` accepts the status, so YouTube receives only the missing thumbnail request and never receives a second `videos.insert` upload. The catalog may remain pending until all required post-upload policy steps complete, but the public identity is never discarded and cannot be duplicated by a retry.
