from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_discovery import discover_all
from local_store import LocalStore, normalize_topic_key

ROOT = Path(__file__).resolve().parents[1]

CONTENT_ROTATION = [
    "definition", "rules", "opening", "tactics", "endgame", "advanced_puzzle",
    "full_game", "comparison", "viewer_challenge", "skill_match", "trend_breakdown",
]


def _candidate_topic_key(candidate: dict[str, Any]) -> str:
    payload = candidate.get("payload") or {}
    return normalize_topic_key(payload.get("topic_key") or candidate.get("topic_key") or candidate.get("title"))


def select_diverse_candidates(store: LocalStore, *, language: str, limit: int) -> list[dict[str, Any]]:
    """Choose fresh topics while rotating the channel's content program."""
    pool = [candidate for candidate in store.list_candidates(status="discovered", limit=500) if candidate.get("language") == language]
    published_topics = store.get_published_topic_keys(language)
    published_moves = store.get_published_move_signatures(language)
    recent_types = store.get_recent_content_types(language, limit=6)
    enriched_pool: list[dict[str, Any]] = []
    for candidate in pool:
        payload = dict(candidate.get("payload") or {})
        topic_key = _candidate_topic_key(candidate)
        payload.setdefault("topic_key", topic_key)
        supplied_moves = payload.get("moves") or []
        # Legacy candidates all carried the same three demo moves. Derive a
        # stable variant from their topic before comparing them with history.
        if supplied_moves == ["0,6-0,5", "0,3-0,4", "1,7-1,4"]:
            variant_index = int(hashlib.sha256(topic_key.encode("utf-8")).hexdigest()[:8], 16) % 5
            variants = [
                ["0,6-0,5", "0,3-0,4", "1,7-1,4"],
                ["1,9-2,7", "1,0-2,2", "1,7-1,4"],
                ["1,7-1,4", "2,3-2,4", "7,9-6,7"],
                ["0,9-0,5", "0,0-0,4", "2,6-2,5"],
                ["3,9-4,8", "3,0-4,1", "7,7-7,4"],
            ]
            payload["moves"] = variants[variant_index]
        enriched = dict(candidate)
        enriched["payload"] = payload
        enriched["topic_key"] = topic_key
        enriched_pool.append(enriched)
    available = []
    for candidate in enriched_pool:
        if _candidate_topic_key(candidate) in published_topics:
            continue
        payload = candidate.get("payload") or {}
        signature = json.dumps({"fen": payload.get("fen"), "moves": payload.get("moves") or []}, ensure_ascii=False, sort_keys=True)
        if signature in published_moves:
            continue
        available.append(candidate)
    if not available:
        return []

    def rank(candidate: dict[str, Any]) -> tuple[float, float]:
        content_type = str(candidate.get("content_type") or "")
        priority = float(candidate.get("priority_score") or 0)
        rotation_index = CONTENT_ROTATION.index(content_type) if content_type in CONTENT_ROTATION else len(CONTENT_ROTATION)
        recent_penalty = 8.0 if content_type in recent_types[:3] else 0.0
        trend_penalty = 6.0 if content_type == "trend_breakdown" and recent_types[:2].count("trend_breakdown") else 0.0
        return (priority - recent_penalty - trend_penalty, -float(rotation_index))

    # First select the highest-priority candidate from the next content type in
    # the channel plan. If that type is unavailable, rank all fresh candidates
    # while still penalizing consecutive repeats.
    for content_type in CONTENT_ROTATION:
        if content_type in recent_types[:4]:
            continue
        candidates = [candidate for candidate in available if candidate.get("content_type") == content_type]
        if candidates:
            candidates.sort(key=rank, reverse=True)
            selected = candidates[:1]
            break
    else:
        selected = sorted(available, key=rank, reverse=True)[:1]

    # For runs requesting more than one item, add only a different topic/type
    # and a different board sequence within the same batch.
    def move_signature(candidate: dict[str, Any]) -> str:
        payload = candidate.get("payload") or {}
        return json.dumps({"fen": payload.get("fen"), "moves": payload.get("moves") or []}, ensure_ascii=False, sort_keys=True)

    remaining = [candidate for candidate in available if candidate["id"] not in {item["id"] for item in selected}]
    while len(selected) < limit and remaining:
        used_types = {str(item.get("content_type") or "") for item in selected}
        used_moves = {move_signature(item) for item in selected}
        candidates = [candidate for candidate in remaining if candidate.get("content_type") not in used_types and move_signature(candidate) not in used_moves]
        if not candidates:
            candidates = [candidate for candidate in remaining if move_signature(candidate) not in used_moves] or remaining
        candidate = sorted(candidates, key=rank, reverse=True)[0]
        selected.append(candidate)
        remaining = [item for item in remaining if item["id"] != candidate["id"]]
    return selected


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
            "topic_key": candidate.get("topic_key") or payload.get("topic_key"),
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
        languages = parse_csv(args.languages, ["en"])
        selection_language = "en" if "en" in languages else languages[0]
        candidates = select_diverse_candidates(store, language=selection_language, limit=max(1, args.daily_count))
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
