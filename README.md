# Chinese Cheese Video

**Chinese Cheese Video** is an autonomous Xiangqi video-production system for the **Xiangqi Lab** YouTube channel. It selects the next curriculum item or a discovered evergreen idea, validates Xiangqi rules and grounded claims, creates a sentence-level visual storyboard, generates male narration, renders a Remotion MP4, runs visual and editorial quality gates, publishes to YouTube, verifies publication state, and commits durable SQLite state so the next scheduled run can continue without manual orchestration.

The repository is designed for English-first production with Simplified Chinese as a secondary localization. Production-facing generated content accepts only `en` and `zh`; Arabic text is rejected by the content contracts. The system does not depend on an open Manus session after GitHub Actions has been configured.

> **Current production contract:** `lesson` and `game` items render as standard landscape videos at `1920×1080`. Only curriculum items whose explicit `format` is `short` render as portrait videos at `1080×1920`. The publisher enforces this contract before upload.

## What a successful run produces

A successful production run creates a job directory containing the validated job JSON, narration, word timings, captions, storyboard metadata, visual-QA frames, thumbnails, and the final MP4. When publishing is enabled, the run uploads the video to the configured channel, applies localized metadata, adds the video to the correct playlist, and records the YouTube ID in SQLite. Standard-video thumbnails are uploaded with `thumbnails.set` and then verified by a separate `videos.list` read-back. Shorts are recorded as `manual_studio_required` because the YouTube API cannot be relied upon for the portrait Shorts thumbnail workflow used by this project.

## Architecture at a glance

| Layer | Responsibility | Primary files |
| --- | --- | --- |
| Curriculum and state | Stores the 72-item curriculum, sequence, publication state, retry state, candidates, and YouTube records | `config/xiangqi_curriculum_en.json`, `data/chinese_cheese_video.db`, `python/local_store.py`, `python/curriculum.py` |
| Discovery | Finds RSS and optional YouTube signals, evergreen ideas, skill-pairings, and post-curriculum candidates without duplicating published content | `python/content_discovery.py`, `python/continuous_topic_generator.py`, `python/automation_runner.py` |
| Research and rules | Grounds scripts and validates FEN, legal move sequences, piece movement, palace, river, horse-leg, elephant-eye, cannon-screen, and flying-general constraints | `python/research_grounding.py`, `python/xiangqi_rules.py`, `python/xiangqi_claims.py` |
| Direction and supervision | Produces narration, claims, storyboard scenes, sentence-level visual intent, repairs, and pre-publication creative review | `python/director.py`, `python/visual_director.py`, `python/sentence_visual_supervision.py`, `python/creative_critic.py`, `python/self_repair.py` |
| Narration | Uses AI Router Gemini-TTS with the male `Schedar` voice for English and Chinese; Edge TTS remains a final fallback only | `python/tts.py`, `python/ai_router_bridge.py`, `python/tts_smoke.py` |
| Rendering | Builds the responsive Xiangqi board, move animation, legal paths, target markers, captions, storyboard overlays, and thumbnail assets | `src/index.tsx`, `src/Composition.tsx`, `python/run_pipeline.py` |
| Quality gates | Validates contracts, claims, visual frames, localization, audio, thumbnails, remote dimensions, and publication state | `python/curriculum_preflight.py`, `python/visual_qa.py`, `python/integration_contracts.py`, `python/youtube_publisher.py` |
| Automation | Runs the full process three times daily, serializes runs with concurrency, uploads artifacts, and commits SQLite state | `.github/workflows/render-video.yml`, `python/automation_runner.py` |
| Reusable systems | Provides Xiangqi-aware config-driven orchestration, namespaced durable evidence, complete-match fallback, and derivative lineage without replacing the legacy state owner | `systems/`, `config/automation.json`, `python/continuous_topic_generator.py`, `python/complete_match_generator.py`, `python/short_highlight_generator.py` |

## Requirements

The supported runtime is **Node.js 22**, **Python 3.11**, and a Linux environment with `ffmpeg`. Remotion also needs its browser bundle, installed by `npx remotion browser ensure`. GitHub Actions installs these dependencies automatically on the hosted Ubuntu runner.

For local work, install Node.js 22, Python 3.11, `ffmpeg`, Git, and the GitHub CLI if you need to inspect or dispatch workflows. The project pins Remotion to `4.0.509`; keep the package lockfile and `package.json` synchronized.

## Local installation

Run the following commands from a clean terminal. The first command changes into the repository so that every later relative path is unambiguous.

```bash
git clone https://github.com/ysrg2003/chinese-cheese-video.git
cd chinese-cheese-video
npm ci
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r python/requirements.txt
npx remotion browser ensure
```

Expected result: `npm ci` completes without dependency-resolution errors, the Python requirements install successfully, and Remotion reports that its browser is ready. If `python3 -m venv` is unavailable, install the operating-system package that provides Python virtual environments, then repeat the command.

## Smallest safe first run

The smallest local verification does not call external AI services, publish to YouTube, or modify the production catalog. It checks the sample input and pipeline contracts only.

```bash
. .venv/bin/activate
XIANGQI_RESEARCH_REQUIRED=0 \
GOOGLE_GROUNDING_ENABLED=0 \
GOOGLE_GROUNDING_REQUIRED=0 \
PREPUBLISH_CRITIC_REQUIRED=0 \
VISUAL_ASSET_ENABLED=0 \
YOUTUBE_PUBLISH_ENABLED=0 \
python python/run_pipeline.py \
  --input python/sample_job.json \
  --language en \
  --storage local \
  --dry-run \
  --skip-tts \
  --skip-render
```

Expected result: the command exits with status `0` and prints a validated job summary. If it reports a missing module, confirm that the virtual environment is active and rerun the dependency installation. If it reports a contract error, do not bypass the gate; inspect the named JSON field and run the relevant test described in `docs/troubleshooting.md`.

## Local render modes

To generate a real local English MP4 from the sample job, configure a working TTS provider first, then run:

```bash
python python/run_pipeline.py \
  --input python/sample_job.json \
  --language en \
  --storage local
```

To stop after job data and audio preparation without rendering the MP4, use `--skip-render`. To render without audio for a visual-only layout check, use `--skip-tts` only when the input and pipeline support it. To inspect the Remotion composition interactively, run:

```bash
npm run dev
```

The sample Remotion command is:

```bash
npm run render:sample
```

For autonomous local selection and discovery, use:

```bash
python python/automation_runner.py \
  --daily-count 1 \
  --languages en \
  --discover-limit 20 \
  --dry-run
```

The `--dry-run` flag prevents durable publication-state advancement. A real local production run should be treated as a publishing operation and should use the same secrets, review gates, and backups as GitHub Actions.

To exercise the Xiangqi-aware configured chain without rendering or publishing, use a copy of the SQLite database:

```bash
cp data/chinese_cheese_video.db /tmp/chinese-cheese-chain.db
LOCAL_DB_PATH=/tmp/chinese-cheese-chain.db XIANGQI_OUTPUT_ROOT=/tmp/chinese-cheese-chain-output \
PYTHONPATH=python:. python python/automation_runner.py \
  --automation-config config/automation.json \
  --automation-only \
  --daily-count 1 \
  --languages en \
  --discover-limit 20
```

The configured chain preserves the curriculum queue first. Only after all active curriculum episodes are published does it select a fresh discovered topic; if discovery is exhausted, it generates a validated terminal complete game from `config/xiangqi_complete_match_profiles.json`. Set `XIANGQI_SHORTS_ENABLED=1` only when a real parent job has completed and you want derivative Short descriptors and lineage artifacts.

## Video-format policy

The `format` field is authoritative. The renderer and publisher must agree on the same dimensions before an upload is allowed.

| Curriculum format | Output | YouTube treatment |
| --- | --- | --- |
| `lesson` | `1920×1080` landscape | Standard video; API thumbnail upload and read-back are required |
| `game` | `1920×1080` landscape | Standard video; API thumbnail upload and read-back are required |
| `short` | `1080×1920` portrait | YouTube Short path; thumbnail state is `manual_studio_required` |

Do not infer format from a curriculum label, title, or historical upload. The backfill tool reads actual remote video dimensions when available and supports an explicitly verified `--known-dimensions` fallback for old videos whose `fileDetails` are unavailable.

## AI and narration policy

The production workflow checks out the reusable [AI Provider Router](https://github.com/ysrg2003/ai-provider-router) into `ai-provider-router` and installs it as an editable Python package. The ordered production chain is controlled by that repository and the selected `AI_ROUTER_CHAIN`; the project does not silently replace the configured provider chain with an unrelated direct call.

The production workflow sets `TTS_PROVIDER=ai_router`, `TTS_VOICE_EN=Schedar`, and `TTS_VOICE_ZH=Schedar`. Narration is split into bounded batches using `TTS_BATCH_MAX_CHARS=480` and `TTS_BATCH_MAX_SEGMENTS=3` to preserve intelligibility and reduce long-form voice drift. Edge TTS is available only as the last-resort fallback after the AI Router chain is exhausted or when explicitly enabled for a controlled test; every fallback is recorded.

The script director is required to use grounded research in production. The claim contract rejects unsupported legal-move claims, and the visual supervisor maps every narration sentence to a renderer-safe visual intent. Existing Xiangqi templates are deterministic and rule-aware; new concepts use a safe `concept_focus` treatment instead of inventing a move or pretending that an unverified visual asset proves a claim.

## GitHub Actions production

The authoritative workflow is `.github/workflows/render-video.yml`. It runs at **08:15, 14:15, and 20:15 UTC** each day, and it can also be dispatched manually. The workflow uses the concurrency group `chinese-cheese-video-production` with `cancel-in-progress: false`, so a second run waits instead of interrupting an active render. New uploads default to `private`; integration tests use `automation_only=true` or `review_only=true` and do not publish.

The production path is:

1. Checkout this repository and the private reusable AI Router repository.
2. Install Node.js 22, Python 3.11, `ffmpeg`, JavaScript dependencies, Python dependencies, and the Remotion browser.
3. Validate the AI Router key pools and ordered chain.
4. Validate YouTube publishing configuration when publishing is enabled.
5. Run `python/curriculum_preflight.py` across all 72 curriculum items.
6. Run autonomous contract checks, TypeScript checks, Python unit tests, compilation checks, visual contracts, thumbnail read-back contracts, and TTS contracts.
7. Reconcile public YouTube state before producing anything new, except in explicit `automation_only` selection smoke mode.
8. Select the next unpublished curriculum item through `config/automation.json` when configured; otherwise use the legacy selector.
9. After all active curriculum episodes are published, select a fresh Xiangqi discovery topic; if discovery is exhausted, generate a validated terminal complete game from `config/xiangqi_complete_match_profiles.json`.
10. Run research, script direction, visual supervision, self-repair, narration, rendering, visual QA, and creative review for the selected parent content.
11. When `shorts_enabled=true`, extract derivative Short descriptors and durable parent/source-window lineage after the parent job completes.
12. Upload the video, localizations, playlist placement, and standard-video thumbnail only when the explicit publishing policy allows it.
13. Verify the YouTube record and commit the SQLite catalog, reusable evidence, and AI Router state back to `master`.

A successful production run must show a successful `produce` job, a completed reconciliation report, a successful autonomous run, uploaded artifacts, and a state commit when SQLite changed. Workflow artifacts are retained for 14 days.

## Manual workflow inputs

Open the repository on GitHub, choose **Actions → Chinese Cheese Video — autonomous production**, click **Run workflow**, and use the following inputs:

| Input | Default | Purpose |
| --- | --- | --- |
| `daily_count` | `1` | Number of new candidates to produce in the run |
| `languages` | `en` | Comma-separated production languages; use `en` or `en,zh` |
| `discovery_limit` | `20` | Maximum discovery candidates to inspect |
| `reconcile_only` | `false` | Reconcile existing public state without producing new content |
| `review_only` | `false` | Generate and validate an MP4 without YouTube upload or publication-state advancement |
| `tts_smoke` | `false` | Run a real AI Router Schedar smoke test without producing or publishing |
| `tts_compare` | `false` | Generate the official male Gemini-TTS comparison set plus an explicitly labeled Edge reference |
| `continuation_depth` | `0` | Internal retry counter; leave at `0` for normal manual runs |
| `automation_config` | empty | Optional domain-owned chain; set to `config/automation.json` to use the Xiangqi-aware stages |
| `automation_only` | `false` | Select through the configured chain only; no render, publish, or curriculum advancement |
| `shorts_enabled` | `false` | Generate derivative Short descriptors and lineage after a completed parent job |

For a safe first workflow test, use `review_only=true`. Do not use destructive deletion workflows without a current backup and explicit confirmation.

## Durable state and artifacts

| Path | Meaning | Retention or handling |
| --- | --- | --- |
| `data/chinese_cheese_video.db` | Curriculum, candidates, jobs, YouTube records, publication state, and retry state | Committed to `master` after a workflow run changes it |
| `data/ai_router.db` | Provider calls, cooldowns, successes, and failure state | Committed to `master`; contains state, not raw API keys |
| `output/jobs/<job-id>/` | Render job JSON, audio, captions, storyboard, QA frames, thumbnails, and MP4 | Ignored locally; uploaded as workflow artifacts |
| `public/generated/<job-id>/` | Renderer-readable generated job and visual assets | Ignored locally; uploaded selectively as artifacts |
| `data/local_storage/` | Optional local video storage | Ignored by Git |
| `config/xiangqi_curriculum_en.json` | Versioned 72-lesson curriculum definition | Source-controlled; changes require preflight and tests |

SQLite commits are the persistence mechanism between scheduled runners. A GitHub Actions artifact is useful for inspection, but the state commit is what makes the next run continue in order and avoid duplicates.

## Configuration and secrets

Copy `.env.example` only for local development. Never commit `.env`, OAuth token files, service credentials, API keys, or generated media. The complete configuration map, GitHub secret setup, OAuth procedure, provider permissions, rotation procedure, and safe health checks are in [`docs/configuration.md`](docs/configuration.md).

The production workflow consumes repository Secrets for confidential values and repository Variables for non-confidential behavior. The most important production secrets are `AI_ROUTER_REPO_TOKEN`, `AI_ROUTER_GEMINI_KEYS_JSON`, `AI_ROUTER_HF_KEYS_JSON`, `HF_TOKEN`, `YOUTUBE_OAUTH_TOKEN_JSON`, `CHATGPT_VISUAL_API_KEY`, and `GOOGLE_GROUNDING_API_KEY`. `SUPABASE_SERVICE_ROLE_KEY` is optional and must remain server-side only.

## Operations and troubleshooting

Read [`docs/operations.md`](docs/operations.md) for scheduled operation, manual dispatch, review-only testing, artifact inspection, backup and restore, release handling, and safe recovery. Read [`docs/integrations.md`](docs/integrations.md) for YouTube OAuth, AI Router, Gemini grounding, visual asset generation, Hugging Face, and optional Supabase. Read [`docs/troubleshooting.md`](docs/troubleshooting.md) when a gate fails, a workflow is pending, an audio provider falls back, a thumbnail is not confirmed, or a video is classified with the wrong format.

## Verification commands

Run the following before merging a code change or creating a new release:

```bash
npm run typecheck
python -m py_compile python/*.py
PYTHONPATH=python python -m unittest discover -s python -p 'test_*.py'
PYTHONPATH=python:. python -m unittest discover -s systems -p 'test_*.py'
PYTHONPATH=python python python/curriculum_preflight.py
python3 scripts/check_system_capsules.py systems
```

The production workflow runs additional contract checks with controlled CI variables. Do not weaken those variables locally merely to make a test pass; a production gate that fails is a signal to fix the underlying contract.

## License and visual assets

The repository's own code and documentation follow the repository license policy. The Xiangqi piece assets are documented in `public/assets/CHESS_PIECES_LICENSE.txt` and retain their upstream attribution. Preserve that attribution when redistributing generated assets or rendered samples.

## References

[1]: https://github.com/ysrg2003/chinese-cheese-video "Chinese Cheese Video repository"
[2]: https://github.com/ysrg2003/ai-provider-router "Reusable AI Provider Router"
[3]: https://docs.github.com/actions/security-guides/using-secrets-in-github-actions "GitHub Actions secrets"
[4]: https://developers.google.com/youtube/v3/guides/authentication "YouTube Data API OAuth 2.0"
[5]: https://developers.google.com/youtube/v3/docs/thumbnails/set "YouTube thumbnails.set"
[6]: https://ai.google.dev/gemini-api/docs/api-key "Gemini API keys"
[7]: https://huggingface.co/docs/hub/en/security-tokens "Hugging Face user access tokens"
[8]: https://supabase.com/docs/guides/getting-started/api-keys "Supabase API keys"
