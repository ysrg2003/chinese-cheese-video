# Chinese Cheese Video — Engineering Context

## 1. الهوية والحدود (Identity and boundaries)

This repository is the specialized production system for the Xiangqi Lab YouTube channel. It selects a curriculum item or a rights-safe discovered topic, validates Xiangqi rules and grounded claims, creates narration and visual supervision data, renders a Remotion video, runs quality gates, publishes when enabled, reconciles remote state, and persists SQLite state for the next scheduled run.

The project is not a generic game engine and is not the reusable framework template. Xiangqi rules, curriculum facts, piece assets, channel policy, and provider configuration remain domain-owned. The newly added `systems/` directory contains only replaceable capabilities: config-driven stage execution, namespaced reusable state evidence, and derivative lineage.

> **Production constraint:** `python/automation_runner.py` and `python/local_store.py` remain the owners of the existing Xiangqi production lifecycle. The new configured automation chain is additive until a future migration proves equivalent behavior with integration evidence.

## 2. Read order before changing code

Read this file, then `README.md`, `docs/independent_automation.md`, `docs/operations.md`, `docs/reusable-systems.md`, the relevant workflow, the owning Python module, and its tests. Never infer a contract from a filename alone. Trace the caller, data schema, state transition, and regression test before editing.

## 3. خريطة الطبقات ومسارات التشغيل (Runtime and entrypoints)

| Area | Owner | Important paths |
|---|---|---|
| Curriculum | 72 English-first Xiangqi lessons and episode state | `config/xiangqi_curriculum_en.json`, `python/curriculum.py`, `python/local_store.py` |
| Autonomous production | curriculum-first selection, discovery, retries, self-repair, pipeline invocation | `python/automation_runner.py` |
| Discovery | RSS, optional YouTube signal, pairings, evergreen series, optional AI idea | `python/content_discovery.py` |
| Domain rules | FEN and legal move validation, horse-leg, river, palace, cannon, flying-general constraints | `python/xiangqi_rules.py`, `python/xiangqi_claims.py` |
| Director | narration, claims, storyboard, visual intent, deterministic fallback | `python/director.py`, `python/visual_director.py` |
| Audio | AI Router Gemini-TTS, Schedar voice, bounded batches, Edge last resort | `python/tts.py`, `python/ai_router_bridge.py` |
| Renderer | Xiangqi board, moves, captions, overlays, assets | `src/index.tsx`, `src/Composition.tsx`, `src/xq.ts` |
| QA and publication | contract gates, visual QA, thumbnails, YouTube read-back | `python/integration_contracts.py`, `python/visual_qa.py`, `python/youtube_publisher.py` |
| Scheduled automation | three daily runs, concurrency, artifacts, SQLite commit | `.github/workflows/render-video.yml` |
| Reusable capsules | generic orchestration, reusable evidence state, derivative lineage | `systems/`, `config/automation.json` |

## 4. دورة البيانات (Data flow)

```text
curriculum JSON / discovery sources
  -> LocalStore candidate and curriculum state
  -> curriculum gate or diverse discovery selection
  -> candidate payload and stable job id
  -> director and Xiangqi claim proof
  -> sentence-level storyboard and visual assets
  -> TTS, cues, captions, and timing
  -> Remotion render
  -> visual/editorial QA and thumbnail contract
  -> YouTube publication and read-back when enabled
  -> LocalStore reconciliation and SQLite commit
```

The configured capsule flow is intentionally narrower:

```text
config/automation.json
  -> systems/config_driven_automation
  -> python/configured_automation_adapter.py
  -> existing LocalStore curriculum/discovery selection
  -> systems/durable_content_state reusable_* evidence
```

It produces a selection envelope and does not render or publish.

## 5. العقود والحالة الموجودة (Existing state contract)

`python/local_store.py` owns legacy tables including `content_candidates`, `video_jobs`, `automation_runs`, `youtube_publications`, curriculum tables, provider state, and normalized YouTube catalog tables. Its `add_candidate` uses the legacy fingerprint/insert behavior; do not replace it casually. `automation_runner.py` depends on curriculum claim/recovery, publication reconciliation, stable job IDs, and status transitions.

The production workflow commits only the SQLite files under `data/`. Never copy those databases into a capsule or expose their contents in documentation. A workflow artifact is for inspection; the state commit is what allows the next scheduled run to continue and avoid duplicate production.

## 6. العقود القابلة لإعادة الاستخدام (Reusable capsule contracts)

### `systems/config_driven_automation/`

The loader validates `schema_version=1`, `domain_id`, unique stage IDs, module, entrypoint, enabled, `on_error`, and kwargs. Relative paths resolve from the repository root. The orchestrator invokes only accepted entrypoint arguments, records every attempt, stops at `selected`, continues at `no_candidate` or `no_valid_candidate`, and skips exceptions only when the config says `on_error=skip`.

The Xiangqi configuration contains one additive adapter stage, `curriculum-or-discovery`, whose module is `configured_automation_adapter`. The production workflow does not use this chain automatically; enabling it requires a separate integration decision and workflow gate.

### `systems/durable_content_state/`

`DurableStateStore` is intentionally namespaced. Its default tables are `reusable_content_variants`, `reusable_short_lineage`, and `reusable_automation_runs`. This avoids collisions with the older Xiangqi schema while allowing the host to persist generic fingerprints, lineage, and automation evidence in the same SQLite file or a temporary copy.

The store is restart-safe for its own identities: variant writes use fingerprint upsert, lineage writes validate the source interval, and automation run writes use a stable run ID. The host still owns publication state, candidate status, curriculum claims, and YouTube records.

### `systems/derivative_lineage/`

The pure capsule computes a parent fingerprint, a source-window fingerprint, metadata that preserves parent metadata, and a filter for already-used windows. It does not call a renderer, TTS, YouTube, or a domain ruleset. A future Short or derivative adapter must supply a valid parent payload and persist the result through `DurableStateStore` after the downstream job is accepted.

## 7. Compatibility facades and adapters

`python/automation_config.py` and `python/automation_orchestrator.py` preserve CLI/import paths while delegating to the capsule. `python/configured_automation_adapter.py` translates Xiangqi curriculum/discovery semantics into the generic stage result. `python/derivative_lineage.py` exposes the pure derivative functions to legacy Python callers.

The configured Xiangqi chain in `config/automation.json` is now production-wired behind `--automation-config` and the `automation_config` workflow input. Its order is authoritative: `curriculum-queue` first, `post-curriculum-topic` only after the active curriculum is complete, and `complete-match-fallback` only when discovery has no fresh candidate. The chain stops at the first `selected` result. When `automation_only=true`, `automation_runner.py` writes `output/automation-selection.json` and stops before candidate claims, rendering, publication, or curriculum advancement.

`python/continuous_topic_generator.py` owns the post-curriculum Xiangqi adapter. It checks `LocalStore.curriculum_gate()`, rejects early activation, filters published topic and move signatures, optionally calls the existing discovery layer, and persists a restart-safe cursor in `reusable_generation_state`. `python/complete_match_generator.py` owns the Xiangqi-specific game adapter. It reads `config/xiangqi_complete_match_profiles.json`, generates deterministic legal playouts from the standard FEN, requires a terminal checkmate or stalemate and a minimum profile length, validates the full sequence through `xiangqi_rules.validate_move_sequence`, then records the candidate and variant evidence.

`python/short_highlight_generator.py` is the Xiangqi derivative adapter. After a parent job completes, it chooses bounded tactical/decision windows, copies parent metadata, writes Short descriptors under `output/shorts/<parent-job-id>/`, and records `reusable_short_lineage` and `reusable_content_variants`. Repeating the extraction for the same parent is idempotent and returns `no_candidate` for already-recorded windows. Actual renderer/publisher submission remains a separate policy-controlled step; descriptor extraction alone never uploads to YouTube.

The adapter is the only place allowed to know that `domain=xiangqi`, that `LocalStore.get_next_curriculum_candidate` is authoritative, or that discovery is optional. Do not place Xiangqi rules, playlist keys, source facts, OAuth, or provider calls in `systems/*/core.py`.

## 8. الاختبارات والتحقق (Verification commands)

From the repository root:

```bash
npm run typecheck
python3 -m py_compile python/*.py
PYTHONPATH=python python3 -m unittest discover -s python -p 'test_*.py' -q
PYTHONPATH=python:. python3 -m unittest discover -s systems -p 'test_*.py' -q
python3 scripts/check_system_capsules.py systems
PYTHONPATH=python python3 python/curriculum_preflight.py
```

The existing Python suite should use the workflow contract environment when local defaults would require external research or provider keys:

```bash
AI_ROUTER_REQUIRE_KEYS=0 PREPUBLISH_CRITIC_REQUIRED=0 XIANGQI_RESEARCH_REQUIRED=0 \
GOOGLE_GROUNDING_ENABLED=0 GOOGLE_GROUNDING_REQUIRED=0 VISUAL_ASSET_ENABLED=0 \
YOUTUBE_PUBLISH_ENABLED=1 PYTHONPATH=python python3 -m unittest discover -s python -p 'test_*.py' -q
```

For a no-production capsule smoke, copy the database to `/tmp`, run `python/automation_orchestrator.py` with `config/automation.json`, and verify `status` plus the selected stage. Test three fixtures separately: an incomplete curriculum must select `curriculum-queue`; a completed curriculum with a fresh discovered candidate must select `post-curriculum-topic`; and a completed curriculum with discovery exhausted must select `complete-match-fallback` and produce a terminal legal game. Run Short extraction only against the generated parent artifact and verify duplicate extraction is idempotent. Do not use the live production database for exploratory smoke tests.

## 9. Known baseline issue and interpretation

The historical `python/sample_job.json` contains moves with narrative labels but no structured `claimProof`. The current director correctly rejects causal/rule language without verified Xiangqi claims. Therefore the README sample pipeline can fail on that old fixture even while the workflow-shaped contract suite passes. Do not weaken the claim contract to make the old sample pass; update the fixture with proper claim proof in a separate change if that behavior is desired.

## 10. External services and security

Secrets belong in GitHub Secrets or a local untracked `.env`: AI Router repository token and key pools, Hugging Face token, YouTube OAuth JSON, visual API key, and Google grounding key. Never put actual values in this file, JSON fixtures, capsule contracts, logs, or commits. YouTube production is controlled by `YOUTUBE_PUBLISH_ENABLED` and `YOUTUBE_PUBLISH_MODE`; use `private` during integration verification.

The capsule unit tests use temporary directories and no provider credentials. Network health checks, OAuth, YouTube upload, AI Router availability, and Remotion rendering are integration/deferred checks and must be reported separately from pure capsule correctness.

## 11. Failure patterns and recovery

| Failure | Owning layer | Recovery |
|---|---|---|
| curriculum claim conflict | `automation_runner.py` and `LocalStore` | preserve curriculum order; do not fall through to discovery |
| active or resumable publication | `automation_runner.py` and reconciliation | reconcile remote state before retry; do not create a new job |
| unsupported causal claim | `director.py` / claim contract | add verified structured claim proof or use neutral narration |
| provider/TTS failure | AI Router/TTS layer | inspect provider state and fallback evidence; do not silently accept bad audio |
| capsule stage error | config/orchestrator | use `on_error=skip` only for optional stage; otherwise fail visibly |
| duplicate derivative window | derivative capsule/state store | compare parent fingerprint, interval, reason, and child fingerprint |

## 12. Adding a new domain or capsule

Add new domain facts and rules under a domain-owned folder or adapter. Change `config/automation.json` only for stage composition and safe kwargs. To add a capability, first write a contract, then add `core.py`, adapters, fixtures, tests, and documentation under `systems/<capability>/`. Demonstrate a temporary-DB test, duplicate/restart behavior where relevant, an integration adapter test, and redaction before wiring production workflow.

## 13. Change protocol for future agents

Before editing, identify the owner layer, read the existing test, write or update a regression test, run the smallest safe check, then run the full suite and `git diff --check`. Do not change schedules, publication visibility, deletion workflows, credentials, or production databases as part of a code refactor. If a gate fails, classify it as a code failure, baseline fixture failure, missing dependency, provider failure, or external quota/auth failure before changing code.

## المراجع (References)

[1]: https://github.com/ysrg2003/chinese-cheese-video "Chinese Cheese Video repository"
[2]: https://github.com/ysrg2003/ai-provider-router "Reusable AI Provider Router"
[3]: https://docs.github.com/actions/security-guides/using-secrets-in-github-actions "GitHub Actions secrets"
[4]: https://developers.google.com/youtube/v3/guides/authentication "YouTube Data API OAuth 2.0"
