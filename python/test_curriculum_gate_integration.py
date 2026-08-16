from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from local_store import LocalStore


class CurriculumGateIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.previous_db = os.environ.get("LOCAL_DB_PATH")
        os.environ["LOCAL_DB_PATH"] = str(Path(self.temp.name) / "gate.db")
        self.store = LocalStore()

    def tearDown(self) -> None:
        if self.previous_db is None:
            os.environ.pop("LOCAL_DB_PATH", None)
        else:
            os.environ["LOCAL_DB_PATH"] = self.previous_db
        self.temp.cleanup()

    def test_first_lesson_is_the_only_runnable_lesson(self) -> None:
        gate = self.store.curriculum_gate("en")
        self.assertFalse(gate["complete"])
        self.assertEqual(gate["first_pending"]["lesson_key"], "en-001-what-is-xiangqi")
        self.assertEqual(gate["first_runnable"]["lesson_key"], "en-001-what-is-xiangqi")
        candidate = self.store.get_next_curriculum_candidate("en")
        self.assertEqual(candidate["payload"]["curriculum_lesson_key"], "en-001-what-is-xiangqi")

    def test_blocked_first_lesson_prevents_any_later_or_supplementary_selection(self) -> None:
        first = self.store.get_next_curriculum_candidate("en")
        assert first is not None
        key = first["payload"]["curriculum_lesson_key"]
        self.store.update_curriculum_episode(key, "en", "blocked", candidate_id=first["id"], error_message="contract failure")
        gate = self.store.curriculum_gate("en")
        self.assertFalse(gate["complete"])
        self.assertTrue(gate["blocked"])
        self.assertEqual(gate["first_pending"]["lesson_key"], key)
        self.assertIsNone(self.store.get_next_curriculum_candidate("en"))

    def test_deleted_lesson_requeued_is_selected_before_evergreen(self) -> None:
        first = self.store.get_next_curriculum_candidate("en")
        assert first is not None
        key = first["payload"]["curriculum_lesson_key"]
        self.store.add_candidate(first)
        self.store.update_curriculum_episode(key, "en", "published", candidate_id=first["id"], job_id=f"{first['id']}-en")
        second = self.store.get_next_curriculum_candidate("en")
        assert second is not None
        second_key = second["payload"]["curriculum_lesson_key"]
        self.store.update_curriculum_episode(second_key, "en", "retry", candidate_id=second["id"], error_message="deleted externally")
        selected = self.store.get_next_curriculum_candidate("en")
        self.assertEqual(selected["payload"]["curriculum_lesson_key"], second_key)
        self.assertEqual(second_key, "en-003-a-short-history-of-xiangqi")

    def test_claim_is_single_writer_and_cannot_claim_later_lesson(self) -> None:
        first = self.store.get_next_curriculum_candidate("en")
        assert first is not None
        first_key = first["payload"]["curriculum_lesson_key"]
        self.assertTrue(self.store.claim_curriculum_lesson(first_key, "en", first["id"]))
        self.assertFalse(self.store.claim_curriculum_lesson(first_key, "en", first["id"]))
        self.assertFalse(self.store.claim_curriculum_lesson("en-002-the-board", "en", "curriculum-en-002-the-board"))
        self.assertEqual(self.store.curriculum_lesson_status(first_key, "en")["status"], "queued")


if __name__ == "__main__":
    unittest.main()


class PublicationContractTests(unittest.TestCase):
    def test_published_without_video_id_is_rejected(self) -> None:
        from integration_contracts import validate_publication_contract

        job = {"id": "job-1", "language": "en", "curriculum_lesson_key": "en-001"}
        errors = validate_publication_contract(job, {"status": "published", "metadata": {"job_id": "job-1"}})
        self.assertTrue(any("video_id" in error for error in errors))

    def test_publication_metadata_must_match_job(self) -> None:
        from integration_contracts import validate_publication_contract

        job = {"id": "job-1", "language": "en", "curriculum_lesson_key": "en-001"}
        publication = {
            "status": "published",
            "video_id": "abc123",
            "video_url": "https://www.youtube.com/watch?v=abc123",
            "metadata": {"job_id": "other-job", "language": "en", "curriculum_lesson_key": "en-001"},
        }
        errors = validate_publication_contract(job, publication)
        self.assertTrue(any("job_id" in error for error in errors))

    def test_resumable_publication_status_is_valid(self) -> None:
        from integration_contracts import validate_publication_contract

        job = {"id": "job-1", "language": "en", "curriculum_lesson_key": "en-001"}
        publication = {"status": "published_thumbnail_pending", "video_id": "abc123", "metadata": {"job_id": "job-1"}}
        self.assertEqual(validate_publication_contract(job, publication), [])
