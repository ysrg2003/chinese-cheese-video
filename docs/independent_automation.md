# Independent Automation Architecture

## Purpose

Chinese Cheese Video operates without an open Manus session. A scheduled GitHub Actions runner discovers or selects work, validates the curriculum and Xiangqi rules, generates a grounded script and visual storyboard, produces male narration, renders a format-correct MP4, performs quality gates, publishes to YouTube when enabled, reconciles public state, uploads artifacts, and commits SQLite state for the next run.

## Why GitHub Actions plus SQLite is the production design

| Design | Strengths | Trade-offs |
| --- | --- | --- |
| GitHub Actions plus committed SQLite | Scheduled execution, durable state, workflow logs, artifacts, and no continuously running server | Runner time limits, provider quotas, and Git commits are part of the persistence path |
| Persistent server plus queue | Fine-grained scheduling and live monitoring | Requires a continuously maintained host, queue, database, and secret manager |
| Local-only execution | Fastest setup for development | Does not provide unattended execution or shared durable state |

The implemented design is GitHub Actions plus SQLite. The workflow serializes production with one concurrency group and does not cancel an active run. After production, it commits `data/chinese_cheese_video.db` and `data/ai_router.db` when they change. The next runner therefore sees curriculum publication state, deduplication fingerprints, provider cooldowns, and resumable YouTube publication records.

## End-to-end stages

1. **Checkout.** The workflow checks out this repository and the reusable `ysrg2003/ai-provider-router` repository.
2. **Runtime setup.** It installs Node.js 22, Python 3.11, `ffmpeg`, JavaScript dependencies, Python dependencies, and the Remotion browser.
3. **Router validation.** It validates ordered provider configuration and key-pool shape without printing secrets.
4. **Curriculum preflight.** It runs the curriculum contract across all 72 lessons before selecting new production work.
5. **Autonomous preflight.** It runs TypeScript, Python, rule, claim, visual, localization, thumbnail, and TTS contract checks with deterministic test variables.
6. **Public reconciliation.** It checks existing YouTube records and repairs resumable publication steps before selecting new work.
7. **Selection.** It chooses the next unpublished curriculum lesson in `sequence_no` order, or a deduplicated discovery candidate after the fixed curriculum path is exhausted.
8. **Research and direction.** It grounds the subject, generates narration and move data, validates claims, builds the storyboard, and assigns sentence-level visual supervision.
9. **Self-repair and review.** Recoverable defects may receive bounded, validated repairs. The creative critic must approve the job before publication.
10. **Narration.** The AI Router generates bounded Gemini-TTS batches using male `Schedar` for English and Chinese. Edge TTS is only the final recorded fallback.
11. **Render and QA.** Remotion renders the job using the explicit format contract and the visual QA stage samples frames and checks the resulting MP4.
12. **Publication.** YouTube upload, localization, playlist placement, and thumbnail handling follow the resumable publisher contract.
13. **Persistence.** The workflow exports a normalized YouTube catalog, uploads artifacts, and commits SQLite state.

## Provider order and failure policy

The reusable AI Router owns provider order, key rotation, backoff, and cooldown. The application’s intended chain is:

1. `gemini-2.5-flash` across the configured Gemini key pool.
2. `gemini-2.5-flash-lite` across the configured Gemini key pool.
3. The configured Hugging Face Inference Provider models.
4. A deterministic local fallback only where the job contract permits it.
5. Edge TTS as a final narration fallback when explicitly enabled.

The system records calls and state in `data/ai_router.db`, but never stores raw keys there. A transient provider failure should cause the Router to try its next valid route. A fixed curriculum contract failure should remain a hard failure until the rule, data, or template is corrected. The system must not hide a legal-move error behind a generic fallback.

## Selection and deduplication

`python/automation_runner.py` calls the discovery layer, stores candidates in `content_candidates`, and selects only unpublished or retryable records. Candidate fingerprints are derived from the content type, language, FEN, moves, pairing, and title. A published candidate is not selected again. A failed render can return to a retryable state, while a successful YouTube ID remains authoritative for reconciliation.

Discovery combines RSS signals, optional YouTube Data API search, evergreen ideas, ordered skill-pairings across `beginner`, `intermediate`, `advanced`, `expert`, `professional`, and `legendary`, and AI-generated ideas when configured. Public material is used as a topic signal; the project does not re-upload third-party footage.

## Curriculum behavior

The versioned curriculum is in `config/xiangqi_curriculum_en.json`. The database stores the same lesson identity and its episode plan. The authoritative next item is the active lesson with the lowest unpublished `sequence_no`; historical lesson labels such as `en-002` do not necessarily equal sequence 2.

Every fixed curriculum item is preflighted before production. `lesson` and `game` items are standard landscape videos at `1920×1080`; explicit `short` items are portrait at `1080×1920`. The publisher also checks the actual rendered MP4 dimensions so curriculum metadata cannot silently misclassify a historical upload.

## Runtime schedule

The workflow runs at `15 8 * * *`, `15 14 * * *`, and `15 20 * * *` UTC. Manual dispatch supports normal production, reconciliation-only mode, review-only mode, a Schedar TTS smoke test, and a male-voice comparison run. A bounded continuation may self-dispatch when public reconciliation needs another window; it is capped by `continuation_depth`.

## Evidence and observability

Every run should leave these evidence classes:

| Evidence | File or location |
| --- | --- |
| Workflow status | GitHub Actions run summary and logs |
| Production result | `automation-run.json` or `automation-run-*.json` |
| Public reconciliation | `continuous-reconcile.json` and `.log` |
| Job contract | `output/jobs/<job-id>/job.json` |
| Director and claims | `output/jobs/<job-id>/director-data.json` |
| Audio provider | `output/jobs/<job-id>/localization/zh/voice_provider.json` |
| Visual QA | `output/jobs/<job-id>/visual_qa/visual-qa.json` and sampled frames |
| YouTube catalog | `youtube-catalog.json` |
| Durable state | `data/chinese_cheese_video.db` and `data/ai_router.db` |

## Operational limits

This design is autonomous but not unlimited. GitHub runner time, YouTube quota, Gemini quota, Hugging Face quota, external visual-provider availability, and artifact retention remain provider-owned limits. The system responds to transient states and retries within explicit caps; it does not guarantee that every scheduled tick produces a public upload.

## References

[1]: https://github.com/ysrg2003/ai-provider-router "Reusable AI Provider Router"
[2]: https://docs.github.com/actions/writing-workflows/choosing-what-your-workflow-does/control-the-concurrency-of-workflows-and-jobs "GitHub Actions concurrency"
[3]: https://docs.github.com/actions/using-workflows/storing-workflow-data-as-artifacts "GitHub Actions artifacts"
[4]: https://ai.google.dev/gemini-api/docs/rate-limits "Gemini API rate limits"
[5]: https://huggingface.co/docs/inference-providers/en/index "Hugging Face Inference Providers"
