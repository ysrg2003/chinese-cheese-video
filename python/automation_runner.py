from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_discovery import discover_all
from local_store import LocalStore

ROOT = Path(__file__).resolve().parents[1]


def parse_csv(value: str, default: list[str]) -> list[str]:
    values = [item.strip() for item in (value or "").split(",") if item.strip()]
    return values or default


def build_input(candidate: dict[str, Any], language: str) -> dict[str, Any]:
    payload = dict(candidate.get("payload") or {})
    payload.update(
        {
            "id": candidate["id"],
            "title": candidate["title"] if language == "en" else payload.get("title_zh", candidate["title"]),
            "language": language,
            "content_type": candidate["content_type"],
            "source_url": candidate.get("source_url"),
            "source_kind": candidate.get("source_kind"),
        }
    )
    return payload


def run_one(candidate: dict[str, Any], language: str, store: LocalStore, run_id: str) -> str:
    # Stable identity is essential: a retry must resume the same YouTube publication,
    # not create a new video with a new run timestamp.
    job_id = f"{candidate['id'][:60]}-{language}".replace("/", "-")
    existing_publication = store.get_youtube_publication(job_id)
    if existing_publication and existing_publication.get("status") == "published":
        return job_id
    payload = build_input(candidate, language)
    with tempfile.NamedTemporaryFile("w", suffix=".json", dir=ROOT / "output", delete=False, encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        input_path = Path(handle.name)
    try:
        command = [
            sys.executable,
            str(ROOT / "python" / "run_pipeline.py"),
            "--input",
            str(input_path),
            "--language",
            language,
            "--storage",
            "local",
            "--job-id",
            job_id,
        ]
        subprocess.run(command, cwd=ROOT, check=True)
        if os.getenv("YOUTUBE_PUBLISH_ENABLED", "0").lower() in {"1", "true", "yes"}:
            publication = store.get_youtube_publication(job_id)
            if not publication or publication.get("status") != "published":
                error = (publication or {}).get("error_message") or "YouTube publication did not reach published state"
                raise RuntimeError(error)
        return job_id
    finally:
        input_path.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unattended daily Chinese Cheese Video content runner")
    parser.add_argument("--daily-count", type=int, default=int(os.getenv("DAILY_CONTENT_COUNT", "1")))
    parser.add_argument("--languages", default=os.getenv("AUTOMATION_LANGUAGES", "en,zh"))
    parser.add_argument("--discover-limit", type=int, default=int(os.getenv("DISCOVERY_LIMIT", "20")))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    store = LocalStore()
    run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    store.start_run(run_id, "github-actions-daily")
    metrics: dict[str, Any] = {"run_id": run_id, "selected": 0, "completed": 0, "failed": 0}
    try:
        discovery_metrics = discover_all(store, args.discover_limit)
        metrics["discovery"] = discovery_metrics
        candidates = store.list_candidates(status="discovered", limit=max(1, args.daily_count))
        languages = parse_csv(args.languages, ["en", "zh"])
        metrics["selected"] = len(candidates)
        for candidate in candidates:
            store.update_candidate(candidate["id"], "processing")
            completed_jobs: list[str] = []
            try:
                if args.dry_run:
                    completed_jobs = [f"dry-run-{candidate['id']}-{language}" for language in languages]
                else:
                    completed_jobs = [run_one(candidate, language, store, run_id) for language in languages]
                store.update_candidate(candidate["id"], "published", ",".join(completed_jobs))
                metrics["completed"] += 1
            except Exception as exc:
                store.update_candidate(candidate["id"], "discovered")
                metrics["failed"] += 1
                print(f"Candidate failed and will be retried: {candidate['id']}: {exc}", file=sys.stderr)
        store.finish_run(run_id, "completed" if metrics["failed"] == 0 else "partial", metrics)
        store.checkpoint()
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        return 0 if metrics["failed"] == 0 else 2
    except Exception as exc:
        metrics["error"] = str(exc)
        store.finish_run(run_id, "failed", metrics, str(exc))
        store.checkpoint()
        raise


if __name__ == "__main__":
    raise SystemExit(main())
