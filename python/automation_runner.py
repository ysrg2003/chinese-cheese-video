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
from xiangqi_rules import validate_move_sequence
from youtube_publisher import RESUMABLE_PUBLICATION_STATUSES

ROOT = Path(__file__).resolve().parents[1]


def _output_root() -> Path:
    configured = Path(os.getenv("XIANGQI_OUTPUT_ROOT", str(ROOT / "output"))).expanduser()
    root = configured if configured.is_absolute() else ROOT / configured
    root.mkdir(parents=True, exist_ok=True)
    return root


CONTENT_ROTATION = [
    "definition", "rules", "opening", "tactics", "endgame", "advanced_puzzle",
    "full_game", "comparison", "viewer_challenge", "skill_match", "trend_breakdown",
]


def _candidate_topic_key(candidate: dict[str, Any]) -> str:
    payload = candidate.get("payload") or {}
    return normalize_topic_key(payload.get("topic_key") or candidate.get("topic_key") or candidate.get("title"))


def _curriculum_lesson_key(candidate: dict[str, Any]) -> str | None:
    payload = candidate.get("payload") or {}
    lesson_key = payload.get("curriculum_lesson_key")
    return str(lesson_key) if lesson_key else None


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
                ["0,9-0,8", "0,0-0,1", "2,6-2,5"],
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


class PermanentContentError(RuntimeError):
    """A candidate is blocked until its source payload is corrected."""


class PublicationPendingError(RuntimeError):
    """A public video exists but still needs post-upload reconciliation."""



def _validate_stored_job_or_raise(job: dict[str, Any], job_id: str) -> None:
    result = validate_move_sequence(str(job.get("fen") or ""), job.get("moves") or [])
    if not result["ok"]:
        raise PermanentContentError(f"Stored job {job_id} failed Xiangqi legal-move validation: {'; '.join(result['errors'])}")


def run_one(candidate: dict[str, Any], language: str, store: LocalStore, run_id: str) -> str:
    # Stable identity is essential: a retry must resume the same YouTube publication,
    # not create a new video with a new run timestamp.
    job_id = f"{candidate['id'][:60]}-{language}".replace("/", "-")
    review_only = os.getenv("XIANGQI_REVIEW_ONLY", "0").lower() in {"1", "true", "yes"}
    history_reader = getattr(store, "get_publication_reset_history", None)
    quarantined = history_reader(job_id) if history_reader else None
    # Full-channel deletion has already verified that the old identity is absent.
    # Individual remediation resets remain quarantined to prevent duplicate uploads.
    reset_group = str((quarantined or {}).get("reset_group") or "")
    full_channel_restart = reset_group.startswith("full_channel_restart_")
    if quarantined and not review_only and not full_channel_restart:
        raise PublicationPendingError(
            f"Public video {quarantined['original_video_id']} is quarantined for review-only replacement; "
            "ordinary production is blocked until the replacement is explicitly approved"
        )
    existing_publication = store.get_youtube_publication(job_id)
    if existing_publication and existing_publication.get("status") == "published":
        stored_job = store.get_video_job_payload(job_id)
        if stored_job:
            _validate_stored_job_or_raise(stored_job, job_id)
        return job_id
    if existing_publication and existing_publication.get("status") in RESUMABLE_PUBLICATION_STATUSES:
        status = str(existing_publication.get("status"))
        video_id = str(existing_publication.get("video_id") or "unknown")
        raise PublicationPendingError(
            f"Public video {video_id} remains in {status}; reconciliation must complete before production retry"
        )
    payload = build_input(candidate, language)
    with tempfile.NamedTemporaryFile("w", suffix=".json", dir=_output_root(), delete=False, encoding="utf-8") as handle:
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
    parser.add_argument("--reconcile-only", action="store_true", help="Do not discover or produce new content; reconciliation runs separately in the workflow.")
    return parser.parse_args()


def is_reconciliation_only(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "reconcile_only", False) or int(getattr(args, "daily_count", 0)) <= 0)


def main() -> int:
    args = parse_args()
    store = LocalStore()
    run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    store.start_run(run_id, "github-actions-daily")
    metrics: dict[str, Any] = {"run_id": run_id, "selected": 0, "completed": 0, "failed": 0}
    try:
        if is_reconciliation_only(args):
            metrics["selection_mode"] = "reconciliation_only"
            store.finish_run(run_id, "completed", metrics)
            store.checkpoint()
            print(json.dumps(metrics, ensure_ascii=False, indent=2))
            return 0
        discovery_metrics = discover_all(store, args.discover_limit)
        metrics["discovery"] = discovery_metrics
        languages = parse_csv(args.languages, ["en"])
        selection_language = "en" if "en" in languages else languages[0]
        curriculum_candidate = store.get_next_curriculum_candidate(selection_language)
        if curriculum_candidate is not None:
            if not args.dry_run:
                store.add_candidate(curriculum_candidate)
            lesson_key = _curriculum_lesson_key(curriculum_candidate)
            if lesson_key and not args.dry_run:
                store.update_curriculum_episode(lesson_key, selection_language, "queued", candidate_id=curriculum_candidate["id"])
            candidates = [curriculum_candidate]
            metrics["selection_mode"] = "curriculum"
            metrics["curriculum_lesson_key"] = lesson_key
        else:
            candidates = select_diverse_candidates(store, language=selection_language, limit=max(1, args.daily_count))
            metrics["selection_mode"] = "supplementary_discovery"
        metrics["selected"] = len(candidates)
        for candidate in candidates:
            if not args.dry_run:
                store.update_candidate(candidate["id"], "processing")
            lesson_key = _curriculum_lesson_key(candidate)
            if lesson_key and not args.dry_run:
                store.update_curriculum_episode(lesson_key, selection_language, "processing", candidate_id=candidate["id"])
            completed_jobs: list[str] = []
            try:
                if args.dry_run:
                    completed_jobs = [f"dry-run-{candidate['id']}-{language}" for language in languages]
                    metrics.setdefault("dry_run_jobs", []).extend(completed_jobs)
                    metrics["completed"] += 1
                    continue
                completed_jobs = [run_one(candidate, language, store, run_id) for language in languages]
                review_only = os.getenv("XIANGQI_REVIEW_ONLY", "0").lower() in {"1", "true", "yes"}
                if review_only:
                    # The MP4 is intentionally available for human review, but it
                    # is not a YouTube publication and must not advance the lesson.
                    store.update_candidate(candidate["id"], "blocked")
                    if lesson_key:
                        store.update_curriculum_episode(
                            lesson_key,
                            selection_language,
                            "blocked",
                            candidate_id=candidate["id"],
                            job_id=completed_jobs[0] if completed_jobs else None,
                            error_message="Review artifact generated; public replacement requires explicit approval",
                        )
                    metrics["review_ready"] = int(metrics.get("review_ready", 0)) + 1
                    metrics.setdefault("review_jobs", []).extend(completed_jobs)
                else:
                    store.update_candidate(candidate["id"], "published", ",".join(completed_jobs))
                    if lesson_key:
                        store.update_curriculum_episode(
                            lesson_key, selection_language, "published", candidate_id=candidate["id"], job_id=completed_jobs[0] if completed_jobs else None
                        )
                    metrics["completed"] += 1
            except PublicationPendingError as exc:
                # A public video already exists. Leave its curriculum entry retryable
                # for the next reconciliation pass, but do not fail the content run
                # or invoke the rendering pipeline again.
                store.update_candidate(candidate["id"], "discovered")
                if lesson_key:
                    store.update_curriculum_episode(
                        lesson_key, selection_language, "retry", candidate_id=candidate["id"], error_message=str(exc)
                    )
                metrics["deferred"] = int(metrics.get("deferred", 0)) + 1
                metrics.setdefault("pending_publications", []).append({"candidate_id": candidate["id"], "reason": str(exc)})
                print(f"Candidate deferred pending YouTube reconciliation: {candidate['id']}: {exc}", file=sys.stderr)
            except Exception as exc:
                if isinstance(exc, PermanentContentError):
                    store.update_candidate(candidate["id"], "blocked")
                    if lesson_key:
                        store.update_curriculum_episode(
                            lesson_key, selection_language, "blocked", candidate_id=candidate["id"], error_message=str(exc)
                        )
                else:
                    store.update_candidate(candidate["id"], "discovered")
                    if lesson_key:
                        store.update_curriculum_episode(
                            lesson_key, selection_language, "retry", candidate_id=candidate["id"], error_message=str(exc)
                        )
                metrics["failed"] += 1
                action = "blocked" if isinstance(exc, PermanentContentError) else "will be retried"
                print(f"Candidate failed and {action}: {candidate['id']}: {exc}", file=sys.stderr)
        deferred = int(metrics.get("deferred", 0))
        incomplete = metrics["failed"] > 0 or deferred > 0
        store.finish_run(run_id, "partial" if incomplete else "completed", metrics)
        store.checkpoint()
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        return 2 if incomplete else 0
    except Exception as exc:
        metrics["error"] = str(exc)
        store.finish_run(run_id, "failed", metrics, str(exc))
        store.checkpoint()
        raise


if __name__ == "__main__":
    raise SystemExit(main())
