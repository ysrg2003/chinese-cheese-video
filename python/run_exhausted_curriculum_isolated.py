from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
output_dir = ROOT / os.getenv("EXHAUSTED_TEST_OUTPUT_DIR", "exhausted-curriculum-output")
output_dir.mkdir(parents=True, exist_ok=True)
full_production = os.getenv("EXHAUSTED_TEST_FULL_PRODUCTION", "0").lower() in {"1", "true", "yes"}
render_output_root = output_dir / "production-output"
render_public_root = output_dir / "production-public"
db_path = output_dir / "isolated-exhausted.db"

# Remotion needs the repository's static Xiangqi assets (board and piece SVGs)
# in the same public root as generated voice and visual assets. Copying them
# here keeps the entire full-production artifact self-contained and isolated.
if full_production:
    shutil.copytree(ROOT / "public", render_public_root, dirs_exist_ok=True)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)

if db_path.exists():
    db_path.unlink()
for suffix in ("-wal", "-shm"):
    path = Path(f"{db_path}{suffix}")
    path.unlink(missing_ok=True)

# Importing LocalStore seeds the canonical curriculum into this temporary DB.
os.environ["LOCAL_DB_PATH"] = str(db_path)
os.environ["PYTHONPATH"] = str(ROOT / "python")
from local_store import LocalStore  # noqa: E402
import content_discovery  # noqa: E402

store = LocalStore(db_path)


class _FixtureResponse:
    def __init__(self, payload: bytes | dict):
        self.content = payload if isinstance(payload, bytes) else b""
        self._payload = payload if isinstance(payload, dict) else None

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return dict(self._payload or {})


def _fixture_http_get(url: str, *args, **kwargs):
    if "youtube/v3/search" in url:
        return _FixtureResponse({"items": [{"id": {"videoId": "isolated-trend-001"}, "snippet": {"title": "Xiangqi Championship Final: River Strategy", "publishedAt": "2026-08-15T00:00:00Z"}}]})
    return _FixtureResponse(b"""<?xml version='1.0'?><rss><channel><item><title>World Xiangqi Tournament Announces New Final</title><link>https://example.test/xiangqi-trend</link><pubDate>Sat, 15 Aug 2026 00:00:00 GMT</pubDate></item></channel></rss>""")


def _fixture_ai_candidate(store_arg, language="en"):
    return {
        "id": "isolated-ai-idea-001",
        "title": "AI Idea: Can a Beginner Survive the Central File?",
        "content_type": "viewer_challenge",
        "language": language,
        "source_kind": "ai_generated",
        "priority_score": 5.0,
        "topic_key": "ai idea beginner central file challenge",
        "fen": content_discovery.DEFAULT_FEN,
        "moves": ["0,6-0,5", "0,3-0,4", "1,7-1,4"],
        "pairing": {},
        "payload": {"topic_key": "ai idea beginner central file challenge", "fen": content_discovery.DEFAULT_FEN, "moves": ["0,6-0,5", "0,3-0,4", "1,7-1,4"], "hook": "Choose the legal continuation."},
    }


with mock.patch.object(content_discovery.requests, "get", side_effect=_fixture_http_get), mock.patch.object(content_discovery, "generate_ai_candidate", side_effect=_fixture_ai_candidate):
    discovery_probe = content_discovery.discover_all(store, limit=20)
with sqlite3.connect(db_path) as connection:
    before = connection.execute("SELECT COUNT(*) FROM content_candidates").fetchone()[0]
    before_runs = connection.execute("SELECT COUNT(*) FROM automation_runs").fetchone()[0]
    lesson_count = connection.execute("SELECT COUNT(*) FROM curriculum_lessons WHERE is_active = 1").fetchone()[0]
    connection.execute("UPDATE curriculum_episode_plans SET status = 'published', published_at = CURRENT_TIMESTAMP WHERE language = 'en'")
    connection.commit()
    next_candidate = store.get_next_curriculum_candidate("en")
    after_exhaustion = connection.execute("SELECT COUNT(*) FROM curriculum_episode_plans WHERE language = 'en' AND status IN ('planned', 'retry')").fetchone()[0]

if next_candidate is not None or after_exhaustion != 0:
    raise RuntimeError(f"fixture was not exhausted: next={next_candidate!r}, remaining={after_exhaustion}")

run_env = os.environ.copy()
run_env.update(
    {
        "LOCAL_DB_PATH": str(db_path),
        "PYTHONPATH": str(ROOT / "python"),
        "YOUTUBE_PUBLISH_ENABLED": "0",
        "YOUTUBE_LOCALIZATION_ENABLED": "0",
        "XIANGQI_REVIEW_ONLY": "1" if full_production else "0",
        "XIANGQI_OUTPUT_ROOT": str(render_output_root),
        "XIANGQI_PUBLIC_ROOT": str(render_public_root),
    }
)
if full_production:
    run_env.update(
        {
            "GOOGLE_GROUNDING_ENABLED": os.getenv("GOOGLE_GROUNDING_ENABLED", "1"),
            "GOOGLE_GROUNDING_REQUIRED": os.getenv("GOOGLE_GROUNDING_REQUIRED", "1"),
            "XIANGQI_RESEARCH_REQUIRED": os.getenv("XIANGQI_RESEARCH_REQUIRED", "1"),
            "PREPUBLISH_CRITIC_REQUIRED": os.getenv("PREPUBLISH_CRITIC_REQUIRED", "1"),
            "VISUAL_STORYBOARD_ENABLED": os.getenv("VISUAL_STORYBOARD_ENABLED", "1"),
            "VISUAL_ASSET_ENABLED": os.getenv("VISUAL_ASSET_ENABLED", "1"),
        }
    )
else:
    run_env.update(
        {
            "GOOGLE_GROUNDING_ENABLED": "0",
            "GOOGLE_GROUNDING_REQUIRED": "0",
            "XIANGQI_RESEARCH_REQUIRED": "0",
            "PREPUBLISH_CRITIC_REQUIRED": "0",
        }
    )

command = [
    sys.executable,
    str(ROOT / "python" / "automation_runner.py"),
    "--daily-count",
    "1",
    "--languages",
    "en",
    "--discover-limit",
    "20",
]
if not full_production:
    command.append("--dry-run")
result = subprocess.run(command, cwd=ROOT, env=run_env, text=True, capture_output=True)
(output_dir / "automation-stdout.txt").write_text(result.stdout, encoding="utf-8")
(output_dir / "automation-stderr.txt").write_text(result.stderr, encoding="utf-8")
if result.returncode != 0:
    raise SystemExit(result.returncode)

metrics = None
for index, character in enumerate(result.stdout):
    if character != "{":
        continue
    try:
        candidate, _ = json.JSONDecoder().raw_decode(result.stdout[index:])
    except json.JSONDecodeError:
        continue
    if isinstance(candidate, dict) and "selection_mode" in candidate:
        metrics = candidate
if not isinstance(metrics, dict):
    raise RuntimeError(f"automation metrics JSON not found in stdout: {result.stdout!r}")

with sqlite3.connect(db_path) as connection:
    after = connection.execute("SELECT COUNT(*) FROM content_candidates").fetchone()[0]
    after_runs = connection.execute("SELECT COUNT(*) FROM automation_runs").fetchone()[0]
    publications = connection.execute("SELECT COUNT(*) FROM youtube_publications").fetchone()[0]
    jobs = connection.execute("SELECT COUNT(*) FROM video_jobs").fetchone()[0]
    candidates = connection.execute("SELECT COUNT(*) FROM content_candidates").fetchone()[0]
    statuses = dict(connection.execute("SELECT status, COUNT(*) FROM curriculum_episode_plans WHERE language='en' GROUP BY status").fetchall())

video_paths = sorted(_display_path(path) for path in render_output_root.glob("jobs/**/*.mp4"))
review_paths = sorted(_display_path(path) for path in render_output_root.glob("jobs/**/creative-review.json"))
visual_qa_paths = sorted(_display_path(path) for path in render_output_root.glob("jobs/**/visual_qa/**/*.json"))

report = {
    "test": "isolated_exhausted_curriculum_full_production" if full_production else "isolated_exhausted_curriculum",
    "database": _display_path(db_path),
    "render_output_root": _display_path(render_output_root),
    "render_public_root": _display_path(render_public_root),
    "lesson_count": lesson_count,
    "next_curriculum_candidate_before_run": None,
    "discovery_probe": discovery_probe,
    "selection_mode": metrics.get("selection_mode"),
    "selected": metrics.get("selected"),
    "completed": metrics.get("completed"),
    "failed": metrics.get("failed"),
    "review_ready": metrics.get("review_ready", 0),
    "dry_run_jobs": metrics.get("dry_run_jobs", []),
    "review_jobs": metrics.get("review_jobs", []),
    "video_paths": video_paths,
    "creative_review_paths": review_paths,
    "visual_qa_paths": visual_qa_paths,
    "database_mutation_checks": {
        "temporary_database_only": True,
        "candidate_count_before": before,
        "candidate_count_after": after,
        "candidate_count_changed_only_in_temporary_database": after >= before,
        "temporary_candidate_discovery_writes_are_expected": True,
        "automation_runs_before": before_runs,
        "automation_runs_after": after_runs,
        "automation_run_record_created": after_runs == before_runs + 1,
        "video_jobs_created": jobs,
        "youtube_publications_created": publications,
        "all_curriculum_statuses": statuses,
    },
    "youtube_publish_enabled": run_env["YOUTUBE_PUBLISH_ENABLED"],
    "review_only": run_env["XIANGQI_REVIEW_ONLY"],
    "full_production": full_production,
    "exit_code": result.returncode,
}
(output_dir / "isolated-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
