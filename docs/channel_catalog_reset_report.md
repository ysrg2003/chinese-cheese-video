# Channel Catalog Reset Report

**Date:** 2026-08-14  
**Reset group:** `user_deleted_channel_catalog_2026-08-14`  
**YouTube verification run:** [31767933148](https://github.com/ysrg2003/chinese-cheese-video/actions/runs/31767933148)

## Verified deletion

The user confirmed deletion of all current channel videos. A read-only OAuth verification workflow queried the owned channel `UCM7pTdgZRwDZ2gZDtC6SITg` and confirmed that all seven previously active IDs were absent:

| Deleted video ID | Former local job |
| --- | --- |
| `oolASOuPoQc` | `curriculum-en-001-what-is-xiangqi-en` |
| `mQERRtjjgjk` | `curriculum-en-003-a-short-history-of-xiangqi-en` |
| `7DEqaNIh3HE` | `curriculum-en-005-the-9x10-point-board-en` |
| `Tg_DcCPxXuo` | `curriculum-en-006-the-river-and-palaces-en` |
| `a8xHxTuBDAM` | `curriculum-en-007-set-up-all-32-pieces-en` |
| `zq7vLtLHdSM` | `curriculum-en-008-xiangqi-coordinates-en` |
| `8KUaj4IiH_8` | `curriculum-en-010-the-general-en` |

> The verification response contained `present_videos: {}` and `verified_absent: true`. It was read-only and did not mutate YouTube.

## SQLite reset performed

The idempotent `reset_deleted_channel_catalog.py` migration created the `publication_reset_history` table and stored one full snapshot per deleted job, tied to the verification run. It then removed all active publication state for the seven jobs.

| Table | Post-reset state |
| --- | --- |
| `youtube_publications` | `status=not_started`; active video, URL, and playlist IDs cleared |
| `youtube_videos` | `status=reset_for_regeneration`; video IDs, URLs, paths, and publication timestamps cleared |
| `youtube_video_playlists` | all seven job links removed |
| `video_jobs` | `status=reset_for_regeneration`; output URL and payload cleared |
| `content_candidates` | `status=discovered`; `published_job_id` cleared |
| `curriculum_episode_plans` | `status=planned`; candidate/job/published timestamp cleared |
| `publication_reset_history` | seven immutable historical snapshots retained, including the old video IDs and verification run |

This makes the deleted videos behave as unpublished for candidate selection and publication logic, while preserving an auditable history instead of silently losing the original records. Existing earlier `deleted_invalid_content` remediation evidence remains separate.

## Operational state

Production remains frozen by default in `.github/workflows/render-video.yml`. While frozen, scheduled runs do not reconcile, discover, render, or publish. The freeze may be removed only after the non-publishing visual acceptance sample verifies the corrected board, the clean-board thumbnail, and the durable asset manifest specified in `docs/xiangqi_visual_spec.md`.
