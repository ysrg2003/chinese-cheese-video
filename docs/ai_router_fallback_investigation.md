# AI Router Fallback Investigation

## Incident

Workflow run `31669851544` published `A Short History of Xiangqi` with `visualStoryboardSource=fallback`. The expected behavior is to call the independent AI Provider Router first and use the deterministic fallback only after the configured provider/model/key chain has been exhausted or the returned JSON fails validation.

## Evidence from the saved workflow artifact

The workflow environment contained a masked `AI_ROUTER_GEMINI_KEYS_JSON` value and a masked `HF_TOKEN` value. `AI_ROUTER_HF_KEYS_JSON` was empty, so the router fell back to the single legacy `HF_TOKEN` environment value. The saved `ai_router.db` contained ten failed Hugging Face calls for the `director` operation, covering the ten configured Hugging Face models. Every failure was HTTP 401 with `Invalid username or password.`. No Gemini provider state was recorded, and no `visual_director:<lesson_key>` operation was recorded. Therefore, the artifact proves that the router did perform ordered Hugging Face model fallback for the director, but it does not prove that Gemini was loaded or that the storyboard request reached a usable Gemini key in that run. Future workflow artifacts must show the dedicated `visual_director:<lesson_key>` operation separately from the narration director operation; its absence is a diagnostic signal, not evidence of successful storyboard generation.

## Router contract

The configured default chain remains ordered as follows: `gemini-2.5-flash`, `gemini-2.5-flash-lite`, then the ten Hugging Face models. For every model, the router iterates through the loaded keys in order, skips keys still cooling down, records each failure, and continues to the next key/model. The deterministic visual fallback is allowed only after this chain fails or produces an invalid storyboard.

## Fixes

The AI Provider Router now accepts the documented JSON array and common wrapper forms such as `{"keys":[...]}`, `{"items":[...]}`, and `{"entries":[...]}`. Each entry accepts `key`, `api_key`, `token`, `secret`, or `value`, while preserving `id`, project metadata, and order. The change is in router commit `7196eb3`.

The Chinese Cheese Video workflow now runs `python python/validate_ai_router_runtime.py` before production. It prints only provider key counts and the ordered model chain. With `AI_ROUTER_REQUIRE_KEYS=1`, it fails before rendering or publishing if either the Gemini or Hugging Face pool is empty. This prevents a misleading successful public video when the intended AI providers were not loaded. The change is in Chinese Cheese Video commit `a18fd38`.

The expected GitHub Secret shape for Gemini is a JSON array such as:

```json
[
  {"id":"gemini-1","key":"AIza...","project":"project-a"},
  {"id":"gemini-2","key":"AIza...","project":"project-a"}
]
```

The Hugging Face pool may be an array in `AI_ROUTER_HF_KEYS_JSON` or a single valid access token in `HF_TOKEN`. The production repository now stores a two-entry ordered pool in `AI_ROUTER_HF_KEYS_JSON`; the legacy `HF_TOKEN` remains only as compatibility fallback. Secret values must never be committed, written to artifacts, or copied into documentation. The token used in the incident returned HTTP 401 and must be rotated and replaced before expecting a successful Hugging Face fallback.

## Visual-fallback hardening

A provider outage is not allowed to produce a passive history or definition lesson. The deterministic fallback now opens such lessons with a board overview, reacts to named concepts such as armies, river/palaces, cannon geometry, coordinates, rules, and pieces, and ends a learning transition with a roadmap. Generic unnamed history beats may use a timeline or cultural-heritage overlay. The validation gate blocks the retired `What Changes Next` headline and adjacent repeated static fallback kinds before render or publication.

## Verification

The AI Router suite covers ordered rotation and wrapper/API-key alias parsing. The Chinese Cheese Video suite now includes dedicated history and board-definition fallback cases in addition to move-storyboard validation. TypeScript is checked directly with the local compiler, and the workflow preflight verifies key-pool presence without exposing secret values. A real workflow run remains the final operational confirmation because only GitHub Actions receives the encrypted repository secrets.
