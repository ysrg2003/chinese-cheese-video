from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from automation_orchestrator import run_automation
from complete_match_generator import generate_complete_match
from director import generate_director_data, make_job
from local_store import LocalStore
from short_highlight_generator import extract_highlights
from timing import finalize_timing
from visual_director import add_visual_storyboard, validate_visual_storyboard

ROOT = Path(__file__).resolve().parents[1]


class XiangqiAutomationCapsuleTests(unittest.TestCase):
    def _db(self, directory: str) -> Path:
        path = Path(directory) / "xiangqi.db"
        LocalStore(path)
        return path

    def _complete(self, path: Path) -> None:
        with sqlite3.connect(path) as db:
            db.execute("UPDATE curriculum_episode_plans SET status='published', published_at=CURRENT_TIMESTAMP, error_message=NULL")

    def test_configured_chain_preserves_curriculum_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._db(directory)
            result = run_automation(config_path=ROOT / "config" / "automation.json", db_path=path, output_path=Path(directory) / "selection.json")
            self.assertEqual(result["status"], "selected")
            self.assertEqual(result["stage"], "curriculum-queue")
            self.assertEqual(result["selection"]["source"], "curriculum")

    def test_complete_match_fallback_is_terminal_and_legal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._db(directory)
            self._complete(path)
            with sqlite3.connect(path) as db:
                db.execute("DELETE FROM content_candidates WHERE status='discovered'")
            result = generate_complete_match(db_path=path, output_path=Path(directory) / "match.json", profile_id="cannon-and-rook")
            self.assertEqual(result["status"], "selected")
            self.assertIn(result["end_reason"], {"checkmate", "stalemate"})
            self.assertGreaterEqual(result["plies"], 70)
            job = json.loads(Path(result["input"]).read_text(encoding="utf-8"))
            self.assertEqual(job["content_type"], "full_game")
            self.assertEqual(len(job["moves"]), result["plies"])
            self.assertEqual(job["visual_mode"], "storyboard")
            self.assertGreaterEqual(job["durationInSeconds"], 120)
            self.assertTrue(all(move.get("claims") for move in job["moves"]))

    def test_complete_match_job_passes_director_and_storyboard_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._db(directory)
            self._complete(path)
            with sqlite3.connect(path) as db:
                db.execute("DELETE FROM content_candidates WHERE status='discovered'")
            result = generate_complete_match(db_path=path, output_path=Path(directory) / "match.json", profile_id="river-crossing")
            puzzle = json.loads(Path(result["input"]).read_text(encoding="utf-8"))
            with patch.dict(os.environ, {"XIANGQI_RESEARCH_REQUIRED": "0", "YOUTUBE_PUBLISH_ENABLED": "0"}, clear=False):
                director_data = generate_director_data(puzzle)
                job = make_job("pipeline-ready-full-game", puzzle, director_data)
            job = add_visual_storyboard(job, puzzle)
            job = finalize_timing(job, requested_duration=float(puzzle["durationInSeconds"]))
            self.assertEqual(validate_visual_storyboard(job), [])
            self.assertTrue(job["claimProof"]["ok"])

    def test_short_lineage_is_parent_preserving_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._db(directory)
            self._complete(path)
            result = generate_complete_match(db_path=path, output_path=Path(directory) / "match.json", profile_id="river-crossing")
            first = extract_highlights(parent_job_path=result["input"], db_path=path, output_dir=Path(directory) / "shorts")
            second = extract_highlights(parent_job_path=result["input"], db_path=path, output_dir=Path(directory) / "shorts")
            self.assertEqual(first["status"], "selected")
            self.assertGreaterEqual(len(first["shorts"]), 1)
            self.assertEqual(second["status"], "no_candidate")
            with sqlite3.connect(path) as db:
                lineage_count = db.execute("SELECT COUNT(*) FROM reusable_short_lineage").fetchone()[0]
            self.assertEqual(lineage_count, len(first["shorts"]))


if __name__ == "__main__":
    unittest.main()
