# Troubleshooting and Recovery

The system is intentionally strict. A failed gate is evidence that a contract needs attention; it is not permission to publish a lower-quality video. Start by identifying the workflow run, selected job ID, stage, and durable state before changing anything.

## First response checklist

When a run fails or appears stuck, record these values:

| Value | Where to obtain it |
| --- | --- |
| Workflow run ID and URL | GitHub Actions run page or `gh run list` |
| Commit SHA | Run summary and `gh run view <run-id> --json headSha` |
| Failed step | Run page or `gh run view <run-id> --log-failed` |
| Job ID | `automation-run-*.json`, artifact path, or SQLite state |
| Reconciliation status | `continuous-reconcile.json` and its log |
| Curriculum status | `data/chinese_cheese_video.db` or exported catalog |
| YouTube video ID | Publication result, catalog, or YouTube channel audit |
| Artifact path | GitHub artifact named `chinese-cheese-video-<run-id>` |

Do not start another production run until you know whether the failed run uploaded a public video. Reconcile public state first; otherwise a retry can create a duplicate.

## The workflow is still running

Check whether the `produce` job is actively rendering or whether it is waiting on a retry or reconciliation step:

```bash
gh run view <run-id> --json status,conclusion,jobs,url
```

If it is rendering, allow the configured 60-minute job timeout unless the runner is clearly dead. If it is in reconciliation, the workflow may be waiting through its bounded backoff window. If a continuation is queued, do not manually start a duplicate run.

If the run exceeds its timeout, inspect the last completed step and the artifact state. A renderer timeout is different from a publication pending state; the latter must be reconciled before any rerender.

## `Checkout reusable AI Router` fails

**Symptoms.** The workflow receives a 401, 403, or 404 while checking out `ysrg2003/ai-provider-router`.

**Likely causes.** `AI_ROUTER_REPO_TOKEN` is missing, belongs to the wrong GitHub account, lacks Contents read access, has expired, or the repository visibility changed.

**Correction.** Create a least-privilege GitHub token that can read the Router repository, replace the secret, and rerun with `tts_smoke=true`. Do not copy the Router code into this repository as an emergency workaround; the integration contract is that the project consumes the reusable Router.

## `validate_ai_router_runtime.py` fails

**Symptoms.** The workflow reports missing keys, malformed JSON, an unavailable chain, or a missing Router path.

**Correction.** Verify the exact secret names `AI_ROUTER_GEMINI_KEYS_JSON`, `AI_ROUTER_HF_KEYS_JSON`, and `HF_TOKEN`. Validate the JSON structure locally without printing values:

```bash
AI_ROUTER_REQUIRE_KEYS=1 \
python python/validate_ai_router_runtime.py
```

A 401 or 403 from a provider means the credential or project configuration is wrong. A 429 means quota or rate limiting and should be handled by the Router’s cooldown policy. Do not edit `python/llm_router.py` to jump around the configured chain.

## TTS uses the wrong voice or falls back

**Symptoms.** `voice_provider.json` reports a provider other than `ai_router`, a voice other than `Schedar`, or a non-null `fallback_error`.

**Expected production metadata.**

```json
{
  "requested_provider": "ai_router",
  "provider_used": "ai_router",
  "voice": "Schedar",
  "fallback_error": null
}
```

**Correction.** Confirm the workflow environment contains `TTS_PROVIDER=ai_router`, `TTS_VOICE_EN=Schedar`, `TTS_VOICE_ZH=Schedar`, `TTS_BATCH_MAX_CHARS=480`, and `TTS_BATCH_MAX_SEGMENTS=3`. Run the dedicated TTS smoke test. Inspect Router state and provider failures before allowing a fallback.

Edge TTS is an explicitly recorded last resort, not the normal provider. If it is used, the job metadata must identify the fallback. A silent or unrecorded provider switch is a failed integration.

## Curriculum preflight fails

**Symptoms.** `python/curriculum_preflight.py` reports one or more invalid lessons before production begins.

**Correction.** Inspect the lesson key, `format`, FEN, move sequence, claims, visual contract, and template named in the error. Run the focused curriculum tests:

```bash
PYTHONPATH=python python -m unittest \
  python/test_curriculum.py \
  python/test_curriculum_preflight.py \
  python/test_curriculum_gate_integration.py \
  python/test_xiangqi_rules.py
```

A fixed curriculum lesson is a hard contract. Do not replace a failed fixed lesson with a generic fallback or mark it published. Fix the curriculum definition or its deterministic template, add a regression test, rerun the full preflight, and only then continue.

## Claims or grounded research fail

**Symptoms.** `claimProof.ok` is false, `groundingStatus` is not `grounded`, or the production step reports an unsupported Xiangqi claim.

**Likely causes.** The research provider is unavailable, the source evidence does not support the sentence, the move sequence is illegal, the wrong FEN was used, or the director introduced a causal claim from a legal-move field alone.

**Correction.** Check `GOOGLE_GROUNDING_API_KEY`, `GOOGLE_GROUNDING_ENABLED=1`, `GOOGLE_GROUNDING_REQUIRED=1`, and `XIANGQI_RESEARCH_REQUIRED=1`. Inspect the references and claim proof in `director-data.json`. Run:

```bash
PYTHONPATH=python python -m unittest \
  python/test_grounding_and_claims.py \
  python/test_claim_visual_contract.py
```

Do not suppress the required research flags in a production run. If the rule is correct but the script is not, repair the script contract and add a deterministic regression case.

## Visual storyboard or asset integration fails

**Symptoms.** A sentence has no visual intent, a visual asset is generated but not inserted, a storyboard scene uses an unsupported kind, or the rendered scene does not express the narration.

**Correction.** Inspect `sentenceVisualIntents`, `sentenceVisualSupervision`, `visualStoryboard`, `visualAssets`, and `visualStoryboardSource` in `job.json`. The renderer must use verified board primitives for Xiangqi legality. New concepts must use a safe `concept_focus` treatment rather than an invented move.

Run the deterministic tests:

```bash
PYTHONPATH=python python -m unittest \
  python/test_visual_assets.py \
  python/test_visual_director.py \
  python/test_sentence_visual_supervision.py \
  python/test_visual_qa.py
```

For a live external asset provider failure, use `review_only=true` and inspect the response and insertion record. Setting `VISUAL_ASSET_ENABLED=0` is useful for a deterministic test, but it does not prove live asset generation or insertion works.

## Visual QA fails or dimensions are wrong

**Symptoms.** The QA report has `ok: false`, sampled frames have the wrong dimensions, a landscape lesson appears portrait, or a Short appears landscape.

**Correction.** Confirm the job’s authoritative `format` and inspect the actual MP4 with `ffprobe`:

```bash
ffprobe -v error \
  -select_streams v:0 \
  -show_entries stream=width,height,duration \
  -of json \
  output/jobs/<job-id>/<job-id>.mp4
```

Expected contracts are `lesson/game=1920×1080` and `short=1080×1920`. Run:

```bash
PYTHONPATH=python python -m unittest \
  python/test_visual_qa.py \
  python/test_youtube_publisher.py
```

Do not fix one video by editing its metadata. Correct the format routing or responsive layout contract, add a regression test, and rerun the curriculum preflight.

## Audio is present but becomes hard to understand

**Symptoms.** The beginning is clear but later narration becomes quiet, distorted, or clipped.

**Correction.** Inspect the provider metadata, audio duration, and loudness before deleting or republishing anything:

```bash
ffprobe -v error \
  -show_entries stream=codec_name,sample_rate,channels,duration \
  -of json output/jobs/<job-id>/<job-id>.mp4
```

Check that the production path used bounded Router batches and that the audio stream duration matches the video duration. Run the TTS router and caption tests. If a provider generated inconsistent batches, fix the batching or normalization code and preserve the failing case as a regression test. Do not replace a published video until public-state reconciliation confirms the existing record and the replacement plan is documented.

## Standard thumbnail is not confirmed

**Symptoms.** A standard landscape video has `thumbnail_policy` pending, `api_upload_and_readback` without confirmation, or a default thumbnail still appears.

**Correction.** Inspect the publisher result and confirm that the workflow performed both operations:

1. `thumbnails.set` uploaded the selected image.
2. `videos.list(part=snippet,id=...)` read back the remote `maxres` thumbnail and dimensions.

Run:

```bash
PYTHONPATH=python python -m unittest \
  python/test_youtube_publisher.py \
  python/test_youtube_publisher_fake_api.py
```

If the video is a Short, `manual_studio_required` is expected and the API mutation should not be attempted. If it is a standard video, inspect file size, MIME type, dimensions, OAuth scopes, YouTube quota, and the read-back response. Never convert the `thumbnails.set` response alone into `api_readback_confirmed`.

## The workflow selected an unexpected lesson

**Symptoms.** The generated lesson key appears out of order or an older item is selected again.

**Correction.** Compare the curriculum definition with the episode-plan and publication tables in `data/chinese_cheese_video.db`. The authoritative order is `sequence_no` in `curriculum_lessons`, while the selected job’s publication state comes from `curriculum_episode_plans` and `youtube_videos`.

Check for a stale local checkout first:

```bash
git pull --ff-only origin master
```

Then inspect the workflow artifact’s database snapshot. A successful publication must commit the updated SQLite state. If the public video exists but the local catalog says planned, run public reconciliation before any production retry.

## YouTube upload fails after rendering

**Symptoms.** The MP4 and QA pass, but upload, localization, playlist placement, or thumbnail read-back fails.

**Correction.** Do not rerender immediately. First inspect the publication record and run reconciliation:

```bash
python python/continuous_reconcile.py \
  --max-attempts 3 \
  --initial-delay-seconds 30 \
  --max-delay-seconds 120 \
  --max-runtime-minutes 10
```

Check `YOUTUBE_OAUTH_TOKEN_JSON`, channel identity, OAuth scopes, visibility mode, YouTube API enablement, and quota. If the video ID already exists, repair the pending step rather than uploading another copy. The publisher records resumable statuses such as `uploaded_playlist_pending`, `published_localization_pending`, and `published_thumbnail_pending` for this purpose.

## Supabase fails

**Symptoms.** The remote storage path cannot connect, tables are missing, or permissions are rejected.

**Correction.** Confirm `SUPABASE_URL`, the server-side key, and the migration order. Use `--storage local` to continue with SQLite or `--storage auto` to allow the application to fall back automatically. Do not expose `SUPABASE_SERVICE_ROLE_KEY` in browser code or logs.

## The repository contains a secret

Stop production if a credential appears in Git history, an artifact, a log, a screenshot, or a message. Revoke or rotate the credential at the provider, replace the GitHub Secret, remove local copies, and scan the repository:

```bash
git grep -nE 'AIza|hf_[A-Za-z0-9]+|service_role|client_secret|refresh_token' -- ':!data/**' ':!node_modules/**' || true
git log --all -S'REPLACE_WITH_SECRET' --oneline
```

Do not put a real token in the search command. Use provider-side revocation as the primary response; deleting a local file is not sufficient.

## References

[1]: https://docs.github.com/actions/security-guides/using-secrets-in-github-actions "GitHub Actions secrets"
[2]: https://developers.google.com/youtube/v3/guides/authentication "YouTube Data API OAuth 2.0"
[3]: https://developers.google.com/youtube/v3/docs/thumbnails/set "YouTube thumbnails.set"
[4]: https://huggingface.co/docs/hub/en/security-tokens "Hugging Face token security"
[5]: https://supabase.com/docs/guides/getting-started/api-keys "Supabase API key security"
