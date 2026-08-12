# AI usage per video

## What is counted?

Chinese Cheese Video records every AI Router attempt in the SQLite database configured by `AI_ROUTER_STATE_DB`. A successful call and a failed fallback attempt are both counted. The record contains the operation, provider, model, safe key identifier, status, error class, HTTP status when available, timestamp, and provider usage metadata. It never stores the API key value.

Since the pipeline passes `operation=director:<job_id>`, you can report one video exactly:

```bash
python3 python/report_ai_usage.py \
  --db data/ai_router.db \
  --job-id live-ai-video-en
```

The report includes:

| Field | Meaning |
| --- | --- |
| `attempts` | Number of provider/model/key attempts for the video |
| `successes` | Successful AI responses |
| `failures` | Failed attempts before success or final failure |
| `models` | Count per model |
| `key_ids` | Count per safe key identifier, never the key value |
| `usage_totals` | Provider token fields when the provider returned them |
| `records` | The ordered attempt-by-attempt audit trail |

## Consumption in the current default configuration

The normal video path asks the director for one structured content response per language. A video rendered in English therefore consumes at least one successful AI request. A Chinese version consumes another independent request. The English and Chinese outputs do not reuse the other language's response because titles, narration, captions, and timing are generated for the selected language.

The daily automation path also runs discovery before selecting a candidate. If Gemini or Hugging Face is enabled, `generate_ai_candidate()` can make one `idea_generation` request per daily run, even before the selected video is sent to the director. That discovery request is not attached to a video job; it is tracked separately by operation `idea_generation`.

For `daily_count=1` and `languages=en,zh`, the minimum successful request count is therefore:

| Stage | Minimum requests |
| --- | ---: |
| AI idea discovery | 1, if the AI discovery path is enabled |
| English director | 1 |
| Chinese director | 1 |
| **Total for the daily run** | **3** |

If only one language is requested, remove the other director request. If discovery is disabled or the deterministic candidate generators are used, remove the discovery request.

## Maximum attempts with the current default chain

The current default chain contains two Gemini models and ten Hugging Face models. With nine Gemini keys and one Hugging Face token, the theoretical provider/model/key attempt space is:

```text
2 Gemini models × 9 Gemini keys = 18 attempts
10 Hugging Face models × 1 HF token = 10 attempts
Total = 28 attempts for one director request
```

The AI Router policy now sets `max_attempts=64`, so it can reach all 28 combinations and still leave room for additional keys or models. It does not automatically use every key when an earlier attempt succeeds. In the successful live tests, each direct Gemini, Flash-Lite, and Hugging Face request used one key and one attempt.

If you configure multiple Hugging Face tokens, multiply the ten Hugging Face model entries by the number of enabled tokens. Keep `max_attempts` high enough to cover the resulting combinations.

## Why a failed key can still be recorded

A 401 or 403 attempt is recorded as `auth` and the key is cooled down. A 429 attempt is recorded as `quota` and cooled down according to `config/policies.json`. A timeout or 5xx error is recorded as `transient` and may be retried according to the backoff policy. An invalid JSON response is recorded as `invalid_or_unknown` and the router moves to the next configured combination.

These are provider attempts, not a promise of token cost. Actual billing or quota accounting depends on the external provider's current plan and policy; use the usage metadata and provider dashboard for the authoritative token and cost record.
