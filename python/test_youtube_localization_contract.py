import os
import tempfile
import unittest
from unittest.mock import patch

import youtube_publisher


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeExtendedApi:
    def __init__(self):
        self.caption_calls = []
        self.video_updates = []
        self.thumbnail_calls = []
        self.playlist_created = []
        self.playlist_items = []

    def playlists(self):
        owner = self
        class Playlists:
            def list(self, **kwargs):
                return FakeRequest({"items": []})
            def insert(self, **kwargs):
                owner.playlist_created.append(kwargs)
                return FakeRequest({"id": "playlist-localized"})
        return Playlists()

    def playlistItems(self):
        owner = self
        class PlaylistItems:
            def list(self, **kwargs):
                return FakeRequest({"items": []})
            def insert(self, **kwargs):
                owner.playlist_items.append(kwargs)
                return FakeRequest({"id": "playlist-item-localized"})
        return PlaylistItems()

    def captions(self):
        owner = self
        class Captions:
            def list(self, **kwargs):
                return FakeRequest({"items": []})
            def insert(self, **kwargs):
                owner.caption_calls.append(kwargs)
                return FakeRequest({"id": "caption-localized"})
        return Captions()

    def videos(self):
        owner = self
        class Videos:
            def update(self, **kwargs):
                owner.video_updates.append(kwargs)
                return FakeRequest({"id": "video-localized"})
        return Videos()

    def thumbnails(self):
        owner = self
        class Thumbnails:
            def set(self, **kwargs):
                owner.thumbnail_calls.append(kwargs)
                return FakeRequest({"items": [{"url": "local-thumb"}]})
        return Thumbnails()


class YouTubeLocalizationContractTests(unittest.TestCase):
    def test_localization_runs_after_publication_without_reupload(self):
        service = FakeExtendedApi()
        assets = {
            "en": {"caption_srt": "/tmp/en.srt"},
            "zh": {
                "title": "中国象棋：合法的防守",
                "description": "这是一个中国象棋教学视频。",
                "audio_track_status": "generated_studio_upload_required",
            },
        }
        thumbnail_assets = {"default": "/tmp/thumbnail.jpg", "zh_studio_localized": "/tmp/thumbnail_zh.jpg"}
        job = {
            "id": "localized-contract",
            "title": "A Legal Xiangqi Defense",
            "language": "en",
            "content_type": "rules",
            "narration": "This is a legal Xiangqi defense.",
        }
        with patch.dict(os.environ, {"YOUTUBE_PUBLISH_ENABLED": "1", "YOUTUBE_LOCALIZATION_ENABLED": "1"}, clear=False), patch.object(
            youtube_publisher, "upload_video", return_value={"id": "video-localized"}
        ), patch("localization.generate_localization_assets", return_value=assets), patch(
            "localization.upload_caption_tracks", return_value={"en": {"id": "en-caption"}, "zh-Hans": {"id": "zh-caption"}}
        ), patch("localization.update_localized_metadata", return_value={"id": "video-localized"}), patch(
            "thumbnail.generate_thumbnail_assets", return_value=thumbnail_assets
        ), patch("localization.set_thumbnail", return_value={"items": []}):
            result = youtube_publisher.publish_video(None, job, service=service)
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["localization"]["status"], "completed")
        self.assertEqual(result["video_id"], "video-localized")
        self.assertEqual(len(service.playlist_items), 1)


if __name__ == "__main__":
    unittest.main()
