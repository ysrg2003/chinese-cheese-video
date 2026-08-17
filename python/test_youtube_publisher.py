from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from local_store import LocalStore
from youtube_publisher import SCOPES, _reusable_existing_video_id, build_metadata, expected_video_dimensions, is_vertical_short, load_playlists, load_policy

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config" / "youtube_metadata_policy.json"
PLAYLISTS = ROOT / "config" / "youtube_playlists.json"


class YouTubePublisherLocalTests(unittest.TestCase):
    def test_oauth_scopes_include_thumbnail_upload_scope(self) -> None:
        self.assertIn("https://www.googleapis.com/auth/youtube.force-ssl", SCOPES)
        self.assertIn("https://www.googleapis.com/auth/youtube.upload", SCOPES)

    def test_only_explicit_short_uses_portrait_short_path(self) -> None:
        self.assertTrue(is_vertical_short(None, {"format": "short"}))
        self.assertTrue(is_vertical_short(None, {"format": "short", "width": 1080, "height": 1920}))
        self.assertFalse(is_vertical_short(None, {"format": "short", "width": 1920, "height": 1080}))
        self.assertFalse(is_vertical_short(None, {"format": "lesson", "width": 1080, "height": 1920}))
        self.assertFalse(is_vertical_short(None, {"format": "game", "width": 1080, "height": 1920}))

    def test_semantic_format_dimensions_are_deterministic(self) -> None:
        self.assertEqual(expected_video_dimensions({"format": "short"}), (1080, 1920))
        self.assertEqual(expected_video_dimensions({"format": "lesson"}), (1920, 1080))
        self.assertEqual(expected_video_dimensions({"format": "game"}), (1920, 1080))
        self.assertEqual(expected_video_dimensions({}), (1920, 1080))

    def test_english_metadata_maps_to_tactics_playlist(self) -> None:
        metadata = build_metadata(
            {
                "title": "The Cannon Pin You Must See",
                "language": "en",
                "content_type": "tactics",
                "narration": "Find the forcing move before the cannon closes the file.",
            },
            policy=load_policy(POLICY),
            playlists=load_playlists(PLAYLISTS),
        )
        self.assertEqual(metadata["language"], "en")
        self.assertEqual(metadata["playlist_key"], "en-tactics")
        self.assertLessEqual(len(metadata["title"]), 100)
        self.assertLessEqual(len(metadata["description"]), 5000)
        self.assertIn("#Xiangqi", metadata["hashtags"])
        self.assertNotIn("Arabic", metadata["description"])

    def test_curriculum_playlist_override_wins_over_content_type_mapping(self) -> None:
        metadata = build_metadata(
            {
                "title": "The 9x10 Point Board",
                "language": "en",
                "content_type": "definition",
                "playlist_key": "en-board-setup",
                "narration": "Learn the intersections before you learn the tactics.",
            },
            policy=load_policy(POLICY),
            playlists=load_playlists(PLAYLISTS),
        )
        self.assertEqual(metadata["playlist_key"], "en-board-setup")
        self.assertEqual(metadata["playlist_title"], "EN — Board, Setup, and Notation")

    def test_chinese_metadata_maps_to_endgame_playlist(self) -> None:
        metadata = build_metadata(
            {
                "title": "车兵残局的关键一步",
                "language": "zh",
                "content_type": "endgame",
                "narration": "这一步让红方把优势转化为胜势。",
            },
            policy=load_policy(POLICY),
            playlists=load_playlists(PLAYLISTS),
        )
        self.assertEqual(metadata["language"], "zh")
        self.assertEqual(metadata["playlist_key"], "zh-endgames")
        self.assertIn("#中国象棋", metadata["hashtags"])
        self.assertNotIn("#Xiangqi", metadata["hashtags"])

    def test_deleted_publication_id_is_never_reused_for_retry(self) -> None:
        self.assertEqual(
            _reusable_existing_video_id({"status": "deleted_invalid_content", "video_id": "deleted-video"}),
            "",
        )
        self.assertEqual(
            _reusable_existing_video_id({"status": "blocked_invalid_content", "video_id": "blocked-video"}),
            "",
        )
        self.assertEqual(
            _reusable_existing_video_id({"status": "uploaded_playlist_pending", "video_id": "retry-video"}),
            "retry-video",
        )
        self.assertEqual(
            _reusable_existing_video_id({"status": "published", "video_id": "published-video"}),
            "published-video",
        )
        self.assertEqual(
            _reusable_existing_video_id({"status": "published_thumbnail_pending", "video_id": "thumbnail-video"}),
            "thumbnail-video",
        )
        self.assertEqual(
            _reusable_existing_video_id({"status": "published_localization_pending", "video_id": "localization-video"}),
            "localization-video",
        )

    def test_publication_replacement_preserves_remediation_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "replacement.db")
            store.upsert_youtube_publication(
                "replacement-job-en",
                "en",
                "rules",
                "deleted_invalid_content",
                metadata={"remediation": {"original_video_id": "old-video"}},
            )
            store.upsert_youtube_publication(
                "replacement-job-en",
                "en",
                "rules",
                "published",
                video_id="new-video",
                video_url="https://www.youtube.com/watch?v=new-video",
                metadata={"title": "Corrected lesson"},
            )
            current = store.get_youtube_publication("replacement-job-en")
            self.assertEqual(current["video_id"], "new-video")
            self.assertEqual(current["metadata"]["remediation"]["original_video_id"], "old-video")

    def test_youtube_catalog_tracks_channel_playlists_video_and_association(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "catalog.db")
            job = {
                "id": "catalog-job-en",
                "title": "Catalog Test",
                "language": "en",
                "content_type": "tactics",
                "source_kind": "generated_evergreen",
                "source_url": "https://example.com/source",
                "narration": "The cannon opens the file.",
                "captions": [],
                "captions_source": "english_captions_disabled_in_video",
                "durationInSeconds": 4.2,
            }
            publication = {
                "status": "published",
                "video_id": "catalog-video",
                "video_url": "https://www.youtube.com/watch?v=catalog-video",
                "playlist_id": "catalog-playlist",
                "playlist_url": "https://www.youtube.com/playlist?list=catalog-playlist",
                "metadata": {"title": "Catalog Test", "playlist_key": "en-tactics", "privacyStatus": "public"},
            }
            store.upsert_youtube_catalog(job, publication, candidate_id="candidate-catalog")
            catalog = store.get_youtube_catalog()
            self.assertEqual(len(catalog["channels"]), 1)
            self.assertGreaterEqual(len(catalog["playlists"]), 22)
            video = next(item for item in catalog["videos"] if item["job_id"] == "catalog-job-en")
            self.assertEqual(video["status"], "published")
            self.assertEqual(video["playlist_key"], "en-tactics")
            self.assertEqual(video["captions_source"], "english_captions_disabled_in_video")
            self.assertEqual(len(catalog["video_playlists"]), 1)
            self.assertEqual(catalog["video_playlists"][0]["youtube_playlist_id"], "catalog-playlist")

    def test_thumbnail_pending_state_preserves_public_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "thumbnail-pending.db")
            store.upsert_youtube_publication(
                "thumbnail-pending-en",
                "en",
                "tactics",
                "published_thumbnail_pending",
                video_id="video-thumbnail",
                video_url="https://www.youtube.com/watch?v=video-thumbnail",
                playlist_id="playlist-thumbnail",
                playlist_url="https://www.youtube.com/playlist?list=playlist-thumbnail",
                metadata={"title": "Thumbnail Pending"},
                error_message="uploadRateLimitExceeded",
            )
            pending = store.get_youtube_publication("thumbnail-pending-en")
            self.assertEqual(pending["status"], "published_thumbnail_pending")
            self.assertEqual(pending["video_id"], "video-thumbnail")
            self.assertEqual(pending["playlist_id"], "playlist-thumbnail")
            store.upsert_youtube_publication(
                "thumbnail-pending-en",
                "en",
                "tactics",
                "published",
                video_id="video-thumbnail",
                metadata={"title": "Thumbnail Pending"},
            )
            completed = store.get_youtube_publication("thumbnail-pending-en")
            self.assertEqual(completed["status"], "published")
            self.assertEqual(completed["video_id"], "video-thumbnail")
            self.assertEqual(completed["playlist_id"], "playlist-thumbnail")

    def test_publication_state_is_persistent_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "test.db")
            store.upsert_youtube_publication(
                "candidate-1-en",
                "en",
                "tactics",
                "published",
                video_id="video-123",
                video_url="https://www.youtube.com/watch?v=video-123",
                playlist_id="playlist-456",
                playlist_url="https://www.youtube.com/playlist?list=playlist-456",
                metadata={"title": "A test"},
            )
            first = store.get_youtube_publication("candidate-1-en")
            self.assertIsNotNone(first)
            self.assertEqual(first["status"], "published")
            self.assertEqual(first["video_id"], "video-123")
            self.assertEqual(first["metadata"]["title"], "A test")
            store.upsert_youtube_publication(
                "candidate-1-en",
                "en",
                "tactics",
                "published",
                video_id="video-123",
            )
            second = store.get_youtube_publication("candidate-1-en")
            self.assertEqual(second["video_id"], "video-123")
            self.assertEqual(second["status"], "published")
            store.upsert_youtube_publication(
                "candidate-1-en",
                "en",
                "tactics",
                "uploaded_playlist_pending",
                video_id="video-123",
                video_url="https://www.youtube.com/watch?v=video-123",
                playlist_id=None,
                playlist_url=None,
                metadata={"title": "A test"},
                error_message="playlistNotFound",
            )
            pending = store.get_youtube_publication("candidate-1-en")
            self.assertEqual(pending["video_id"], "video-123")
            self.assertIsNone(pending["playlist_id"])
            self.assertEqual(pending["status"], "uploaded_playlist_pending")


if __name__ == "__main__":
    unittest.main()
