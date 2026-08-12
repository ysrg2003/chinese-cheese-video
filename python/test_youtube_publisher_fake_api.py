from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import youtube_publisher

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config" / "youtube_metadata_policy.json"
PLAYLISTS = ROOT / "config" / "youtube_playlists.json"


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeUploadRequest:
    def __init__(self):
        self.calls = 0

    def next_chunk(self):
        self.calls += 1
        return None, {"id": "video-001"}


class FakePlaylists:
    def __init__(self):
        self.created = []

    def list(self, **kwargs):
        return FakeRequest({"items": []})

    def insert(self, **kwargs):
        self.created.append(kwargs)
        return FakeRequest({"id": "playlist-001"})


class FakePlaylistItems:
    def __init__(self):
        self.inserted = []

    def list(self, **kwargs):
        return FakeRequest({"items": []})

    def insert(self, **kwargs):
        self.inserted.append(kwargs)
        return FakeRequest({"id": "playlist-item-001"})


class FakeService:
    def __init__(self):
        self.playlists_api = FakePlaylists()
        self.playlist_items_api = FakePlaylistItems()

    def playlists(self):
        return self.playlists_api

    def playlistItems(self):
        return self.playlist_items_api


class YouTubePublisherFakeApiTests(unittest.TestCase):
    def test_publish_uploads_and_associates_playlist(self):
        service = FakeService()
        job = {
            "id": "job-001",
            "title": "Find the Cannon Pin",
            "language": "en",
            "content_type": "tactics",
            "narration": "Find the forcing move before the cannon closes the file.",
        }
        with tempfile.NamedTemporaryFile(suffix=".mp4") as video, patch.dict(os.environ, {"YOUTUBE_PUBLISH_ENABLED": "1"}, clear=False), patch.object(
            youtube_publisher, "upload_video", return_value={"id": "video-001"}
        ):
            result = youtube_publisher.publish_video(
                video.name,
                job,
                policy_path=POLICY,
                playlists_path=PLAYLISTS,
                service=service,
            )
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["video_id"], "video-001")
        self.assertEqual(result["playlist_id"], "playlist-001")
        self.assertEqual(len(service.playlists_api.created), 1)
        self.assertEqual(len(service.playlist_items_api.inserted), 1)
        resource = service.playlist_items_api.inserted[0]["body"]["snippet"]["resourceId"]
        self.assertEqual(resource["videoId"], "video-001")

    def test_retry_reuses_existing_video_id(self):
        service = FakeService()
        job = {
            "id": "job-002",
            "title": "Retry the Playlist Association",
            "language": "en",
            "content_type": "tactics",
            "narration": "The upload already exists; only the playlist association needs a retry.",
        }
        with tempfile.NamedTemporaryFile(suffix=".mp4") as video, patch.dict(os.environ, {"YOUTUBE_PUBLISH_ENABLED": "1"}, clear=False), patch.object(
            youtube_publisher, "upload_video", side_effect=AssertionError("must not upload again")
        ):
            result = youtube_publisher.publish_video(
                video.name,
                job,
                policy_path=POLICY,
                playlists_path=PLAYLISTS,
                service=service,
                existing_publication={"video_id": "video-existing"},
            )
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["video_id"], "video-existing")
        resource = service.playlist_items_api.inserted[0]["body"]["snippet"]["resourceId"]
        self.assertEqual(resource["videoId"], "video-existing")


if __name__ == "__main__":
    unittest.main()
