from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from random import choice
from typing import Any

from director import generate_director_data, make_job, normalize_language
from local_store import LocalStore
from supabase_store import SupabaseStore
from tts import align_narration_segments_to_cues, captions_from_narration, captions_from_narration_segments, captions_from_word_cues, synthesize
from timing import finalize_timing
from youtube_publisher import publish_video
from visual_director import add_visual_storyboard, validate_visual_storyboard
from visual_assets import add_generated_visual_assets
from xiangqi_rules import validate_move_sequence

ROOT = Path(__file__).resolve().parents[1]


def sample_puzzle(language: str = "en") -> dict[str, Any]:
    language = normalize_language(language)
    return {
        "id": "local-sample",
        "title": "The Quiet Trap on the Left Wing" if language == "en" else "左翼的安静陷阱",
        "language": language,
        "fen": "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR r",
        "moves": ["0,6-0,5", "0,3-0,4", "1,7-1,4"],
        "theme": "wood",
    }


def read_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_store(args: argparse.Namespace) -> Any | None:
    if args.dry_run:
        return None
    if args.storage == "local":
        return LocalStore(args.db_path)
    if args.storage == "supabase":
        return SupabaseStore()

    # Auto mode is deliberately local-first. If Supabase is configured but its
    # schema or network is unavailable, production continues on SQLite.
    if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        try:
            candidate = SupabaseStore()
            candidate.list_puzzles()
            return candidate
        except Exception as exc:
            print(f"Supabase unavailable; using local SQLite database: {exc}")
    return LocalStore(args.db_path)


def choose_puzzle(store: Any, args: argparse.Namespace) -> dict[str, Any]:
    provided = read_json(args.input)
    if provided:
        return provided
    puzzles = store.list_puzzles() if store else []
    if puzzles:
        return choice(puzzles) if args.random else puzzles[0]
    return sample_puzzle(args.language)


def write_job_files(job: dict[str, Any], stage_dir: Path, public_dir: Path) -> None:
    stage_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(job, ensure_ascii=False, indent=2)
    (stage_dir / "job.json").write_text(payload, encoding="utf-8")
    (public_dir / "job.json").write_text(payload, encoding="utf-8")


def render_job(job: dict[str, Any], stage_dir: Path) -> Path:
    output_path = stage_dir / f"{job['id']}.mp4"
    props_path = stage_dir / "job.json"
    command = [
        "npx",
        "remotion",
        "render",
        "src/index.tsx",
        "XiangqiComposition",
        str(output_path),
        f"--props={props_path}",
        "--codec=h264",
        "--image-format=jpeg",
        "--log=warn",
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chinese Cheese Video production pipeline")
    parser.add_argument("--input", help="JSON puzzle file")
    parser.add_argument("--job-id", help="Stable job id; generated when omitted")
    parser.add_argument("--random", action="store_true", help="Choose a random active puzzle")
    parser.add_argument("--language", choices=["en", "zh"], default="en", help="Video language; English by default")
    parser.add_argument("--storage", choices=["local", "auto", "supabase"], default="local", help="Storage backend; local SQLite by default")
    parser.add_argument("--db-path", default=os.getenv("LOCAL_DB_PATH", "data/chinese_cheese_video.db"), help="SQLite path")
    parser.add_argument("--skip-tts", action="store_true", help="Skip Edge-TTS and render without audio")
    parser.add_argument("--skip-render", action="store_true", help="Stop after generating audio and data")
    parser.add_argument("--dry-run", action="store_true", help="Do not persist data, render, or call external services")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    store = build_store(args)
    puzzle = choose_puzzle(store, args)
    source_language = normalize_language(puzzle.get("language"))
    target_language = normalize_language(args.language)
    if source_language != target_language:
        for text_field in ("title", "narration", "captions"):
            puzzle.pop(text_field, None)
    puzzle["language"] = target_language
    job_id = args.job_id or f"xiangqi-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    stage_dir = ROOT / "output" / "jobs" / job_id
    public_dir = ROOT / "public" / "generated" / job_id
    publication_store = None
    if store:
        publication_store = store if hasattr(store, "get_youtube_publication") else LocalStore(args.db_path)
    existing_publication = publication_store.get_youtube_publication(job_id) if publication_store else None
    if existing_publication and existing_publication.get("status") == "published":
        stored_job = publication_store.get_video_job_payload(job_id) if publication_store and hasattr(publication_store, "get_video_job_payload") else None
        if stored_job:
            legal = validate_move_sequence(str(stored_job.get("fen") or ""), stored_job.get("moves") or [])
            if not legal["ok"]:
                raise RuntimeError("Stored published job failed Xiangqi legal-move validation: " + "; ".join(legal["errors"]))
        result = {
            "job_id": job_id,
            "status": "already_published",
            "youtube": existing_publication,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    try:
        director_data = generate_director_data(puzzle, store=store, operation=f"director:{job_id}")
        job = make_job(job_id, puzzle, director_data)
        if os.getenv("XIANGQI_PRODUCTION_FREEZE", "0").lower() in {"1", "true", "yes"}:
            raise RuntimeError(
                "Production is temporarily frozen until deterministic Xiangqi legal-move validation is enabled."
            )
        job = add_visual_storyboard(job, puzzle, store=store)
        # Generated images are optional editorial establishing shots. The
        # deterministic Xiangqi board remains available if planning, service
        # authentication, image validation, or download fails.
        job = add_generated_visual_assets(job, puzzle, stage_dir, public_dir)
        if store:
            # A JSON input may be a one-off puzzle that is not yet registered in the local catalog.
            puzzle_id = None if args.input else puzzle.get("id")
            store.create_job(job, puzzle_id=puzzle_id)

        audio_duration = None
        word_cues: list[dict[str, Any]] = []
        if args.skip_tts:
            job["audioSrc"] = ""
        else:
            generated_audio, _, word_cues = synthesize(job, stage_dir)
            public_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(generated_audio, public_dir / "voice.mp3")
            job["audioSrc"] = f"generated/{job_id}/voice.mp3"
            audio_duration = word_cues[-1]["endSec"] if word_cues else None
            if audio_duration is None:
                try:
                    probe = subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nk=1", str(generated_audio)],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    audio_duration = float(probe.stdout.strip())
                except (OSError, subprocess.CalledProcessError, ValueError):
                    audio_duration = None
            if job.get("narrationSegments"):
                # The spoken move sentence, its caption, and the board move
                # all share one audio-derived window. This prevents a full
                # narration sentence from covering later move labels.
                job["narrationSegments"] = align_narration_segments_to_cues(
                    job["narrationSegments"], word_cues, job["language"],
                    fallback_duration=float(job.get("durationInSeconds") or 0),
                )
                job["captions"] = captions_from_narration_segments(job["narrationSegments"], job["language"])
                job["captions_source"] = "move_narration_audio"
            elif word_cues:
                job["captions"] = captions_from_word_cues(word_cues, job["language"], max_units=4, max_duration=1.6)
                job["captions_source"] = "edge_tts_word_boundaries_short"
            else:
                job["captions"] = captions_from_narration(job["narration"], float(job.get("durationInSeconds") or 0), job["language"])
                job["captions_source"] = "narration_fallback"

        job = finalize_timing(
            job,
            audio_duration=audio_duration,
            requested_duration=float(puzzle["durationInSeconds"]) if puzzle.get("durationInSeconds") else None,
        )
        storyboard_errors = validate_visual_storyboard(job, audio_duration=audio_duration)
        if storyboard_errors:
            raise RuntimeError("Visual storyboard validation failed: " + "; ".join(storyboard_errors))
        write_job_files(job, stage_dir, public_dir)
        result: dict[str, Any] = {"job": job, "stage_dir": str(stage_dir)}

        if not args.skip_render and not args.dry_run:
            output_path = render_job(job, stage_dir)
            result["video_path"] = str(output_path)
            if store:
                video_url = store.upload("xiangqi-videos", f"jobs/{job_id}.mp4", output_path, "video/mp4")
                store.update_job(job_id, "completed", output_url=video_url, output_payload=result)
                result["video_url"] = video_url

            publication: dict[str, Any] = {"status": "rendered", "metadata": {}}
            if publication_store and os.getenv("YOUTUBE_PUBLISH_ENABLED", "0").lower() in {"1", "true", "yes"}:
                content_type = str(job.get("content_type") or "definition")
                publication_store.upsert_youtube_publication(
                    job_id,
                    job["language"],
                    content_type,
                    "publishing",
                    metadata={"job_id": job_id, "title": job.get("title")},
                )
                try:
                    publication = publish_video(
                        output_path,
                        job,
                        existing_publication=existing_publication,
                        localization_dir=stage_dir / "localization",
                    )
                    result["youtube"] = publication
                    publication_store.upsert_youtube_publication(
                        job_id,
                        job["language"],
                        content_type,
                        publication.get("status", "failed"),
                        video_id=publication.get("video_id"),
                        video_url=publication.get("video_url"),
                        playlist_id=publication.get("playlist_id"),
                        playlist_url=publication.get("playlist_url"),
                        metadata=publication.get("metadata", {}),
                        error_message=publication.get("error_message"),
                    )
                    publication_store.upsert_youtube_catalog(
                        job,
                        publication,
                        audio_path=stage_dir / "voice.mp3",
                        video_path=output_path,
                    )
                    if publication.get("status") != "published":
                        raise RuntimeError(publication.get("error_message") or "YouTube playlist association is pending")
                except Exception as publish_exc:
                    publication_store.upsert_youtube_publication(
                        job_id,
                        job["language"],
                        content_type,
                        "failed",
                        video_id=publication.get("video_id"),
                        video_url=publication.get("video_url"),
                        playlist_id=publication.get("playlist_id"),
                        playlist_url=publication.get("playlist_url"),
                        metadata=publication.get("metadata", {"job_id": job_id, "title": job.get("title")}),
                        error_message=str(publish_exc),
                    )
                    publication["status"] = "failed"
                    publication["error_message"] = str(publish_exc)
                    publication_store.upsert_youtube_catalog(
                        job,
                        publication,
                        audio_path=stage_dir / "voice.mp3",
                        video_path=output_path,
                    )
                    raise
            elif publication_store:
                publication_store.upsert_youtube_catalog(
                    job,
                    publication,
                    audio_path=stage_dir / "voice.mp3",
                    video_path=output_path,
                )
        elif store:
            store.update_job(job_id, "ready_for_render", output_payload=result)

        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        if store:
            try:
                store.update_job(job_id, "failed", error_message=str(exc))
            except Exception as update_exc:
                print(f"Unable to mark job failed: {update_exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
