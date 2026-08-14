# Continuous Publication Completion Contract

## Purpose

The autonomous production workflow must complete the current public publication before it advances the curriculum. A post-upload failure such as a YouTube thumbnail rate limit is not a reason to render or upload the video again. The public `video_id` is the durable identity, and reconciliation is the only permitted operation after `videos.insert` has succeeded.

## Completion policy

| Situation | Allowed action | Forbidden action | Workflow outcome |
|---|---|---|---|
| No resumable public publication exists | Discover the next eligible lesson and run the normal pre-publish gates | Bypass legal, localization, thumbnail, or visual QA gates | Produce one new public video |
| A public publication is `uploaded_playlist_pending`, `published_localization_pending`, or `published_thumbnail_pending` | Retry only the missing post-upload operation with the existing `video_id` | Render the job again or call `videos.insert` again | Keep retrying with exponential backoff |
| A retryable YouTube rate-limit or transient error remains | Keep the same GitHub Actions run alive for the configured retry window, then let the next continuation/scheduled run resume the same state | Fire rapid unbounded requests against YouTube | Preserve pending state and retry later |
| Reconciliation returns `published` | Mark the matching curriculum episode published using `curriculum_lesson_key`, then continue to the next eligible lesson | Spend a full production cycle merely re-marking the already-public lesson | The next lesson can start in the same workflow |
| A permanent authentication or configuration error occurs | Preserve public identity and expose the error in artifacts | Re-upload, overwrite state, or silently continue | Stop new production and require configuration repair |

## Retry parameters

Each reconciliation run is deliberately short and observable. It performs an immediate attempt, then retries after 30 seconds, 60 seconds, and at most 120 seconds. If YouTube still returns a retryable rate-limit, the run finishes its bounded retry window and queues a fresh continuation after three minutes. The number of attempts and the total window are configurable through environment variables so the workflow can be tuned without changing publication logic.

The loop is idempotent. It inspects the SQLite publication state before and after every attempt, exits immediately when no resumable publication remains, and never invokes the renderer. If the short window ends while a public publication is still pending, the database state remains resumable and the continuation repeats the same post-upload work without creating a duplicate.

## Curriculum handoff

When reconciliation completes a publication, it updates the associated curriculum episode through the persisted `curriculum_lesson_key`. This prevents an extra run from selecting the already-public lesson merely to transition its curriculum status. The next normal production pass can therefore select the next lesson, such as en-014, directly.

## Safety invariant

> A public YouTube video is never recreated because a post-upload operation failed.

This contract is enforced at three boundaries: the YouTube publisher reuses the existing identity, the runner refuses to render public pending jobs, and the workflow actively reconciles before allowing new curriculum production.

## GitHub Actions continuation

The production workflow keeps each reconciliation window short. If a retryable YouTube rate-limit remains after that window, it waits three minutes and dispatches the same workflow again with the original production inputs and an incremented continuation depth. This creates visible, bounded runs instead of a single long idle run. The depth cap prevents an accidental infinite loop; the scheduled runs remain the final safety net. GitHub documents that `workflow_dispatch` can be triggered from a workflow using `GITHUB_TOKEN`, which is the mechanism used here [1] [2].

The continuation carries `daily_count`, `languages`, `discovery_limit`, and `reconcile_only` forward. It never changes the content identity, never clears a pending publication, and never turns a post-upload retry into a new upload.

The first deployment of this loop exposed and fixed a CLI wiring defect: the workflow passed `--output`, while the Python entry point expected `output_path`. The corrected parser now maps the CLI flag explicitly, and a regression test covers this exact failure mode. Production is gated on the successful completion of the reconciliation step, so it cannot proceed after a broken or incomplete reconciliation invocation.

## References

[1]: https://docs.github.com/actions/using-workflows/triggering-a-workflow "GitHub Docs: Triggering a workflow"
[2]: https://github.blog/changelog/2022-09-08-github-actions-use-github_token-with-workflow_dispatch-and-repository_dispatch/ "GitHub Changelog: Use GITHUB_TOKEN with workflow_dispatch and repository_dispatch"
