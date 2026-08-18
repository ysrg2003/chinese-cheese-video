# Reusable Systems Integration Record

## Scope

This change adds the reusable system capsules extracted from the generalized framework to `chinese-cheese-video`, while preserving the existing Xiangqi production path. The integration is intentionally additive: `python/automation_runner.py` remains the owner of curriculum-first production, discovery, self-repair, rendering, YouTube publication, and legacy state transitions.

## Why the integration is adapter-first

The Xiangqi repository predates the generic framework and owns a different SQLite schema. Its `content_candidates` table does not have the same columns as the newer generic framework table, and its `LocalStore.add_candidate` has legacy fingerprint/insert semantics. Replacing `python/local_store.py` with the newer generic implementation would risk curriculum claims, publication reconciliation, provider state, and YouTube catalog behavior.

For that reason, `systems/durable_content_state` uses namespaced tables named `reusable_content_variants`, `reusable_short_lineage`, and `reusable_automation_runs`. The existing LocalStore remains the owner of production tables. `python/configured_automation_adapter.py` composes the two layers: it asks the old LocalStore for the authoritative curriculum/discovery candidate and records only generic automation evidence through the capsule.

## Integrated paths

| Path | Role |
|---|---|
| `systems/config_driven_automation/` | Generic config loader and ordered stage orchestrator |
| `systems/durable_content_state/` | Namespaced variant, lineage, and automation-run state |
| `systems/derivative_lineage/` | Pure parent/window fingerprint and metadata-preservation logic |
| `config/automation.json` | Xiangqi domain-owned worked example for the generic chain |
| `python/configured_automation_adapter.py` | Adapter from Xiangqi LocalStore/curriculum to generic stage result |
| `python/automation_config.py` | Compatibility CLI facade for config validation |
| `python/automation_orchestrator.py` | Compatibility CLI facade for configured chain execution |
| `python/derivative_lineage.py` | Compatibility facade for pure derivative functions |
| `docs/reusable-systems.md` | Beginner and maintainer instructions |
| `AI_CONTEXT.md` | Engineering context and ownership boundaries |

## Verification record

The baseline environment initially lacked `node_modules`, so `npm ci` was run from the lockfile before TypeScript verification. After that installation, `npm run typecheck`, Python compilation, and curriculum preflight passed. The workflow-shaped Python suite passed **178 tests**. The capsule suite passed **5 tests**, and `check_system_capsules.py` returned `status=ok` for all three capsules.

The final configured-chain smoke used a copy of `data/chinese_cheese_video.db` under `/tmp/chinese-cheese-final-smoke`. It selected `curriculum-en-020-keep-general-safe` through stage `curriculum-or-discovery`, returned `status=selected`, and persisted the result in a `reusable_automation_runs` table in the temporary copy. A query against the original production database confirmed that no `reusable_*` table had been created by the smoke, proving that the live database was not modified.

The final verification commands were:

```bash
npm run typecheck
python3 -m py_compile python/*.py systems/*/*.py systems/*/tests/*.py
AI_ROUTER_REQUIRE_KEYS=0 PREPUBLISH_CRITIC_REQUIRED=0 XIANGQI_RESEARCH_REQUIRED=0 \
GOOGLE_GROUNDING_ENABLED=0 GOOGLE_GROUNDING_REQUIRED=0 VISUAL_ASSET_ENABLED=0 \
YOUTUBE_PUBLISH_ENABLED=1 PYTHONPATH=python python3 -m unittest discover -s python -p 'test_*.py' -q
PYTHONPATH=python:. python3 -m unittest discover -s systems -p 'test_*.py' -q
PYTHONPATH=python python3 python/curriculum_preflight.py
python3 scripts/check_system_capsules.py systems
```

## Baseline observations that were not caused by this integration

The first baseline test attempt without the workflow contract environment failed three Xiangqi rule tests because `XIANGQI_RESEARCH_REQUIRED` defaults to enabled locally. Re-running with the same controlled variables used by the workflow passed all 178 tests.

The historical `python/sample_job.json` still fails the safe pipeline smoke because its three moves use causal/rule narration without structured `claimProof`; the current director correctly raises `ValueError: causal/rule language requires structured Xiangqi claims`. This pre-existing fixture issue is documented in `README.md` and `AI_CONTEXT.md` and was not weakened or hidden by the capsule integration.

The baseline and final suite logs also contain mocked publication/reconciliation reports for quota, OAuth, and provider failures. They are test evidence and do not mean that this integration performed a YouTube upload. No production upload, TTS call, Remotion render, or destructive workflow was run as part of this change.

## Security boundary

No secret, OAuth token, cookie, production database, generated media, or private credential was added to `systems/`, fixtures, documentation, or the commit. YouTube publication remains controlled by the existing workflow variables; integration smoke is selection-only and does not publish.
