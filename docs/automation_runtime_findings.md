# Automation runtime findings

## GitHub Actions

Sources:
- https://docs.github.com/actions/using-workflows/events-that-trigger-workflows
- https://docs.github.com/actions/writing-workflows/choosing-what-your-workflow-does/control-the-concurrency-of-workflows-and-jobs
- https://docs.github.com/en/actions/tutorials/store-and-share-data

Scheduled workflows are supported through the `schedule` event. A production workflow should define one schedule in UTC, allow manual dispatch, and avoid assuming the job will start at the exact minute. A repository-level concurrency group can ensure only one content-production run is active at a time; the default queue behavior keeps at most one pending run, while `cancel-in-progress` should not be used for a production render because cancelling a running render can lose a partially completed job.

Workflow artifacts can persist MP4 files, logs, and state snapshots after a run. Artifacts are immutable in the current action version, so each run should use a unique artifact name. For a long-lived SQLite catalog, the workflow should download the previous database from a durable external store or commit a controlled state file back to the repository. GitHub artifacts alone are not a convenient database for the next independent scheduled run.

## Hugging Face Inference Providers

Source: https://huggingface.co/docs/inference-providers/en/index

Hugging Face Inference Providers exposes a unified interface to multiple providers. The OpenAI-compatible endpoint is `https://router.huggingface.co/v1`, authenticated with `HF_TOKEN`. Provider selection can be automatic (`:fastest`), cost-oriented (`:cheapest`), preference-based (`:preferred`), or explicit. The system will use an explicit ordered model/provider list and record which provider served each request.

Hugging Face is a fallback for text planning and idea generation only. It is not assumed to be a guaranteed free quota or a permanent provider; the runner handles 401, 402, 429, 5xx, timeouts, and unavailable-model errors and moves to the next fallback.

## Architecture implication

The scheduled job should use a single `content-runner` command with a persistent state artifact. The sequence is: restore state, discover candidates, fingerprint and deduplicate, generate the next content plan, call the provider manager, validate output, render the video, upload the video and metadata, save a new state snapshot, and upload artifacts. The job must be idempotent and resume-safe so a retry cannot create duplicate content.
