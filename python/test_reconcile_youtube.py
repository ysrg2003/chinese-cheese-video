import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import reconcile_youtube
from local_store import LocalStore


class ReconcileCurriculumTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = LocalStore(Path(self.tempdir.name) / "catalog.db")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_deleted_public_video_is_requeued_for_regeneration(self) -> None:
        candidate = self.store.get_next_curriculum_candidate("en")
        assert candidate is not None
        lesson_key = candidate["payload"]["curriculum_lesson_key"]
        job_id = f"{candidate['id']}-en"
        job = dict(candidate["payload"])
        job.update({"id": job_id, "title": candidate["title"], "language": "en", "content_type": candidate["content_type"]})
        self.store.add_candidate(candidate)
        self.store.update_curriculum_episode(lesson_key, "en", "published", candidate_id=candidate["id"], job_id=job_id)
        self.store.create_job(job)
        self.store.upsert_youtube_publication(
            job_id, "en", candidate["content_type"], "published", video_id="deleted-video",
            video_url="https://www.youtube.com/watch?v=deleted-video",
            metadata={"curriculum_lesson_key": lesson_key},
        )
        service = Mock()
        service.videos.return_value.list.return_value = Mock(execute=Mock(return_value={"items": []}))
        with patch.dict(os.environ, {"YOUTUBE_PUBLISH_ENABLED": "1"}, clear=False), patch(
            "reconcile_youtube.LocalStore", return_value=self.store
        ), patch("reconcile_youtube.build_service", return_value=service), patch(
            "reconcile_youtube.publish_video"
        ) as publish:
            self.assertEqual(reconcile_youtube.main(), 0)
        state = self.store.curriculum_lesson_status(lesson_key, "en")
        self.assertIsNotNone(state)
        self.assertEqual(state["status"], "retry")
        self.assertEqual(self.store.get_youtube_publication(job_id)["status"], "deleted_external")
        publish.assert_not_called()

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


    def test_stale_review_only_block_is_requeued_without_publication(self) -> None:
        candidate = self.store.get_next_curriculum_candidate("en")
        assert candidate is not None
        lesson_key = candidate["payload"]["curriculum_lesson_key"]
        job_id = f"{candidate['id']}-en"
        self.store.add_candidate(candidate)
        self.store.update_curriculum_episode(
            lesson_key,
            "en",
            "blocked",
            candidate_id=candidate["id"],
            job_id=job_id,
            error_message="Review artifact generated; public replacement requires explicit approval",
        )
        with self.store._connect() as connection:
            connection.execute(
                "UPDATE curriculum_episode_plans SET updated_at='2020-01-01T00:00:00+00:00' WHERE lesson_key=? AND language='en'",
                (lesson_key,),
            )
        recovered = self.store.recover_stale_curriculum_processing("en", 900)
        self.assertEqual(recovered[0]["lesson_key"], lesson_key)
        self.assertEqual(self.store.curriculum_lesson_status(lesson_key, "en")["status"], "retry")

    def test_stale_publishing_without_video_id_is_requeued_safely(self) -> None:
        candidate = self.store.get_next_curriculum_candidate("en")
        assert candidate is not None
        lesson_key = candidate["payload"]["curriculum_lesson_key"]
        job_id = f"{candidate['id']}-en"
        self.store.add_candidate(candidate)
        self.store.update_curriculum_episode(
            lesson_key,
            "en",
            "retry",
            candidate_id=candidate["id"],
            job_id=job_id,
            error_message="YouTube publish lease expired during a previous run",
        )
        self.store.upsert_youtube_publication(job_id, "en", "rules", "publishing", video_id=None)
        with self.store._connect() as connection:
            connection.execute(
                "UPDATE curriculum_episode_plans SET updated_at='2020-01-01T00:00:00+00:00' WHERE lesson_key=? AND language='en'",
                (lesson_key,),
            )
        recovered = self.store.recover_stale_curriculum_processing("en", 900)
        self.assertEqual(recovered[0]["previous_status"], "publishing")
        publication = self.store.get_youtube_publication(job_id)
        self.assertEqual(publication["status"], "failed")

    def test_stale_processing_without_publication_is_requeued(self) -> None:
        candidate = self.store.get_next_curriculum_candidate("en")
        assert candidate is not None
        lesson_key = candidate["payload"]["curriculum_lesson_key"]
        job_id = f"{candidate['id']}-en"
        self.store.add_candidate(candidate)
        self.store.update_curriculum_episode(lesson_key, "en", "processing", candidate_id=candidate["id"], job_id=job_id)
        with self.store._connect() as connection:
            connection.execute(
                "UPDATE curriculum_episode_plans SET updated_at='2020-01-01T00:00:00+00:00' WHERE lesson_key=? AND language='en'",
                (lesson_key,),
            )
        recovered = self.store.recover_stale_curriculum_processing("en", 900)
        self.assertEqual(recovered[0]["lesson_key"], lesson_key)
        self.assertEqual(self.store.curriculum_lesson_status(lesson_key, "en")["status"], "retry")
        self.assertEqual(self.store.list_candidates(status="discovered", limit=10)[0]["id"], candidate["id"])


if __name__ == "__main__":
    unittest.main()
