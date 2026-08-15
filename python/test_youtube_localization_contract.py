import os
import tempfile
import unittest
from pathlib import Path
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
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("zh/captions.srt", "zh/captions.vtt", "zh/voice.mp3"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"artifact")
            assets = {
                "en": {"enabled": False, "source": "english_captions_disabled_in_video"},
                "zh": {
                    "title": "中国象棋：合法的防守",
                    "description": "这是一个中国象棋教学视频。",
                    "audio_path": str(root / "zh/voice.mp3"),
                    "caption_srt": str(root / "zh/captions.srt"),
                    "caption_vtt": str(root / "zh/captions.vtt"),
                    "audio_track_status": "generated_studio_upload_required",
                },
            }
            from PIL import Image
            thumbnail_en = root / "thumbnail.jpg"
            Image.new("RGB", (1280, 720), (20, 30, 40)).save(thumbnail_en, format="JPEG")
            thumbnail_assets = {"default": str(thumbnail_en), "english": str(thumbnail_en), "localized_thumbnail_status": "disabled_by_policy"}
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
                "localization.upload_caption_tracks", return_value={"zh-Hans": {"id": "zh-caption"}}
            ), patch("localization.update_localized_metadata", return_value={"id": "video-localized"}), patch(
                "thumbnail.generate_thumbnail_assets", return_value=thumbnail_assets
            ), patch("localization.set_thumbnail", return_value={"items": []}):
                result = youtube_publisher.publish_video(None, job, service=service)
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["localization"]["status"], "completed")
        self.assertEqual(result["video_id"], "video-localized")
        self.assertEqual(len(service.playlist_items), 1)

    def test_portrait_short_does_not_call_api_thumbnail_setter(self):
        service = FakeExtendedApi()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("zh/captions.srt", "zh/captions.vtt", "zh/voice.mp3"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"artifact")
            assets = {
                "en": {"enabled": False, "source": "english_captions_disabled_in_video"},
                "zh": {
                    "title": "中国象棋棋盘",
                    "description": "这是一个中国象棋棋盘教学视频。",
                    "audio_path": str(root / "zh/voice.mp3"),
                    "caption_srt": str(root / "zh/captions.srt"),
                    "caption_vtt": str(root / "zh/captions.vtt"),
                    "audio_track_status": "generated_studio_upload_required",
                },
            }
            job = {
                "id": "portrait-short-contract",
                "title": "The 9×10 Point Board",
                "language": "en",
                "content_type": "board_setup",
                "narration": "A Xiangqi board has nine files and ten ranks.",
            }
            with patch.dict(os.environ, {"YOUTUBE_PUBLISH_ENABLED": "1", "YOUTUBE_LOCALIZATION_ENABLED": "1"}, clear=False), patch.object(
                youtube_publisher, "upload_video", return_value={"id": "portrait-video"}
            ), patch.object(youtube_publisher, "is_vertical_short", return_value=True), patch(
                "localization.generate_localization_assets", return_value=assets
            ), patch("localization.upload_caption_tracks", return_value={"zh-Hans": {"id": "zh-caption"}}), patch(
                "localization.update_localized_metadata", return_value={"id": "portrait-video"}
            ), patch("thumbnail.generate_thumbnail_assets") as thumbnail_mock, patch(
                "localization.set_thumbnail"
            ) as setter_mock:
                result = youtube_publisher.publish_video(None, job, service=service)
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["thumbnail_policy"], "manual_studio_required")
        self.assertEqual(result["localization"]["thumbnail"]["default_upload_status"], "manual_studio_required")
        thumbnail_mock.assert_not_called()
        setter_mock.assert_not_called()
        self.assertEqual(service.thumbnail_calls, [])

    def test_localization_preflight_blocks_upload_on_missing_artifacts(self):
        service = FakeExtendedApi()
        job = {
            "id": "blocked-localization-contract",
            "title": "A Legal Xiangqi Defense",
            "language": "en",
            "content_type": "rules",
            "narration": "This is a legal Xiangqi defense.",
        }
        with tempfile.NamedTemporaryFile(suffix=".mp4") as video, patch.dict(
            os.environ, {"YOUTUBE_PUBLISH_ENABLED": "1", "YOUTUBE_LOCALIZATION_ENABLED": "1"}, clear=False
        ), patch.object(youtube_publisher, "upload_video", return_value={"id": "must-not-upload"}) as upload_mock, patch(
            "localization.generate_localization_assets", side_effect=RuntimeError("translation unavailable")
        ):
            with self.assertRaises(youtube_publisher.YouTubePublisherError):
                youtube_publisher.publish_video(video.name, job, service=service)
        upload_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
