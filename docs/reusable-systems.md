# Reusable System Capsules in Chinese Cheese Video

This repository is a specialized Xiangqi production system. The reusable capsules added here provide generic contracts without replacing the existing production runner or its legacy catalog schema.

## What was added

| Capsule | Responsibility | Xiangqi adapter or consumer |
|---|---|---|
| `systems/config_driven_automation/` | Loads schema-versioned stage chains, invokes entrypoints, and returns `selected` or `no_valid_candidate` envelopes | `config/automation.json` and `python/configured_automation_adapter.py` |
| `systems/durable_content_state/` | Persists reusable automation evidence, variants, lineage, and run envelopes with idempotent writes | `python/configured_automation_adapter.py` using `DurableStateStore` |
| `systems/derivative_lineage/` | Computes parent/window fingerprints, preserves parent metadata, and filters used source windows | `python/derivative_lineage.py`; a renderer or publisher can consume its outputs later |

The existing `python/automation_runner.py` remains the production owner of curriculum-first selection, discovery, self-repair, rendering, YouTube publication, and legacy SQLite tables. The new configured chain is an additive, safe integration surface. It does not silently replace the production schedule.

## Safe first smoke

Run from the repository root. This command uses a copy of the production database so the smoke cannot alter the channel catalog:

```bash
rm -rf /tmp/chinese-cheese-capsule-smoke
mkdir -p /tmp/chinese-cheese-capsule-smoke
cp data/chinese_cheese_video.db /tmp/chinese-cheese-capsule-smoke/state.db
PYTHONPATH=python:. python3 python/automation_orchestrator.py \
  --config config/automation.json \
  --db-path /tmp/chinese-cheese-capsule-smoke/state.db \
  --output /tmp/chinese-cheese-capsule-smoke/selection.json \
  --reason capsule-integration-smoke
```

Expected result is a JSON envelope with `status=selected` or `status=no_valid_candidate`, `domain=xiangqi`, and `config_path` pointing to `config/automation.json`. A selected result identifies the curriculum or discovered candidate. The smoke records one row in a namespaced table such as `reusable_automation_runs`; it does not publish, render, call TTS, or change the original database.

## Contracts and ownership

`config/automation.json` is static domain configuration. It contains the `domain_id`, ordered stages, module, entrypoint, enabled flag, error policy, and kwargs. It is not a secret file and must not contain OAuth, API keys, cookies, or production state.

`systems/durable_content_state` uses `reusable_*` SQLite tables by default. This is intentional. The legacy `python/local_store.py` owns `content_candidates`, `video_jobs`, `youtube_publications`, curriculum tables, and channel catalog tables. A direct replacement of that class would risk column and lifecycle incompatibilities, so the new capsule is composed through an adapter instead of silently taking over the old database.

`systems/derivative_lineage` is pure logic. It does not render a video, upload a Short, or call YouTube. A future derivative adapter must pass a parent payload, source window, and renderer contract, then persist the returned metadata through `DurableStateStore` after a real derivative job is accepted.

## Tests and verification

Run the following checks after changing a capsule:

```bash
npm run typecheck
PYTHONPATH=python:. python3 -m unittest discover -s python -p 'test_*.py' -q
PYTHONPATH=python:. python3 -m unittest discover -s systems -p 'test_*.py' -q
python3 -m py_compile python/*.py systems/*/*.py systems/*/tests/*.py
python3 scripts/check_system_capsules.py systems
PYTHONPATH=python python3 python/curriculum_preflight.py
```

The existing repository tests must be run with the workflow contract environment when local defaults require external research or provider keys:

```bash
AI_ROUTER_REQUIRE_KEYS=0 \
PREPUBLISH_CRITIC_REQUIRED=0 \
XIANGQI_RESEARCH_REQUIRED=0 \
GOOGLE_GROUNDING_ENABLED=0 \
GOOGLE_GROUNDING_REQUIRED=0 \
VISUAL_ASSET_ENABLED=0 \
YOUTUBE_PUBLISH_ENABLED=1 \
PYTHONPATH=python python3 -m unittest discover -s python -p 'test_*.py' -q
```

The original `python/sample_job.json` is not a reliable production smoke because its historical move narration lacks the structured Xiangqi claim proof now required by `director.py`. Use the workflow-shaped test environment and the repository's contract tests instead; do not weaken a production contract merely to make the old sample pass.

## Adding a new adapter

Create a module under `python/` that translates the Xiangqi payload to the capsule contract. The adapter owns domain-specific rules, source facts, playlist policy, and publication decisions. The capsule owns only generic identity, status, fingerprint, lineage, and error behavior. Add a fake fixture and an integration test with a temporary database before enabling the adapter in a production workflow.

Never copy `data/*.db`, `.env`, OAuth files, cookies, generated media, or provider keys into `systems/`. Keep YouTube production `private` while verifying any new integration, and record external-provider checks separately from pure capsule tests.
