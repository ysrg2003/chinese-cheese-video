# v1.3.0 — Production-Ready Autonomous Xiangqi Video System

## Release scope

This release marks the completed autonomous production baseline for Chinese Cheese Video. It includes the format contract, remote thumbnail read-back verification, legacy Short classification, deterministic Xiangqi claim contracts, format-aware visual QA, Schedar Gemini-TTS batching through the reusable AI Provider Router, pre-publication creative review, sentence-level visual supervision, bounded self-repair, public-state reconciliation, curriculum preflight, and the complete English operational documentation set.

This release does not intentionally change production behavior beyond the documentation and release metadata added in this finalization pass. The production state databases are preserved from the latest successful workflow state commit.

## Verified production evidence

| Evidence | Result |
| --- | --- |
| Latest completed stability workflow | [31991752221](https://github.com/ysrg2003/chinese-cheese-video/actions/runs/31991752221) — success |
| Previous standard-video stability workflow | [31990132871](https://github.com/ysrg2003/chinese-cheese-video/actions/runs/31990132871) — success |
| Latest persisted state commit before this release | `1fd9705f7a57bfb7444513e56e2249e3ff4cfb71` |
| Standard-video proof | en-009 `Fpqn9-msA54`, `1920×1080`, thumbnail `api_readback_confirmed` |
| Short-format proof | en-002 `RNyd5i9Qgdk`, `1080×1920`, thumbnail `manual_studio_required` |
| Curriculum | 72-item preflight passes before production |
| Tests | 178 tests passing under the CI contract environment |
| Voice | AI Router Gemini-TTS, male `Schedar` for English and Chinese |
| Claim gate | `claimProof.ok: true` in the verified production runs |
| Visual gate | 20-scene visual QA passed in the verified production runs |

## Operational contracts

`lesson` and `game` curriculum items must render at `1920×1080`. Only explicit `short` items may render at `1080×1920`. Standard thumbnails require both `thumbnails.set` and a subsequent `videos.list` read-back before the database can record `api_readback_confirmed`. Shorts remain `manual_studio_required` and must not receive a false standard-thumbnail success state.

Production narration uses `TTS_PROVIDER=ai_router`, `TTS_VOICE_EN=Schedar`, and `TTS_VOICE_ZH=Schedar`. Audio is generated in bounded batches. Edge TTS is retained only as a final, explicitly recorded fallback after the AI Router chain is exhausted.

The workflow runs at `08:15`, `14:15`, and `20:15` UTC, serializes execution through its concurrency group, reconciles public state before production, validates the entire curriculum, uploads artifacts, and commits SQLite state for the next run.

## Documentation included

| Document | Purpose |
| --- | --- |
| `README.md` | Complete beginner setup and architecture guide |
| `docs/configuration.md` | Secrets, variables, provider setup, verification, rotation, and revocation |
| `docs/operations.md` | Scheduled operation, manual dispatch, artifacts, backups, recovery, and releases |
| `docs/integrations.md` | GitHub, AI Router, Gemini, visual assets, YouTube, Hugging Face, and Supabase integrations |
| `docs/troubleshooting.md` | Root-cause troubleshooting and regression-test mapping |
| `docs/independent_automation.md` | Autonomous architecture and persistence model |

## Known non-blocking note

GitHub may report a Node.js 20 deprecation annotation for third-party actions that are automatically forced onto Node.js 24. This did not affect the verified workflow successes and should be handled in a future dependency-refresh pass.

## Security boundary

No live API key, OAuth token, service credential, or private secret belongs in this release note or in the repository. Configure confidential values through GitHub Actions Secrets as described in `docs/configuration.md`. If a credential is exposed, revoke it at the provider before updating the repository secret.
