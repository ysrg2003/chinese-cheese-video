# Cross-Layer Production Contracts

The production system is governed by one invariant: **a later layer may not reinterpret, replace, or silently skip the output of an earlier layer**. Every production job keeps the same stable `job_id`, language, curriculum lesson key, FEN, move trace, narration segments, visual storyboard, audio artifact, and YouTube publication identity from selection through reconciliation.

## Curriculum gate

`LocalStore.curriculum_gate(language)` is authoritative. The first active lesson whose status is not `published` controls the run. If that lesson is `planned` or `retry`, it is the only lesson eligible for production. If it is `queued`, `processing`, `failed`, or `blocked`, production stops with a partial/deferred result. Supplementary discovery is allowed only when every active curriculum lesson is published.

`claim_curriculum_lesson()` is a single-writer guard. It atomically claims only the first runnable lesson and rejects a second claim or a later lesson whose predecessors are not published. This prevents a scheduled run, manual run, retry, or reconciliation process from selecting different content at the same time.

## Pipeline contract

`integration_contracts.py` validates the shared job at the `director`, `storyboard`, `tts`, and `render` boundaries. It checks the supported language, English-language restrictions, required identity fields, exact puzzle identity, legal Xiangqi move trace, verified `claimProof`, narration segment presence, audio presence after TTS, and one `visualStoryboard` scene per narration segment.

The storyboard field is intentionally named `visualStoryboard`, matching the actual consumer schema used by the visual QA and creative critic layers. A payload with a different field name is rejected rather than silently rendered without its intended visuals.

## Publication contract

Before a YouTube result is written to the catalog, the publication contract validates the status, stable `job_id`, language, curriculum lesson key, playlist key, video ID, and video URL. A `published` result without a video ID is rejected. Resumable states remain resumable and are handled by reconciliation; they do not trigger a second render or upload.

## Failure behavior

An externally deleted public video is reconciled to `deleted_external`, its curriculum episode is returned to `retry`, and the same stable job identity is regenerated. A pending publication is deferred to reconciliation. A permanent Xiangqi or contract failure is blocked and cannot be hidden by an evergreen fallback. A transient production attempt has a bounded subprocess timeout (`PIPELINE_ATTEMPT_TIMEOUT_SECONDS`, default 20 minutes, maximum 60 minutes), so a stuck AI, TTS, or renderer process cannot hold GitHub Actions indefinitely.

## CI guarantee

The autonomous workflow checks for the contract module and its call sites, then executes the full Python test suite, TypeScript compilation, Python compilation, and diff validation before reconciliation or production. The regression suite includes curriculum bypass prevention, deleted-video requeue behavior, single-writer claims, publication identity checks, legal Elephant Eye claims, and self-repair job identity reuse.
