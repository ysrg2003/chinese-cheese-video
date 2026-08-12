# External AI runtime findings

## Google Gemini API

Source: https://ai.google.dev/gemini-api/docs/models

Checked on 2026-08-12. The current official model page lists stable endpoints `gemini-2.5-flash` and `gemini-2.5-flash-lite`. Gemini 2.5 Flash is described as a price-performance model for low-latency, high-volume reasoning tasks. Gemini 2.5 Flash-Lite is described as the fastest and most budget-friendly model in the 2.5 family. The same page also lists newer 3.x models, so model names should remain configurable rather than hard-coded permanently.

The official model page marks `gemini-2.0-flash` and `gemini-2.0-flash-lite` as shut down; the current project must not use them as fallbacks.

Source: https://ai.google.dev/gemini-api/docs/rate-limits

Gemini rate limits are evaluated across RPM (requests per minute), TPM (input tokens per minute), and RPD (requests per day). Limits are applied per Google Cloud project, not per API key, and RPD resets at midnight Pacific time. A 429 `RESOURCE_EXHAUSTED` response should be treated as a quota or spend-limit event and trigger backoff/circuit-breaker handling. Key rotation across keys from the same project does not bypass project-level limits; multiple projects are needed for independent project-level quotas and must be used in accordance with Google's terms.

Source: https://ai.google.dev/gemini-api/docs/changelog

The changelog confirms stable `gemini-2.5-flash` and `gemini-2.5-flash-lite` endpoints, and shows that preview endpoints can be deprecated or shut down. Production configuration should use stable IDs with environment overrides and should log model lifecycle errors.

## Architecture implications

The independent runner should use this order: `gemini-2.5-flash` across configured projects/keys, then `gemini-2.5-flash-lite` using the same ordered pool, then Hugging Face providers, then a deterministic local fallback. The manager must record provider, model, key slot, project slot, status, retry-after, error class, request id, and token usage where returned.

A key pool is a resilience mechanism, not a way to evade provider quotas. The implementation should support several Google projects, respect 429 retry guidance, apply exponential backoff and cooldowns, stop using exhausted keys until the configured reset window, and keep the next run state in the local database.
