# External Integrations

Chinese Cheese Video is a coordinator. It owns curriculum state, Xiangqi validation, rendering, and publication contracts, while several external services provide models, authentication, discovery signals, or optional storage. This document explains what each integration does, what it must never do, and how to verify it safely.

## Integration map

| Integration | Direction | Production role | Failure behavior |
| --- | --- | --- | --- |
| GitHub Actions | Runner into repository, Router, and YouTube | Schedules and executes production | Run fails or preserves pending state; no invalid publication |
| AI Provider Router | Coordinator into the checked-out Router package | Ordered Gemini and Hugging Face model/key chain | Per-route cooldown, ordered fallback, deterministic safe fallback only where the contract allows it |
| Gemini TTS through Router | Coordinator into Router audio interface | Male `Schedar` narration for English and Chinese | Next Router route, then recorded final Edge fallback if enabled |
| Google/Gemini grounding | Research layer into provider | Grounded sources before script generation | Required production gate fails; no unsupported script is published |
| ChatGPT-compatible visual API | Visual supervisor into external visual endpoint | Scene-specific assets that fit verified board context | Deterministic renderer-safe treatment or asset gate failure |
| YouTube Data API v3 | Publisher into YouTube | Upload, localization, playlists, thumbnails, and read-back | Resumable publication state and bounded reconciliation prevent duplicate uploads |
| Hugging Face Inference Providers | Router into Hugging Face | Fallback model routes | Cooldown, next route, or final safe fallback |
| Supabase | Optional storage backend | Remote alternative to SQLite | `local` or `auto` mode falls back to SQLite |

## GitHub Actions integration

The main workflow is `.github/workflows/render-video.yml`. It checks out the application repository and then checks out `ysrg2003/ai-provider-router` using `AI_ROUTER_REPO_TOKEN`. It uses Node.js 22, Python 3.11, Ubuntu, and `ffmpeg`; it installs the repository’s dependencies and the Router package, then runs preflight, tests, production, artifacts, and state persistence.

The workflow requires `contents: write` to commit SQLite state and `actions: write` to queue a bounded continuation when a transient public publication state needs another run. It uses a single concurrency group and never cancels an active run.

GitHub Secrets are read through the `secrets` context, while non-confidential options use repository Variables. Follow [GitHub’s official secrets documentation](https://docs.github.com/actions/security-guides/using-secrets-in-github-actions) and the exact setup table in [`configuration.md`](configuration.md). Never echo a secret, pass it as a positional command-line argument, or store it in a generated JSON artifact.

## AI Provider Router integration

The Router is a reusable external repository rather than a copy of provider logic inside this project. The production workflow checks it out at `ai-provider-router`, exposes `AI_ROUTER_PATH`, `AI_ROUTER_CONFIG_DIR`, and `AI_ROUTER_STATE_DB`, and installs it as an editable package. The application uses `python/ai_router_bridge.py` to call the Router’s current interface.

The intended ordered chain is:

1. `gemini-2.5-flash` across the configured Gemini key pool.
2. `gemini-2.5-flash-lite` across the configured Gemini key pool.
3. The configured Hugging Face models and token/key pool.
4. A deterministic local fallback only for a contract-approved failure class.
5. Edge TTS as the final narration fallback when enabled and when all AI Router audio routes fail.

The actual key order, model availability, cooldown state, and provider result are recorded in `data/ai_router.db`. Keys themselves must never be written to that database. The validation command is:

```bash
AI_ROUTER_REQUIRE_KEYS=1 \
python python/validate_ai_router_runtime.py
```

A real audio smoke test is:

```bash
TTS_PROVIDER=ai_router \
TTS_VOICE_EN=Schedar \
python python/tts_smoke.py --output-dir tts-smoke
```

Success requires the Router package, valid provider configuration, a generated audio file, and metadata that identifies the selected provider and voice. If the smoke test fails, inspect the Router’s route and cooldown details before changing the application’s provider policy.

## Gemini and research grounding

Production sets `XIANGQI_RESEARCH_REQUIRED=1`, `GOOGLE_GROUNDING_ENABLED=1`, and `GOOGLE_GROUNDING_REQUIRED=1`. The research layer gathers and records source material before the director produces the script. The claim layer then validates legal moves, movement rules, board geometry, and other factual statements against the grounded job data.

`GOOGLE_GROUNDING_API_KEY` is the dedicated production credential. `GOOGLE_GROUNDING_MODEL` defaults to `gemini-2.5-flash`. A missing key, disabled API, rate limit, malformed response, or source timeout must be visible as a gate result. Do not change the required flags to zero in production merely to publish through a failure.

Useful checks are:

```bash
python python/verify_grounding_sources.py
python python/verify_grounded_pipeline.py
```

The first check focuses on source availability and the second exercises the full grounded contract with controlled environment settings. The current Gemini API key guidance is available at [Google AI for Developers](https://ai.google.dev/gemini-api/docs/api-key).

## Visual asset integration

The visual path is split into two responsibilities. The AI visual director reads the narration and board context and creates a sentence-level storyboard; the optional visual asset provider creates a bounded number of scene assets that are inserted only when they pass the asset contract. The renderer itself remains deterministic and can fall back to verified board primitives such as `horse_leg`, `elephant_eye`, `cannon_screen`, legal paths, river overlays, palace boundaries, target markers, and `concept_focus`.

The production variables are:

```text
VISUAL_STORYBOARD_ENABLED=1
VISUAL_ASSET_ENABLED=1
VISUAL_ASSET_MAX_PER_VIDEO=2
VISUAL_ASSET_TIMEOUT_SECONDS=720
CHATGPT_VISUAL_API_BASE=https://yousefsg-chatgpt-api.hf.space
```

`CHATGPT_VISUAL_API_KEY` is secret. The provider endpoint is not allowed to decide Xiangqi legality or replace the board state. A generated image must be inserted into a renderer-safe scene, and the job JSON must retain the asset reference. A provider that returns a visually attractive but semantically unrelated image is a failed asset integration, not a successful generation.

For deterministic contract tests, disable live assets only in the test environment:

```bash
VISUAL_ASSET_ENABLED=0 \
PYTHONPATH=python python -m unittest python/test_visual_assets.py python/test_sentence_visual_supervision.py
```

For a live review, use `review_only=true` and inspect both the job JSON and the rendered frames. Do not use a live visual provider in the unit-test suite.

## YouTube Data API integration

The publisher uses the YouTube Data API v3 with OAuth user authorization. The scopes are:

```text
https://www.googleapis.com/auth/youtube.upload
https://www.googleapis.com/auth/youtube.force-ssl
```

The exact OAuth bootstrap is implemented in `python/youtube_publisher.py`. It runs a local browser consent flow with offline access and writes an authorized-user JSON file. Store that file’s contents in `YOUTUBE_OAUTH_TOKEN_JSON`, not in Git. Read [YouTube’s OAuth guide](https://developers.google.com/youtube/v3/guides/authentication) before changing the application or consent configuration.

The publishing sequence is resumable. It uploads the MP4, applies English and optional Simplified Chinese metadata, creates or selects the configured playlist, and records the YouTube ID. If a later step is pending, the next reconciliation pass repairs the recorded publication rather than uploading a duplicate.

The publisher’s privacy mode is controlled by `YOUTUBE_PUBLISH_MODE`, whose allowed values are `public`, `private`, and `unlisted`. Production currently uses `public` only after all pre-publication gates pass.

## Thumbnail integration and read-back

For standard landscape videos, the publisher uploads the selected generated thumbnail through the official [`thumbnails.set`](https://developers.google.com/youtube/v3/docs/thumbnails/set) method. A successful `thumbnails.set` response alone is not accepted as proof. The publisher then calls `videos.list(part=snippet,id=...)` and verifies that the remote `maxres` thumbnail URL and dimensions match the contract. Only then is the database state set to `api_readback_confirmed`.

Portrait Shorts use `manual_studio_required`. The system does not falsely report an API-uploaded 16:9 thumbnail for a 9:16 video. The operational procedure is to select or upload the portrait-safe image in YouTube Studio on a computer.

The relevant tests are:

```bash
PYTHONPATH=python python -m unittest \
  python/test_youtube_publisher.py \
  python/test_youtube_publisher_fake_api.py \
  python/test_backfill_thumbnails.py
```

## Localization and captions

The default production language is English. The optional secondary output is Simplified Chinese. Localization updates title and description metadata and creates Chinese audio and caption artifacts. In-video captions are renderer content and remain distinct from a separate manually maintained English YouTube caption track.

The publisher uses the job’s language contract to set `defaultLanguage` and `defaultAudioLanguage`. A localization failure is a publication gate failure when localization is required; it must not silently publish a half-localized record.

## Hugging Face integration

Hugging Face is accessed through the Router’s fallback path, using `HF_BASE_URL` and `HF_MODELS`. The recommended production credential is a fine-grained or read-only user access token stored as `HF_TOKEN` or an ordered JSON pool in `AI_ROUTER_HF_KEYS_JSON`. Read [Hugging Face’s token security guide](https://huggingface.co/docs/hub/en/security-tokens) for token creation, least privilege, and revocation.

A Hugging Face failure should be visible in the Router state and logs, then the chain should proceed according to its configured policy. Do not replace a failed Gemini route by editing the application to call Hugging Face directly; that would bypass the Router’s key rotation and cooldown state.

## Optional Supabase integration

SQLite is the production persistence backend because GitHub Actions commits it back to the repository. Supabase is optional and is supported through `python/supabase_store.py` when `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and the SQL migrations are available.

Apply the migrations in order:

```text
sql/001_initial_schema.sql
sql/002_curriculum_schema.sql
```

Use `--storage local` for the default path, `--storage auto` to try Supabase and fall back to SQLite, or `--storage supabase` to require the remote backend. Never put a service-role or Supabase secret key in browser code. Supabase’s current [API key guidance](https://supabase.com/docs/guides/getting-started/api-keys) distinguishes public keys from elevated server-side keys and documents rotation.

## References

[1]: https://github.com/ysrg2003/ai-provider-router "Reusable AI Provider Router"
[2]: https://developers.google.com/youtube/v3/guides/authentication "YouTube Data API OAuth 2.0"
[3]: https://developers.google.com/youtube/v3/docs/thumbnails/set "YouTube thumbnails.set"
[4]: https://ai.google.dev/gemini-api/docs/api-key "Gemini API keys"
[5]: https://huggingface.co/docs/hub/en/security-tokens "Hugging Face user access tokens"
[6]: https://supabase.com/docs/guides/getting-started/api-keys "Supabase API key security"
