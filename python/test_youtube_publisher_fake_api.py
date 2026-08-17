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
        self.stale = False

    def list(self, **kwargs):
        if self.stale:
            return FakeRequest({"items": [{"id": "playlist-stale", "snippet": {"title": "EN — Tactics 101"}}]})
        return FakeRequest({"items": []})

    def insert(self, **kwargs):
        self.created.append(kwargs)
        self.stale = False
        return FakeRequest({"id": "playlist-001"})


class FakeHttpError(Exception):
    def __init__(self, message="playlistNotFound"):
        super().__init__(message)
        self.resp = type("Response", (), {"status": 404})()


def thumbnail_upload_response(video_id: str) -> dict:
    return {
        "kind": "youtube#thumbnailSetResponse",
        "items": [{
            "maxres": {
                "url": f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
                "width": 1280,
                "height": 720,
            }
        }],
    }


def dynamic_thumbnail_upload(_service, video_id, _thumbnail_path):
    return thumbnail_upload_response(str(video_id))


class FakeVideos:
    def list(self, **kwargs):
        video_id = str(kwargs.get("id") or "video-001")
        return FakeRequest({"items": [{"snippet": {"thumbnails": thumbnail_upload_response(video_id)["items"][0]}}]})


class StaleVideos(FakeVideos):
    def list(self, **kwargs):
        video_id = str(kwargs.get("id") or "video-001")
        return FakeRequest({"items": [{"snippet": {"thumbnails": {"maxres": {"url": f"https://i.ytimg.com/vi/{video_id}-old/maxresdefault.jpg", "width": 1280, "height": 720}}}}]})


class FakePlaylistItems:
    def __init__(self):
        self.inserted = []
        self.raise_stale_once = False

    def list(self, **kwargs):
        if self.raise_stale_once and kwargs.get("playlistId") == "playlist-stale":
            self.raise_stale_once = False
            raise FakeHttpError()
        return FakeRequest({"items": []})

    def insert(self, **kwargs):
        self.inserted.append(kwargs)
        return FakeRequest({"id": "playlist-item-001"})


class FakeService:
    def __init__(self):
        self.playlists_api = FakePlaylists()
        self.playlist_items_api = FakePlaylistItems()
        self.videos_api = FakeVideos()

    def playlists(self):
        return self.playlists_api

    def playlistItems(self):
        return self.playlist_items_api

    def captions(self):
        return object()

    def videos(self):
        return self.videos_api

    def thumbnails(self):
        return object()


class FakeThumbnailRateLimitError(Exception):
    def __init__(self):
        super().__init__("The user has uploaded too many thumbnails recently: uploadRateLimitExceeded")
        self.resp = type("Response", (), {"status": 429})()


class YouTubePublisherFakeApiTests(unittest.TestCase):
    def test_publish_uploads_and_associates_playlist(self):
        service = FakeService()
        job = {
            "id": "job-001",
            "title": "Find the Cannon Pin",
            "language": "en",
            "content_type": "tactics",
            "format": "lesson",
            "renderedWidth": 1920,
            "renderedHeight": 1080,
            "narration": "Find the forcing move before the cannon closes the file.",
        }
        with tempfile.NamedTemporaryFile(suffix=".mp4") as video, patch.dict(os.environ, {"YOUTUBE_PUBLISH_ENABLED": "1", "YOUTUBE_LOCALIZATION_ENABLED": "0"}, clear=False), patch.object(
            youtube_publisher, "upload_video", return_value={"id": "video-001"}
        ), patch("thumbnail.generate_thumbnail_assets", return_value={"default": "thumbnail_en.jpg", "english": "thumbnail_en.jpg"}), patch(
            "thumbnail.validate_thumbnail_assets", return_value=[]
        ), patch("localization.set_thumbnail", side_effect=dynamic_thumbnail_upload):
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

    def test_standard_thumbnail_must_pass_youtube_readback(self):
        service = FakeService()
        service.videos_api = StaleVideos()
        job = {
            "id": "job-stale-thumbnail",
            "title": "Stale Thumbnail",
            "language": "en",
            "content_type": "tactics",
            "format": "lesson",
            "renderedWidth": 1920,
            "renderedHeight": 1080,
            "narration": "The uploaded thumbnail must be read back from YouTube.",
        }
        with tempfile.NamedTemporaryFile(suffix=".mp4") as video, patch.dict(os.environ, {"YOUTUBE_PUBLISH_ENABLED": "1", "YOUTUBE_LOCALIZATION_ENABLED": "0"}, clear=False), patch.object(
            youtube_publisher, "upload_video", return_value={"id": "video-stale-thumbnail"}
        ), patch("thumbnail.generate_thumbnail_assets", return_value={"default": "thumbnail_en.jpg", "english": "thumbnail_en.jpg"}), patch(
            "thumbnail.validate_thumbnail_assets", return_value=[]
        ), patch("localization.set_thumbnail", side_effect=dynamic_thumbnail_upload):
            result = youtube_publisher.publish_video(video.name, job, policy_path=POLICY, playlists_path=PLAYLISTS, service=service)
        self.assertEqual(result["status"], "published_localization_pending")
        self.assertIn("read-back failed", result["error_message"])

    def test_new_storyboard_upload_requires_rendered_visual_qa(self):
        service = FakeService()
        job = {
            "id": "job-missing-visual-qa",
            "title": "Missing Visual QA",
            "language": "en",
            "content_type": "tactics",
            "format": "lesson",
            "renderedWidth": 1920,
            "renderedHeight": 1080,
            "narration": "The board must explain the sentence.",
            "visual_mode": "storyboard",
            "visualStoryboardSource": "ai_router",
        }
        with tempfile.NamedTemporaryFile(suffix=".mp4") as video, patch.dict(os.environ, {"YOUTUBE_PUBLISH_ENABLED": "1", "YOUTUBE_LOCALIZATION_ENABLED": "0"}, clear=False), patch.object(
            youtube_publisher, "upload_video", side_effect=AssertionError("must not upload without visual QA")
        ) as upload_mock:
            with self.assertRaises(youtube_publisher.YouTubePublisherError) as context:
                youtube_publisher.publish_video(
                    video.name,
                    job,
                    policy_path=POLICY,
                    playlists_path=PLAYLISTS,
                    service=service,
                )
        self.assertIn("visual QA gate failed", str(context.exception))
        upload_mock.assert_not_called()

    def test_stale_playlist_is_replaced_without_reupload(self):
        service = FakeService()
        service.playlists_api.stale = True
        service.playlist_items_api.raise_stale_once = True
        job = {
            "id": "job-stale-playlist",
            "title": "Replace a Stale Playlist",
            "language": "en",
            "content_type": "tactics",
            "format": "lesson",
            "renderedWidth": 1920,
            "renderedHeight": 1080,
            "narration": "The video already exists; replace only the deleted playlist.",
        }
        with tempfile.NamedTemporaryFile(suffix=".mp4") as video, patch.dict(os.environ, {"YOUTUBE_PUBLISH_ENABLED": "1", "YOUTUBE_LOCALIZATION_ENABLED": "0"}, clear=False), patch.object(
            youtube_publisher, "upload_video", side_effect=AssertionError("must not upload again")
        ), patch("thumbnail.generate_thumbnail_assets", return_value={"default": "thumbnail_en.jpg", "english": "thumbnail_en.jpg"}), patch(
            "thumbnail.validate_thumbnail_assets", return_value=[]
        ), patch("localization.set_thumbnail", side_effect=dynamic_thumbnail_upload):
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
        self.assertEqual(result["playlist_id"], "playlist-001")
        self.assertEqual(len(service.playlists_api.created), 1)
        resource = service.playlist_items_api.inserted[0]["body"]["snippet"]["resourceId"]
        self.assertEqual(resource["videoId"], "video-existing")

    def test_thumbnail_rate_limit_preserves_public_video_and_retry_does_not_reupload(self):
        service = FakeService()
        job = {
            "id": "job-thumbnail-pending",
            "title": "Thumbnail Retry",
            "language": "en",
            "content_type": "tactics",
            "format": "lesson",
            "renderedWidth": 1920,
            "renderedHeight": 1080,
            "narration": "Explain the pressure, effect, and rule around the move.",
        }
        localization_assets = {"zh": {"title": "缩略图重试", "description": "测试"}, "en": {"title": "Thumbnail Retry"}}
        thumbnail_assets = {"default": "thumbnail_en.jpg", "english": "thumbnail_en.jpg"}
        with tempfile.NamedTemporaryFile(suffix=".mp4") as video, patch.dict(os.environ, {"YOUTUBE_PUBLISH_ENABLED": "1", "YOUTUBE_LOCALIZATION_ENABLED": "1"}, clear=False), patch.object(
            youtube_publisher, "upload_video", return_value={"id": "video-thumbnail-pending"}
        ) as upload_mock, patch("localization.generate_localization_assets", return_value=localization_assets), patch(
            "localization.validate_localization_assets", return_value=[]
        ), patch("thumbnail.generate_thumbnail_assets", return_value=thumbnail_assets), patch(
            "thumbnail.validate_thumbnail_assets", return_value=[]
        ), patch("localization.upload_caption_tracks", return_value={"zh": {"status": "completed"}}), patch(
            "localization.update_localized_metadata", return_value={"ok": True}
        ), patch("localization.set_thumbnail", side_effect=FakeThumbnailRateLimitError()):
            first = youtube_publisher.publish_video(
                video.name,
                job,
                policy_path=POLICY,
                playlists_path=PLAYLISTS,
                service=service,
            )
        self.assertEqual(first["status"], "published_thumbnail_pending")
        self.assertEqual(first["video_id"], "video-thumbnail-pending")
        self.assertEqual(first["playlist_id"], "playlist-001")
        self.assertEqual(upload_mock.call_count, 1)

        with tempfile.NamedTemporaryFile(suffix=".mp4") as video, patch.dict(os.environ, {"YOUTUBE_PUBLISH_ENABLED": "1", "YOUTUBE_LOCALIZATION_ENABLED": "1"}, clear=False), patch.object(
            youtube_publisher, "upload_video", side_effect=AssertionError("must not re-upload an existing public video")
        ) as retry_upload, patch("localization.generate_localization_assets", return_value=localization_assets), patch(
            "localization.validate_localization_assets", return_value=[]
        ), patch("thumbnail.generate_thumbnail_assets", return_value=thumbnail_assets), patch(
            "thumbnail.validate_thumbnail_assets", return_value=[]
        ), patch("localization.upload_caption_tracks", return_value={"zh": {"status": "completed"}}), patch(
            "localization.update_localized_metadata", return_value={"ok": True}
        ), patch("localization.set_thumbnail", side_effect=dynamic_thumbnail_upload):
            second = youtube_publisher.publish_video(
                None,
                job,
                policy_path=POLICY,
                playlists_path=PLAYLISTS,
                service=service,
                existing_publication={
                    "status": "published_thumbnail_pending",
                    "video_id": "video-thumbnail-pending",
                    "video_url": "https://www.youtube.com/watch?v=video-thumbnail-pending",
                    "playlist_id": "playlist-001",
                    "playlist_url": "https://www.youtube.com/playlist?list=playlist-001",
                },
            )
        self.assertEqual(second["status"], "published")
        self.assertEqual(second["video_id"], "video-thumbnail-pending")
        retry_upload.assert_not_called()

    def test_retry_reuses_existing_video_id(self):
        service = FakeService()
        job = {
            "id": "job-002",
            "title": "Retry the Playlist Association",
            "language": "en",
            "content_type": "tactics",
            "format": "lesson",
            "renderedWidth": 1920,
            "renderedHeight": 1080,
            "narration": "The upload already exists; only the playlist association needs a retry.",
        }
        with tempfile.NamedTemporaryFile(suffix=".mp4") as video, patch.dict(os.environ, {"YOUTUBE_PUBLISH_ENABLED": "1", "YOUTUBE_LOCALIZATION_ENABLED": "0"}, clear=False), patch.object(
            youtube_publisher, "upload_video", side_effect=AssertionError("must not upload again")
        ), patch("thumbnail.generate_thumbnail_assets", return_value={"default": "thumbnail_en.jpg", "english": "thumbnail_en.jpg"}), patch(
            "thumbnail.validate_thumbnail_assets", return_value=[]
        ), patch("localization.set_thumbnail", side_effect=dynamic_thumbnail_upload):
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
