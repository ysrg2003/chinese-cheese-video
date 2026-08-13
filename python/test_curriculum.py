import os
import tempfile
import unittest
from pathlib import Path

from local_store import LocalStore


class CurriculumStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "curriculum.db"
        self.previous_db = os.environ.get("LOCAL_DB_PATH")
        os.environ["LOCAL_DB_PATH"] = str(self.db_path)
        self.store = LocalStore()

    def tearDown(self) -> None:
        if self.previous_db is None:
            os.environ.pop("LOCAL_DB_PATH", None)
        else:
            os.environ["LOCAL_DB_PATH"] = self.previous_db
        self.temp.cleanup()

    def test_seeded_curriculum_starts_with_what_is_xiangqi(self) -> None:
        summary = self.store.curriculum_summary("en")
        self.assertEqual(summary["total_lessons"], 72)
        self.assertEqual(summary["status_counts"], {"planned": 72})
        next_candidate = self.store.get_next_curriculum_candidate("en")
        self.assertIsNotNone(next_candidate)
        self.assertEqual(next_candidate["payload"]["curriculum_lesson_key"], "en-001-what-is-xiangqi")
        self.assertEqual(next_candidate["payload"]["playlist_key"], "en-start-here")
        self.assertEqual(next_candidate["title"], "What Is Xiangqi?")

    def test_prerequisite_unlocks_only_after_publication(self) -> None:
        first = self.store.get_next_curriculum_candidate("en")
        assert first is not None
        first_key = first["payload"]["curriculum_lesson_key"]
        self.store.update_curriculum_episode(first_key, "en", "published", candidate_id=first["id"], job_id="job-001")
        next_candidate = self.store.get_next_curriculum_candidate("en")
        self.assertIsNotNone(next_candidate)
        self.assertEqual(next_candidate["payload"]["curriculum_lesson_key"], "en-002-xiangqi-in-60-seconds")

    def test_curriculum_candidate_contains_teaching_and_board_contract(self) -> None:
        candidate = self.store.get_next_curriculum_candidate("en")
        assert candidate is not None
        payload = candidate["payload"]
        self.assertTrue(payload["objective"])
        self.assertTrue(payload["analysis_focus"])
        self.assertTrue(payload["hook"])
        self.assertEqual(len(payload["moves"]), 3)
        self.assertTrue(all("piece" in move and "label" in move for move in payload["moves"]))


if __name__ == "__main__":
    unittest.main()
