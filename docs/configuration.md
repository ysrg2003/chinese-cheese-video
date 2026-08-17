# Configuration, Credentials, and Runtime Variables

This document is the authoritative configuration reference for Chinese Cheese Video. It separates **secrets**, **public identifiers**, **runtime variables**, and **derived state** so that a new maintainer can configure the project without guessing. Never paste a real secret into this document, a commit, an issue, a workflow log, or a shell command that may be retained in history.

## Configuration locations

| Location | Use | Security rule |
| --- | --- | --- |
| Local `.env` | Local experiments and dry runs | Ignored by Git; never commit it |
| GitHub repository **Secrets** | API keys, OAuth JSON, private-repository access, and service credentials | Encrypted by GitHub and exposed only to the workflow steps that use them |
| GitHub repository **Variables** | Non-secret defaults, feature flags, model lists, and timeouts | Visible to repository maintainers; never put a credential here |
| `config/*.json` | Versioned policy, playlists, and the 72-lesson curriculum | Source-controlled; no secrets allowed |
| `data/*.db` | Durable SQLite catalog and AI Router state | Generated state; committed by the production workflow so the next runner can continue |

The GitHub setup path is **Repository → Settings → Secrets and variables → Actions**. Use the **Secrets** tab for confidential values and the **Variables** tab for non-confidential values. The exact GitHub procedure is documented in [GitHub’s official secrets guide](https://docs.github.com/actions/security-guides/using-secrets-in-github-actions).

## Production secrets

The following values are consumed by `.github/workflows/render-video.yml`. Secret names are case-sensitive.

| Secret | Classification | Required for | Safe format | Rotation trigger |
| --- | --- | --- | --- | --- |
| `AI_ROUTER_REPO_TOKEN` | GitHub access token | Checking out private `ysrg2003/ai-provider-router` | A GitHub token with minimum read access to that repository | Token expiry, exposure, permission change, or repository transfer |
| `AI_ROUTER_GEMINI_KEYS_JSON` | API-key pool | Gemini director, research, visual supervision, and related AI Router calls | JSON array of objects containing `id`, `key`, and optional `project` | Any suspected exposure or provider key rotation |
| `AI_ROUTER_HF_KEYS_JSON` | API-key pool | Ordered Hugging Face fallback keys | JSON array of objects or the exact format accepted by the checked-out AI Router version | Token exposure, expiry, or provider policy change |
| `HF_TOKEN` | Hugging Face access token | Hugging Face Inference Providers fallback | `hf_REPLACE_WITH_TOKEN` | Expiry, exposure, or permission change |
| `YOUTUBE_OAUTH_TOKEN_JSON` | OAuth authorized-user JSON | Video upload, metadata localization, playlist placement, and thumbnail operations | JSON emitted by the repository’s OAuth bootstrap command | Revocation, expiry without refresh, wrong channel, or exposure |
| `YOUTUBE_API_KEY` | Google API key | Optional public YouTube search during discovery | Google API key string | Exposure, restriction change, or project rotation |
| `CHATGPT_VISUAL_API_KEY` | Visual API key | Optional generated visual assets through the configured visual API | Provider-issued token string | Exposure, expiry, or endpoint change |
| `GOOGLE_GROUNDING_API_KEY` | Google/Gemini API key | Required production research grounding | Google API key string | Exposure, quota, or project rotation |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase server-side secret | Optional Supabase storage backend | Supabase secret or legacy `service_role` key | Exposure or Supabase key migration |

GitHub’s built-in `GITHUB_TOKEN` is used by the workflow for its own repository actions. Do not create a custom `GITHUB_TOKEN` secret. The workflow also uses `actions: write` and `contents: write` permissions so it can dispatch bounded continuations and commit SQLite state.

### `AI_ROUTER_REPO_TOKEN` — private AI Router checkout

**Purpose.** The production workflow checks out `ysrg2003/ai-provider-router` into `ai-provider-router` and installs it with `pip install -e ai-provider-router`. Without this secret, a private Router repository cannot be checked out.

**Classification.** Secret GitHub access token.

**How to obtain it.** Open [GitHub token settings](https://github.com/settings/personal-access-tokens), create a fine-grained token owned by the account that can read `ysrg2003/ai-provider-router`, and grant only repository **Contents: Read** access to that repository. Use the shortest practical expiry and record the expiry date in your password manager.

**Where to add it.** In `ysrg2003/chinese-cheese-video`, open **Settings → Secrets and variables → Actions → Secrets → New repository secret**, enter the exact name `AI_ROUTER_REPO_TOKEN`, paste the token, and click **Add secret**. GitHub should display the name without revealing the value.

**Minimal verification.** Dispatch the workflow with `tts_smoke=true`. The step **Checkout reusable AI Router** must pass, and the logs must never print the token.

**If it fails.** A checkout `404` or `403` usually means the token belongs to the wrong account, lacks repository access, has expired, or the repository is not private-accessible to that account. Confirm the repository name and token scope, replace the secret, and rerun the smoke test.

**Rotation and revocation.** Create the replacement token first, update the GitHub secret, run the smoke test, then revoke the old token at the GitHub token settings page. If the token was exposed, revoke it immediately before creating its replacement.

### `AI_ROUTER_GEMINI_KEYS_JSON` — ordered Gemini key pool

**Purpose.** Provides the AI Router with the ordered Gemini key pool used by the configured chain. The Router tracks per-key success, failure, cooldown, and provider state in `data/ai_router.db`; it does not store the raw keys there.

**Classification.** Secret JSON key pool.

**Safe placeholder.** Use a parseable structure such as:

```json
[
  {"id":"gemini-primary-1","key":"REPLACE_WITH_GEMINI_KEY","project":"google-project-label"},
  {"id":"gemini-secondary-1","key":"REPLACE_WITH_GEMINI_KEY","project":"google-project-label"}
]
```

**How to obtain it.** Open [Google AI Studio API keys](https://aistudio.google.com/app/apikey), sign in to the Google account that owns the intended project, create or select the project, create a key, and store the key in a password manager. Do not paste the live value into source control. The [Gemini API key guide](https://ai.google.dev/gemini-api/docs/api-key) explains the provider-side authentication model.

**Where to add it.** Add the complete JSON array as the GitHub repository secret `AI_ROUTER_GEMINI_KEYS_JSON`. Do not add it as a repository variable. Local runs may use the same variable in `.env` for a controlled private environment.

**Minimal verification.** Run `python python/validate_ai_router_runtime.py` with `AI_ROUTER_REQUIRE_KEYS=1`. Success confirms that the key pool parses and the configured ordered chain is available without printing key values.

**If it fails.** A JSON parse error means the array contains invalid JSON, trailing comments, or shell quoting damage. A zero-key error means the secret is empty or named incorrectly. A 401/403 means the key is invalid, disabled, restricted to the wrong API, or tied to a project without the required API enabled. A 429 means quota or rate limiting; the Router will use its ordered cooldown and fallback policy, but quotas must still be managed at the provider project level.

**Rotation and revocation.** Create replacement keys, update the array while preserving the intended order, run `tts_smoke=true`, and only then revoke old keys in Google AI Studio or Google Cloud. If a key was exposed, revoke it immediately and replace it in every environment.

### `AI_ROUTER_HF_KEYS_JSON` and `HF_TOKEN` — Hugging Face fallback

**Purpose.** These values support the Hugging Face portion of the AI Router chain after the ordered Gemini routes are exhausted or cooled down. `HF_TOKEN` is the simplest single-token setup; `AI_ROUTER_HF_KEYS_JSON` is useful when the Router is configured for an ordered pool.

**Classification.** Secret access-token or JSON key pool.

**How to obtain it.** Open the official [Hugging Face access-token settings](https://huggingface.co/settings/tokens), create a token dedicated to this production system, and select the minimum read or fine-grained permissions required by the configured inference route. Hugging Face recommends one token per application and fine-grained tokens for production use.[1]

**Safe values.**

```text
HF_TOKEN=hf_REPLACE_WITH_TOKEN
```

```json
[
  {"id":"hf-production-1","token":"REPLACE_WITH_HF_TOKEN"}
]
```

**Where to add them.** Add `HF_TOKEN` and, if used, `AI_ROUTER_HF_KEYS_JSON` under GitHub repository Secrets. Keep `HF_MODELS` as a repository Variable because model names are not secrets.

**Minimal verification.** Run `python python/validate_ai_router_runtime.py` and then dispatch `tts_smoke=true`. The validation must report a configured Hugging Face route without revealing the token.

**If it fails.** A 401/403 means the token is invalid, expired, pending organization approval, or missing access to the requested model/provider. A model-not-found error means `HF_MODELS` contains an unsupported identifier. A rate-limit error requires cooldown or provider-side quota management; do not work around quotas by duplicating tokens without following provider terms.

**Rotation and revocation.** Use the token settings page to refresh or delete the token, replace the GitHub secret, run the smoke test, and delete the old token. If a token is leaked, revoke it immediately; Hugging Face documents a dedicated revocation path in its [token security guide](https://huggingface.co/docs/hub/en/security-tokens).

### `YOUTUBE_OAUTH_TOKEN_JSON` — YouTube authorized-user credentials

**Purpose.** Authorizes uploads, metadata localization, playlist placement, and thumbnail operations for the Xiangqi Lab channel. The project uses OAuth user authorization rather than a service account because the YouTube Data API does not support service-account access to a linked YouTube channel.[2]

**Classification.** Secret OAuth authorized-user JSON containing an access token and refresh token.

**Scopes.** The publisher requests:

```text
https://www.googleapis.com/auth/youtube.upload
https://www.googleapis.com/auth/youtube.force-ssl
```

**Before you begin.** Use the Google account that owns the target YouTube channel. In [Google Cloud Console](https://console.cloud.google.com/), create or select the project, enable **YouTube Data API v3**, configure the OAuth consent screen, and create an OAuth client for a desktop application. Download the client JSON to a local path that is ignored by Git, such as `client_secrets.json`.

**Generate the token locally.** From the repository root, run:

```bash
python python/youtube_publisher.py \
  --auth-client-secrets client_secrets.json \
  --auth-output youtube-token.json
```

The command opens a local browser consent page. Approve the two scopes for the intended channel. The script uses an offline token flow and writes the authorized-user JSON to `youtube-token.json`. Confirm that the file exists, but do not print it.

**Store it in GitHub.** Open the repository’s **Settings → Secrets and variables → Actions → Secrets → New repository secret**, use the exact name `YOUTUBE_OAUTH_TOKEN_JSON`, and paste the full file contents. Do not commit `youtube-token.json` or `client_secrets.json`; both are ignored by `.gitignore`.

**Minimal verification.** First run a dry publisher check that does not upload:

```bash
python python/youtube_publisher.py \
  --video output/jobs/<job-id>/<job-id>.mp4 \
  --job-json output/jobs/<job-id>/job.json \
  --dry-run
```

Then run the workflow with `review_only=true` to validate the MP4 without publication. Finally, use a normal production run only when the OAuth account, channel, and visibility setting have been checked.

**If it fails.** A missing-secret error means the name is wrong or the secret is not available to the repository. An expired-token-without-refresh-token error means the OAuth flow was not created with offline access; repeat the bootstrap. A 403 usually means YouTube Data API v3 is disabled, the consent screen is incomplete, the scope is missing, the wrong Google account was authorized, or the channel is not the intended destination. A quota error is provider-side and should not be hidden by retries.

**Rotation and revocation.** Revoke the OAuth client grant in the Google Account security page or Google Cloud credentials page, delete the old GitHub secret, run the bootstrap again, update the secret, and test with `review_only=true`. If the JSON was exposed, revoke it immediately; an OAuth refresh token must be treated as a channel-level credential.

### `CHATGPT_VISUAL_API_KEY` — visual asset provider

**Purpose.** Authorizes the configured visual API at `CHATGPT_VISUAL_API_BASE`, currently defaulting to `https://yousefsg-chatgpt-api.hf.space`. The visual supervisor uploads or references verified board context and requests scene-specific assets rather than arbitrary unrelated images.

**Classification.** Secret API key.

**Where to add it.** Add `CHATGPT_VISUAL_API_KEY` as a GitHub repository Secret and keep the endpoint in the non-secret repository Variable `CHATGPT_VISUAL_API_BASE` if it needs to change.

**Minimal verification.** Run the visual asset tests with `VISUAL_ASSET_ENABLED=0` for deterministic contract testing, then run a controlled production or review-only job with the provider enabled. The resulting job JSON must show a storyboard and any generated assets must be inserted into a renderer-safe scene; an asset that is generated but not referenced is a failed integration.

**If it fails.** Check the endpoint, key, timeout, provider availability, and response shape. Set `VISUAL_ASSET_ENABLED=0` only for a deterministic diagnostic run; do not treat that diagnostic as proof that live asset generation works.

**Rotation and revocation.** Rotate the key at the provider, update the GitHub Secret, and rerun the controlled review-only test.

### `GOOGLE_GROUNDING_API_KEY` — production research grounding

**Purpose.** Supports the required research phase before production script generation. The workflow uses `GOOGLE_GROUNDING_REQUIRED=1` and `XIANGQI_RESEARCH_REQUIRED=1`, so a missing or unusable grounding path is a production gate failure rather than a reason to publish unsupported claims.

**Classification.** Secret Google/Gemini API key.

**How to obtain it.** Use the same provider account and project controls described in the [Gemini API key guide](https://ai.google.dev/gemini-api/docs/api-key). Enable the API required by the current research implementation and restrict the key to the intended project where possible.

**Where to add it.** Add the key as `GOOGLE_GROUNDING_API_KEY`. The workflow has a compatibility fallback to `GEMINI_API_KEY_1` only when the dedicated secret is absent, but a dedicated grounding secret is clearer and safer.

**Minimal verification.** Run `python python/verify_grounding_sources.py` in an environment where the required research flags and key are set. The result must report grounded sources rather than a disabled or cached-only path.

**If it fails.** Check the key, model name, API enablement, timeout, quota, and the `GOOGLE_GROUNDING_MODEL` variable. Do not set `GOOGLE_GROUNDING_REQUIRED=0` in production merely to bypass a research failure.

**Rotation and revocation.** Rotate the key at the provider, update the GitHub Secret, and rerun the grounded pipeline verification.

### `SUPABASE_SERVICE_ROLE_KEY` — optional remote storage

**Purpose.** Enables the optional Supabase backend when `STORAGE_BACKEND=supabase` or when `--storage supabase` is selected. SQLite remains the normal persistent backend for GitHub Actions.

**Classification.** Highly privileged server-side secret. Supabase documents that the legacy `service_role` key has elevated access and bypasses Row Level Security; newer projects may expose a secret key instead.[3]

**How to obtain it.** Open the target project in the [Supabase dashboard](https://supabase.com/dashboard), go to **Settings → API Keys**, and copy the server-side secret or legacy service-role key appropriate to the current project. Keep the project URL separately as `SUPABASE_URL`.

**Where to add it.** Add `SUPABASE_SERVICE_ROLE_KEY` as a GitHub Secret. Never put it in browser code, a public variable, a README, a screenshot, or a URL. Add `SUPABASE_URL` as a non-secret repository Variable only if the remote backend is actually enabled.

**Minimal verification.** Apply the repository SQL migrations in `sql/001_initial_schema.sql` and `sql/002_curriculum_schema.sql`, then run a controlled local command with `--storage supabase`. A successful run must create or read the expected tables and must not log the key.

**If it fails.** Check that the URL belongs to the same project as the key, that the migrations were applied, and that the server-side request is not being made from a browser. If Supabase is unavailable, use `--storage local` or `--storage auto`; the production system is designed to continue with SQLite.

**Rotation and revocation.** Create a replacement server-side key in the Supabase API Keys page, update every secure consumer, verify the backend, then disable or delete the old key. Treat any previously exposed legacy service-role key as compromised and rotate it immediately.

## Non-secret repository variables

The workflow already supplies production defaults for many variables. Set only the values that must differ from those defaults. The following table documents the important supported variables and their effective production behavior.

| Variable | Type and default | Effect |
| --- | --- | --- |
| `AI_ROUTER_CHAIN` | string; `default` | Selects the ordered Router chain |
| `AI_ROUTER_REQUIRE_KEYS` | boolean-like; `1` in production | Requires configured provider keys during runtime validation |
| `HF_BASE_URL` | URL; `https://router.huggingface.co/v1` | Hugging Face OpenAI-compatible endpoint |
| `HF_MODELS` | comma-separated model list; `openai/gpt-oss-120b:fastest` | Ordered Hugging Face fallback models |
| `GEMINI_PRIMARY_MODEL` | string; `gemini-2.5-flash` | Primary Gemini model in direct/local Router settings |
| `GEMINI_SECONDARY_MODEL` | string; `gemini-2.5-flash-lite` | Secondary Gemini model |
| `AI_MAX_ATTEMPTS` | integer; `24` | Maximum AI route attempts in the local Router |
| `AI_REQUEST_TIMEOUT_SECONDS` | integer; `90` | Per-request AI timeout in local Router code |
| `TTS_PROVIDER` | enum; `ai_router` in production | Narration provider selector |
| `TTS_VOICE_EN` | string; `Schedar` in production | English Gemini-TTS voice |
| `TTS_VOICE_ZH` | string; `Schedar` in production | Chinese Gemini-TTS voice |
| `TTS_BATCH_MAX_CHARS` | integer; `480` in production | Maximum characters per TTS batch |
| `TTS_BATCH_MAX_SEGMENTS` | integer; `3` in production | Maximum segment count in a bounded batch |
| `TTS_EDGE_FALLBACK_ENABLED` | boolean-like; code default `1` | Permits final Edge fallback after AI Router failure; keep enabled only as an explicitly recorded last resort |
| `TTS_EDGE_VOICE_EN` | string; provider-specific | English Edge fallback voice for controlled fallback tests |
| `TTS_EDGE_VOICE_ZH` | string; provider-specific | Chinese Edge fallback voice for controlled fallback tests |
| `USE_WORD_CAPTIONS` | boolean-like; `1` in production | Enables word-timed caption generation |
| `VISUAL_STORYBOARD_ENABLED` | boolean-like; `1` in production | Enables AI storyboard supervision |
| `VISUAL_ASSET_ENABLED` | boolean-like; `1` in production | Enables the external visual asset path |
| `VISUAL_ASSET_MAX_PER_VIDEO` | integer; `2` in production | Limits external visual assets per video |
| `VISUAL_ASSET_TIMEOUT_SECONDS` | integer; `720` in production | Visual asset request timeout |
| `CHATGPT_VISUAL_API_BASE` | URL; `https://yousefsg-chatgpt-api.hf.space` | Visual asset endpoint |
| `PREPUBLISH_CRITIC_REQUIRED` | boolean-like; `1` in production | Requires creative review before publication |
| `PREPUBLISH_CRITIC_MAX_ITERATIONS` | integer; `2` | Maximum creative-critic repair iterations |
| `SELF_REPAIR_ENABLED` | boolean-like; `1` in production | Enables bounded self-repair for recoverable job defects |
| `SELF_REPAIR_MAX_ATTEMPTS` | integer; `2` | Maximum self-repair attempts |
| `XIANGQI_RESEARCH_REQUIRED` | boolean-like; `1` in production | Requires research grounding |
| `GOOGLE_GROUNDING_ENABLED` | boolean-like; `1` in production | Enables Google/Gemini grounding |
| `GOOGLE_GROUNDING_REQUIRED` | boolean-like; `1` in production | Blocks production if required grounding fails |
| `GOOGLE_GROUNDING_MODEL` | string; `gemini-2.5-flash` | Grounding model |
| `GOOGLE_GROUNDING_TIMEOUT_SECONDS` | integer; `90` | Grounding request timeout |
| `RESEARCH_SOURCE_TIMEOUT_SECONDS` | integer; `25` | Source fetch timeout |
| `RESEARCH_ALLOW_CACHE` | boolean-like; implementation default | Allows approved research cache behavior |
| `YOUTUBE_PUBLISH_ENABLED` | boolean-like; `1` in production workflow | Enables upload and publication |
| `YOUTUBE_PUBLISH_MODE` | enum `public`, `private`, or `unlisted`; `public` | YouTube visibility for new uploads |
| `YOUTUBE_LOCALIZATION_ENABLED` | boolean-like; `1` | Adds configured localized title and description metadata |
| `YOUTUBE_AUTO_CREATE_PLAYLISTS` | boolean-like; `1` | Creates missing configured playlists when permitted |
| `YOUTUBE_HTTP_TIMEOUT_SECONDS` | integer; `180` in production | YouTube HTTP timeout, clamped by publisher code |
| `YOUTUBE_THUMBNAIL_READBACK_ATTEMPTS` | integer; `3` | Read-back attempts after standard thumbnail upload |
| `YOUTUBE_CHANNEL_ID` | public identifier | Expected channel identifier |
| `YOUTUBE_CHANNEL_HANDLE` | public identifier; default channel handle | Human-readable channel handle |
| `YOUTUBE_CHANNEL_TITLE` | public label | Channel title used in metadata |
| `YOUTUBE_ENGLISH_CAPTIONS_IN_VIDEO` | boolean-like | Controls optional manual English caption-track maintenance; in-video captions remain part of the renderer contract |
| `DISCOVERY_RSS_QUERY` | string; `xiangqi OR "Chinese chess" OR 象棋` | RSS discovery query |
| `DISCOVERY_RSS_FEEDS` | comma-separated URLs; empty means defaults | Optional explicit RSS feeds |
| `YOUTUBE_SEARCH_QUERY` | string; `xiangqi Chinese chess` | Optional YouTube discovery query |
| `YOUTUBE_LOOKBACK_DAYS` | integer; `7` | YouTube discovery lookback window |
| `DAILY_CONTENT_COUNT` | integer; `1` | Default local production count |
| `AUTOMATION_LANGUAGES` | comma-separated; `en,zh` | Default local automation languages |
| `DISCOVERY_LIMIT` | integer; `20` | Default local discovery limit |
| `LOCAL_DB_PATH` | path; `data/chinese_cheese_video.db` | SQLite catalog location |
| `AI_ROUTER_STATE_DB` | path; `data/ai_router.db` | Router state location |
| `AI_ROUTER_PATH` | path; local `../ai-provider-router`, CI `ai-provider-router` | Reusable Router checkout |
| `AI_ROUTER_CONFIG_DIR` | path; Router `config` directory | Router configuration location |
| `SUPABASE_URL` | URL; empty unless remote storage is used | Optional Supabase project URL |
| `STORAGE_BACKEND` | enum `local`, `auto`, `supabase`; local default | Storage backend selection |
| `XIANGQI_PRODUCTION_FREEZE` | boolean-like; `0` | Set to `1` for an emergency production freeze; preflight and production steps are skipped |
| `XIANGQI_REVIEW_ONLY` / `REVIEW_ONLY` | boolean-like; `0` | Blocks upload and publication-state advancement for review-only runs |
| `PIPELINE_ATTEMPT_TIMEOUT_SECONDS` | integer; `1200` | Local pipeline attempt timeout |
| `RECONCILIATION_MAX_ATTEMPTS` | integer; workflow override `4` | Bounded public-state reconciliation attempts |
| `RECONCILIATION_INITIAL_DELAY_SECONDS` | integer; workflow override `30` | First reconciliation delay |
| `RECONCILIATION_MAX_DELAY_SECONDS` | integer; workflow override `120` | Maximum reconciliation delay in CI |
| `RECONCILIATION_MAX_RUNTIME_MINUTES` | integer; workflow override `15` | Reconciliation runtime cap in CI |
| `CURRICULUM_PROCESSING_STALE_SECONDS` | integer; code default `900` | Stale curriculum processing threshold |

## JSON key-pool validation

Never use a single comma-separated string when the Router is configured for structured key pools. Use valid JSON, preserve the intended key order, and validate it without printing the secrets:

```bash
AI_ROUTER_REQUIRE_KEYS=1 \
python python/validate_ai_router_runtime.py
```

Expected result: the command reports the configured chain and key-pool shape without printing raw values. If the command reports malformed JSON, validate the secret in a local file with a JSON parser, replace shell-newline damage, and update the GitHub Secret.

## Local `.env` example

The tracked `.env.example` is intentionally conservative and contains placeholders. Copy it only for local work:

```bash
cp .env.example .env
```

Production uses GitHub Actions Secrets and Variables instead of committing a local `.env`. The local file must remain ignored by Git.

## Secret exposure response

If any credential appears in a chat, commit, issue, terminal capture, artifact, screenshot, or log, treat it as compromised. Revoke or rotate it at the provider first, replace the GitHub Secret, remove the exposed value from local files, run secret scanning, and inspect the Git history. Do not rely on deleting the visible message or file alone. For GitHub, Hugging Face, Google, YouTube, and Supabase, follow the provider-specific rotation procedures above.

## References

[1]: https://huggingface.co/docs/hub/en/security-tokens "Hugging Face user access tokens"
[2]: https://developers.google.com/youtube/v3/guides/authentication "YouTube Data API OAuth 2.0 authorization"
[3]: https://supabase.com/docs/guides/getting-started/api-keys "Supabase API keys and service-role security"
[4]: https://docs.github.com/actions/security-guides/using-secrets-in-github-actions "Using secrets in GitHub Actions"
[5]: https://ai.google.dev/gemini-api/docs/api-key "Gemini API keys"
[6]: https://github.com/ysrg2003/ai-provider-router "Reusable AI Provider Router"
