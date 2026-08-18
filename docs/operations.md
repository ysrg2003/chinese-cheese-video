# Operations Runbook

This runbook explains how to operate Chinese Cheese Video after configuration is complete. The normal operating model is **GitHub Actions plus committed SQLite state**. The repository is not designed to require a continuously open local session.

## Normal schedule

The production workflow is `.github/workflows/render-video.yml`. GitHub Actions starts it at:

| UTC | User timezone UTC+3 |
| --- | --- |
| 08:15 | 11:15 |
| 14:15 | 17:15 |
| 20:15 | 23:15 |

GitHub may delay scheduled workflows under load. The workflow uses a single concurrency group with `cancel-in-progress: false`, which prevents concurrent catalog mutation and protects an active render from cancellation.

The schedule is a trigger, not a guarantee that a new video will be published on every tick. A run may reconcile public state, discover no eligible candidate, preserve a pending retry state, or stop at a hard quality gate. The workflow must never publish an invalid curriculum item merely to satisfy a schedule.

## First operational verification

After adding the required GitHub Secrets and Variables, run a non-publishing check before enabling public production.

### Step 1: Verify the repository and branch

Run from a local checkout:

```bash
git clone https://github.com/ysrg2003/chinese-cheese-video.git
cd chinese-cheese-video
git fetch origin master
git status --short --branch
```

Expected result: the checkout is on `master` and has no unexpected uncommitted files. If the branch is behind, run `git pull --ff-only origin master`. If the working tree contains local production databases or generated media, copy them to a backup location before cleaning anything.

### Step 2: Run the AI Router smoke test

On GitHub, open **Actions → Chinese Cheese Video — autonomous production → Run workflow**. Set `tts_smoke=true`, keep the other inputs at their defaults, and dispatch the workflow.

Expected result: the checkout, dependency installation, Router validation, and male `Schedar` TTS smoke test pass. No video is produced or published. If checkout fails, fix `AI_ROUTER_REPO_TOKEN`; if key validation fails, fix the Router key-pool JSON; if TTS fails, inspect the provider/model/key order rather than switching directly to Edge TTS.

### Step 3: Run review-only production

Dispatch the workflow with `review_only=true`, `daily_count=1`, `languages=en`, and `discovery_limit=20`.

Expected result: the workflow runs preflight, research, direction, visual supervision, narration, rendering, creative review, and visual QA, but it does not upload to YouTube or advance the publication state. Download the artifact named `chinese-cheese-video-<run-id>` and inspect `output/jobs/<job-id>/job.json`, `visual_qa/visual-qa.json`, the rendered MP4, and the voice-provider metadata.

If the artifact is correct, return to the workflow dispatch form and run the normal production path with `review_only=false`.

### Configured Xiangqi chain smoke

To verify the Xiangqi-aware chain without rendering, publishing, claiming a curriculum lesson, or reconciling YouTube, dispatch the workflow with:

| Input | Value |
|---|---|
| `automation_config` | `config/automation.json` |
| `automation_only` | `true` |
| `publish` | not applicable; `automation_only` is selection-only |
| `review_only` | `false` |
| `daily_count` | `1` |
| `languages` | `en` |
| `shorts_enabled` | `false` |

The artifact must contain `automation-selection.json`. Before curriculum completion, its selected stage must be `curriculum-queue`. After all active curriculum episodes are published, the expected order is `post-curriculum-topic` and then `complete-match-fallback` only when discovery has no fresh candidate. Local deterministic tests should use a temporary SQLite copy and `CONFIGURED_AUTOMATION_DISCOVERY_ENABLED=0` when exercising the fallback.

For Short lineage, do not enable `shorts_enabled` in a selection-only run. Enable it only in a review or production run after the parent job artifact exists. The extractor writes descriptors and lineage evidence; it does not independently upload Shorts. Keep `YOUTUBE_PUBLISH_MODE=private` during this rollout.

## Manual production

Use the normal manual dispatch only when you intentionally want to produce content outside the schedule. The safe default is one candidate in English:

| Input | Recommended value | Reason |
| --- | --- | --- |
| `daily_count` | `1` | Limits one production item per run |
| `languages` | `en` | Preserves English-first curriculum order |
| `discovery_limit` | `20` | Keeps discovery bounded |
| `reconcile_only` | `false` | Allows production after reconciliation |
| `review_only` | `false` | Enables actual publication |
| `tts_smoke` | `false` | Use a separate smoke run for TTS testing |
| `tts_compare` | `false` | Use a separate voice-comparison run |
| `continuation_depth` | `0` | Normal starting depth |
| `automation_config` | empty for legacy path; `config/automation.json` for configured Xiangqi chain | Selects domain-owned stages |
| `automation_only` | `false` | Selection-only configured smoke; no render or publication |
| `shorts_enabled` | `false` | Extracts parent-preserving Short descriptors after a completed parent job |

Never launch a second production workflow while one is active. Check the latest runs first:

```bash
gh run list \
  --workflow render-video.yml \
  --limit 5 \
  --json databaseId,status,conclusion,headSha,createdAt,url
```

Monitor one run until it completes:

```bash
gh run watch <run-id> --interval 20
```

A successful run should end with `status=completed` and `conclusion=success`. The `produce` job should show successful preflight, reconciliation, autonomous production, artifact upload, and state commit steps.

## What happens inside a production run

The runner performs the following sequence, and a failure at a quality gate must not be hidden by a generic fallback:

| Stage | Primary responsibility | Evidence of success |
| --- | --- | --- |
| Checkout | Retrieves the repository and reusable AI Router | Both checkout steps pass |
| Dependencies | Installs Node, Python, `ffmpeg`, JavaScript packages, Python packages, and Remotion browser | All setup steps pass |
| Router validation | Confirms ordered provider chain and key-pool shape | `validate_ai_router_runtime.py` passes |
| YouTube configuration | Confirms OAuth JSON exists when publishing is enabled and privacy mode is valid | Configuration step passes |
| Curriculum preflight | Executes `make_job()` or equivalent contract generation for all 72 lessons | Zero curriculum errors |
| Autonomous preflight | Runs TypeScript, Python, contract, visual, claim, localization, thumbnail, and TTS checks | All controlled CI gates pass |
| Public reconciliation | Reconciles previously uploaded videos before selecting new work | `continuous-reconcile.json` reports `status: complete` |
| Selection | Chooses the next unpublished curriculum item or a deduplicated discovery candidate | Run JSON identifies one selected item |
| Research and direction | Grounds the script, validates claims, generates storyboard and sentence intents | `groundingStatus: grounded`, `claimProof.ok: true` |
| Narration | Generates bounded AI Router Gemini-TTS batches with Schedar | `provider_used: ai_router`, `voice: Schedar`, no fallback error |
| Render | Produces MP4 using `format`-driven dimensions | `lesson/game=1920×1080`; `short=1080×1920` |
| Visual QA | Samples frames and checks board, captions, overlays, and dimensions | `visual_qa/visual-qa.json` reports `ok: true` |
| Creative review | Runs the pre-publication critic and bounded repair loop | Approval decision and score are recorded |
| Publication | Uploads video, localizations, playlist placement, and thumbnail according to policy | YouTube ID and publication state are recorded |
| Read-back | Confirms the actual remote record and standard thumbnail after upload | Standard videos reach `api_readback_confirmed` |
| Persistence | Exports catalog, uploads artifacts, commits SQLite state | GitHub state commit appears when the DB changed |

## Format and thumbnail verification

Use the actual rendered MP4 as the source of truth for local dimensions:

```bash
ffprobe -v error \
  -select_streams v:0 \
  -show_entries stream=width,height,duration \
  -of json \
  output/jobs/<job-id>/<job-id>.mp4
```

Expected result for a standard curriculum lesson or game:

```json
{"width":1920,"height":1080}
```

Expected result for an explicit Short:

```json
{"width":1080,"height":1920}
```

The publisher refuses a format mismatch before upload. For standard videos, `thumbnails.set` is not enough: the publisher calls `videos.list(part=snippet,id=...)`, checks the returned `maxres` thumbnail URL and dimensions, and records `api_readback_confirmed` only after the read-back succeeds. For Shorts, the publisher does not attempt an invalid landscape thumbnail mutation and records `manual_studio_required`.

To backfill old publications, use the dedicated workflow `.github/workflows/backfill-thumbnails.yml`. Supply the actual job IDs. When YouTube does not expose dimensions for an old item, use `--known-dimensions` only with dimensions verified from a trusted artifact or an authoritative remote record:

```bash
python python/backfill_thumbnails.py \
  --job-id <job-id> \
  --known-dimensions <job-id>=1920x1080
```

Do not classify an old video from its curriculum label alone.

## Artifact inspection

Download artifacts with the GitHub CLI:

```bash
mkdir -p /tmp/chinese-cheese-artifacts
cd /tmp/chinese-cheese-artifacts
gh run download <run-id> --repo ysrg2003/chinese-cheese-video --dir .
find . -maxdepth 5 -type f | sort | sed -n '1,240p'
```

The most useful files are:

| Artifact | Inspection purpose |
| --- | --- |
| `job.json` | Selected curriculum item, format, moves, narration, claims, storyboard, and generated assets |
| `director-data.json` | Director output, grounded research, claim proof, and visual supervision |
| `visual_qa/visual-qa.json` | QA result, frame dimensions, scene diagnostics, and errors |
| `visual_qa/scene-*.jpg` | Sampled frames for human visual inspection |
| `localization/zh/voice_provider.json` | Provider, voice, language, batch count, and fallback status |
| `localization/zh/captions.srt` / `.vtt` | Chinese caption timing artifacts |
| `continuous-reconcile.json` | Public-state reconciliation result |
| `youtube-catalog.json` | Normalized catalog export after the run |
| `data/chinese_cheese_video.db` | Persistent artifact database snapshot |
| `data/ai_router.db` | Persistent provider state snapshot |

Never upload an artifact containing a secret. The workflow should redact GitHub Secrets in logs, but a generated file that contains raw credentials is still a security incident.

## Database persistence and backup

The two durable files are `data/chinese_cheese_video.db` and `data/ai_router.db`. Before a manual reset, deletion, migration, or release, create a timestamped backup outside the repository:

```bash
mkdir -p ../chinese-cheese-backups
cp data/chinese_cheese_video.db ../chinese-cheese-backups/chinese_cheese_video-$(date -u +%Y%m%dT%H%M%SZ).db
cp data/ai_router.db ../chinese-cheese-backups/ai_router-$(date -u +%Y%m%dT%H%M%SZ).db
```

Record the Git commit, workflow run, and YouTube audit manifest beside the backup. A backup is not complete unless it can be restored to a separate temporary path and opened by the project’s SQLite code.

The destructive workflows are intentionally separate from production: `delete-all-channel-videos.yml`, `delete-invalid-youtube-videos.yml`, `delete-target-en012.yml`, and `delete-wrong-evergreen.yml`. Review their confirmation requirements and create a backup before using any of them. Do not delete a YouTube video merely to fix a metadata or audio issue until the public record and local catalog have been reconciled.

## Reconciliation and pending publication

If a video upload succeeds but playlist, localization, or thumbnail read-back is pending, the catalog preserves the YouTube ID and the workflow reconciles public state before retrying. This is designed to prevent duplicate uploads. A retry must repair the pending publication state rather than render the same public job again.

The workflow uses bounded reconciliation attempts and may self-dispatch a continuation when a transient retry window expires. `continuation_depth` has a safety cap. If the cap is reached, the run preserves the pending state for the next scheduled run rather than holding a runner indefinitely.

## Emergency freeze

Set the repository Variable `XIANGQI_PRODUCTION_FREEZE=1` to stop new research and production while preserving the repository and reconciliation steps needed to inspect state. Use this when a provider credential is compromised, a public-state mismatch is suspected, or a code change needs investigation. Return it to `0` only after the relevant checks pass.

## Release procedure

A release is a Git tag and GitHub Release pointing to a verified commit. Before creating one:

```bash
git status --short --branch
npm run typecheck
python -m py_compile python/*.py
PYTHONPATH=python python -m unittest discover -s python -p 'test_*.py'
PYTHONPATH=python python python/curriculum_preflight.py
```

Create a tag only after the working tree is clean and the validation output has been saved. The release notes should identify the commit, test count, workflow verification run, production contracts, known non-blocking warnings, and any migration instructions. Do not include secrets or raw OAuth JSON in a release asset.

## References

[1]: https://docs.github.com/actions/writing-workflows/choosing-what-your-workflow-does/control-the-concurrency-of-workflows-and-jobs "GitHub Actions concurrency"
[2]: https://docs.github.com/actions/using-workflows/storing-workflow-data-as-artifacts "GitHub Actions artifacts"
[3]: https://developers.google.com/youtube/v3/docs/thumbnails/set "YouTube thumbnails.set"
[4]: https://developers.google.com/youtube/v3/guides/authentication "YouTube Data API OAuth 2.0"
