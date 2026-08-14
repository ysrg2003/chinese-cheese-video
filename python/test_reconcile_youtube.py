import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import reconcile_youtube
from local_store import LocalStore


class ReconcileCurriculumTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = LocalStore(Path(self.tempdir.name) / "catalog.db")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_successful_reconciliation_marks_curriculum_episode_published(self) -> None:
        candidate = self.store.get_next_curriculum_candidate("en")
        assert candidate is not None
        lesson_key = candidate["payload"]["curriculum_lesson_key"]
        job_id = f"{candidate['id']}-en"
        job = dict(candidate["payload"])
        job.update(
            {
                "id": job_id,
                "title": candidate["title"],
                "language": "en",
                "content_type": candidate["content_type"],
                "narration": "A legal Xiangqi introduction.",
                "captions": [],
            }
        )
        self.store.add_candidate(candidate)
        self.store.update_curriculum_episode(lesson_key, "en", "retry", candidate_id=candidate["id"])
        self.store.create_job(job)
        self.store.upsert_youtube_publication(
            job_id,
            "en",
            candidate["content_type"],
            "published_thumbnail_pending",
            video_id="existing-public-video",
            video_url="https://www.youtube.com/watch?v=existing-public-video",
            playlist_id="playlist-001",
            playlist_url="https://www.youtube.com/playlist?list=playlist-001",
            metadata={"curriculum_lesson_key": lesson_key, "playlist_key": candidate["payload"]["playlist_key"]},
            error_message="uploadRateLimitExceeded",
        )
        published_result = {
            "status": "published",
            "video_id": "existing-public-video",
            "video_url": "https://www.youtube.com/watch?v=existing-public-video",
            "playlist_id": "playlist-001",
            "playlist_url": "https://www.youtube.com/playlist?list=playlist-001",
            "playlist_item": {"id": "item-001"},
            "metadata": {"curriculum_lesson_key": lesson_key, "playlist_key": candidate["payload"]["playlist_key"]},
        }
        with patch.dict(os.environ, {"YOUTUBE_PUBLISH_ENABLED": "1"}, clear=False):
            with patch("reconcile_youtube.LocalStore", return_value=self.store), patch(
                "reconcile_youtube.publish_video", return_value=published_result
            ):
                self.assertEqual(reconcile_youtube.main(), 0)

        publication = self.store.get_youtube_publication(job_id)
        self.assertIsNotNone(publication)
        self.assertEqual(publication["status"], "published")
        curriculum_status = self.store.curriculum_lesson_status(lesson_key, "en")
        self.assertIsNotNone(curriculum_status)
        self.assertEqual(curriculum_status["status"], "published")
        self.assertEqual(curriculum_status["job_id"], job_id)


if __name__ == "__main__":
    unittest.main()
