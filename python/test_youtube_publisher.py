from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from local_store import LocalStore
from youtube_publisher import build_metadata, load_playlists, load_policy

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config" / "youtube_metadata_policy.json"
PLAYLISTS = ROOT / "config" / "youtube_playlists.json"


class YouTubePublisherLocalTests(unittest.TestCase):
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
                "captions": [{"startSec": 0.0, "endSec": 1.2, "text": "The cannon opens the file."}],
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
            self.assertEqual(video["captions_source"], "edge_tts_word_boundaries")
            self.assertEqual(len(catalog["video_playlists"]), 1)
            self.assertEqual(catalog["video_playlists"][0]["youtube_playlist_id"], "catalog-playlist")

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


if __name__ == "__main__":
    unittest.main()
