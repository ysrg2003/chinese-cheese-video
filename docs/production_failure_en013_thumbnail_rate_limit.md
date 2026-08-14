# Production incident: en-013 thumbnail rate limit

## What actually happened

Production run `31792595701` rendered `curriculum-en-013-the-horse-and-blocked-eye-en` with the new 13-scene beat-level storyboard. The rendered MP4 and `visual_qa/visual-qa.json` were valid: `visualQA.ok` was `true`, and all three moves had `action`, `reply`, `effect`, and `constraint` windows with distinct frame fingerprints.

The failure occurred after the YouTube upload had already returned video ID `dw6V8q69hY8`. The final `thumbnails.set` request returned HTTP 429 with reason `uploadRateLimitExceeded` and message `The user has uploaded too many thumbnails recently`. The old publisher raised this as a failed candidate without carrying the returned video ID into the publication row. That was a publication-state defect, not a render, legality, visual-director, or caption-generation defect.

## Source-controlled fix

`youtube_publisher.py` now classifies the post-upload failure as `published_thumbnail_pending`, returns the public video ID, playlist ID, playlist item, and error, and accepts that status as resumable. `run_pipeline.py` preserves the status and identity in both publication and normalized catalog rows. `reconcile_youtube.py` selects the new status and calls `publish_video(None, ..., existing_publication=...)`; `_reusable_existing_video_id()` therefore prevents a second `videos.insert` call. The next attempt only completes the missing post-upload operation.

The same state model covers `published_localization_pending` for a caption or metadata operation that fails after upload. A missing thumbnail remains pending rather than being falsely marked complete, so the channel policy is still enforced before the catalog becomes `published`.

## One-time data recovery

The catalog row for en-013 was migrated to `published_thumbnail_pending` with video ID `dw6V8q69hY8` and the known Piece Academy playlist ID. This migration repairs state fidelity only; it does not re-render, edit, delete, or re-upload the public video. Future scheduled reconciliation can retry the thumbnail against that existing video.

## Regression coverage

The fake YouTube API test simulates a successful upload followed by a thumbnail 429, asserts the returned pending status and video ID, then retries with the existing publication and asserts that `upload_video()` is never called. SQLite tests assert that the pending status preserves the public video and playlist identity.

## Reconciliation-only orchestration

The first attempt to repair the orphan used `daily_count=0`, but the old runner still selected the next curriculum lesson because its curriculum branch bypassed the daily-count limit. It therefore rendered en-013 again before reusing the existing video ID; it did not create a duplicate, but it wasted a full render and was not the intended repair mode.

The source-controlled orchestration fix adds a `reconcile_only` workflow input and an `is_reconciliation_only()` guard. When enabled, the production step is skipped. A non-positive daily count also stops discovery and curriculum selection. Reconciliation can now repair pending public states without generating a new lesson, rendering an old job, or calling `videos.insert`.

## Public-pending no-rerender guard

A second root-cause guard now runs before the production subprocess. If the stable job identity already has a public YouTube video in `uploaded_playlist_pending`, `published_localization_pending`, or `published_thumbnail_pending`, `automation_runner.py` raises a retryable `PublicationPendingError` and does not create an input file or invoke `run_pipeline.py`. The next workflow run reconciles the existing `video_id` first. This makes the no-duplicate guarantee explicit at the orchestration boundary, not only inside the publisher.
