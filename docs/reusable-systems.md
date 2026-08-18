# Reusable System Capsules in Chinese Cheese Video

This repository now uses the extracted reusable capsules through **Xiangqi-specific adapters**. The integration keeps the legacy catalog and publication lifecycle as the production owner, while the configured chain, post-curriculum generation, complete-game fallback, and derivative lineage are connected to `automation_runner.py` behind explicit configuration.

## Integrated architecture

| Layer | Responsibility | Xiangqi integration point |
|---|---|---|
| `systems/config_driven_automation/` | Loads schema-versioned stage chains, invokes entrypoints, and stops at the first `selected` result | `config/automation.json`, `python/automation_orchestrator.py`, workflow input `automation_config` |
| `systems/durable_content_state/` | Persists variants, Shorts lineage, generation cursor, and automation evidence with idempotent writes | `python/configured_automation_adapter.py`, `python/continuous_topic_generator.py`, `python/complete_match_generator.py`, `python/short_highlight_generator.py` |
| `systems/derivative_lineage/` | Computes parent/window fingerprints, preserves parent metadata, and filters used source windows | `python/short_highlight_generator.py` after a completed parent job |
| `python/continuous_topic_generator.py` | Enforces the curriculum gate, filters duplicates, optionally calls existing Xiangqi discovery, and records cursor state | `post-curriculum-topic` stage |
| `python/complete_match_generator.py` | Generates deterministic legal playouts from standard Xiangqi FEN, requires terminal checkmate/stalemate, and records a full-game candidate | `complete-match-fallback` stage |
| `python/short_highlight_generator.py` | Produces bounded derivative Short descriptors and parent/source-window lineage | `XIANGQI_SHORTS_ENABLED=1` or workflow input `shorts_enabled=true` |

## Configured Xiangqi chain

`config/automation.json` is the domain-owned composition file. Its order is deliberate:

1. `curriculum-queue` calls `configured_automation_adapter.select_job` and preserves the authoritative 72-lesson order.
2. `post-curriculum-topic` activates only when `LocalStore.curriculum_gate()` reports that every active curriculum episode is published. It filters published topic keys and move signatures, then uses the existing discovery layer when enabled.
3. `complete-match-fallback` runs only after the previous stages return `no_candidate`. It selects a profile from `config/xiangqi_complete_match_profiles.json`, generates a deterministic legal playout, validates the entire sequence through `xiangqi_rules.validate_move_sequence`, and requires a terminal checkmate or stalemate plus the profile minimum ply count.

The generic orchestrator stops at `selected`. The configured path is opt-in through `--automation-config config/automation.json` or the workflow input `automation_config`. `--automation-only` and `automation_only=true` stop before candidate claims, rendering, publication, or curriculum advancement.

## Post-curriculum and full-game behavior

Before the 72-lesson curriculum is complete, the configured chain can select only the next runnable curriculum episode. It cannot select a discovery topic or generate a fallback match. After completion, it first uses a fresh discovered Xiangqi topic. If no fresh candidate remains, the complete-match adapter creates a full parent job whose moves start from the standard position and end at a validated terminal state. The selected profile, seed, terminal reason, ply count, and content fingerprint are recorded in the job and in `reusable_content_variants`.

The current legacy `LocalStore` remains the owner of `content_candidates`, `video_jobs`, curriculum claims, YouTube publications, and channel catalog tables. The durable capsule adds only namespaced `reusable_content_variants`, `reusable_short_lineage`, `reusable_automation_runs`, and `reusable_generation_state`. This avoids silently replacing Xiangqi-specific schema or reconciliation behavior.

## Derivative Short behavior

After a real parent job has completed, `short_highlight_generator.extract_highlights()` reads the parent job artifact, selects bounded tactical or decision windows, copies parent metadata, and writes descriptors below `output/shorts/<parent-job-id>/`. Each child has a parent fingerprint, source interval, reason, and child fingerprint. The same extraction is idempotent: already-recorded windows are not generated again.

The extractor records lineage and variant evidence but does not render or upload by itself. A future renderer/publisher adapter must consume the child descriptor and pass its own acceptance state before a publication state transition. YouTube remains `private` during integration and the configured workflow smoke path never uploads.

## Safe chain smoke

Run from the repository root and use a copy of the production database:

```bash
rm -rf /tmp/chinese-cheese-chain-smoke
mkdir -p /tmp/chinese-cheese-chain-smoke
cp data/chinese_cheese_video.db /tmp/chinese-cheese-chain-smoke/state.db
LOCAL_DB_PATH=/tmp/chinese-cheese-chain-smoke/state.db XIANGQI_OUTPUT_ROOT=/tmp/chinese-cheese-chain-smoke/output \
PYTHONPATH=python:. python3 python/automation_runner.py \
  --automation-config config/automation.json \
  --automation-only \
  --daily-count 1 \
  --languages en \
  --discover-limit 20
```

For deterministic stage coverage, use separate temporary copies. An incomplete curriculum must select `curriculum-queue`. A completed curriculum with a fresh discovered candidate must select `post-curriculum-topic`. A completed curriculum with discovery candidates removed must select `complete-match-fallback` and produce a terminal legal parent game. Run Short extraction against that generated parent artifact twice; the first call should generate lineage rows and the second should return `no_candidate` without duplicates.

## Verification commands

```bash
npm run typecheck
python3 -m py_compile python/*.py systems/*/*.py systems/*/tests/*.py
PYTHONPATH=python:. python3 -m unittest discover -s python -p 'test_*.py' -q
PYTHONPATH=python:. python3 -m unittest discover -s systems -p 'test_*.py' -q
python3 scripts/check_system_capsules.py systems
PYTHONPATH=python python3 python/curriculum_preflight.py
```

The Python suite must use the workflow contract environment when local defaults require external research or provider keys. The historical `python/sample_job.json` remains a baseline fixture with missing structured `claimProof`; its rejection by the director is expected and must not be hidden by weakening the claims contract.

## Ownership and portability rules

Domain adapters own Xiangqi rules, curriculum facts, discovery policy, profile data, playlist policy, and publication decisions. Capsules own generic identity, status, fingerprint, lineage, restart behavior, and error contracts. Do not add Xiangqi rules, source facts, OAuth, cookies, or provider calls to `systems/*/core.py`.

Never copy `data/*.db`, `.env`, OAuth files, cookies, generated media, or provider keys into `systems/`. Keep the production visibility `private` while verifying the integration, and report external-provider checks separately from pure capsule correctness.
