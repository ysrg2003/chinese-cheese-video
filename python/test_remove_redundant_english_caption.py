from __future__ import annotations

import unittest

from remove_redundant_english_caption import remove_redundant_english_tracks


class FakeRequest:
    def __init__(self, payload=None):
        self.payload = payload or {}

    def execute(self):
        return self.payload


class FakeCaptions:
    def __init__(self):
        self.deleted = []

    def list(self, **kwargs):
        return FakeRequest({
            "items": [
                {"id": "manual-en", "snippet": {"language": "en", "name": "English transcript", "trackKind": "standard"}},
                {"id": "auto-en", "snippet": {"language": "en", "name": "English (auto-generated)", "trackKind": "ASR"}},
                {"id": "zh-track", "snippet": {"language": "zh-Hans", "name": "简体中文 transcript", "trackKind": "standard"}},
            ]
        })

    def delete(self, **kwargs):
        self.deleted.append(kwargs["id"])
        return FakeRequest({})


class FakeService:
    def __init__(self):
        self._captions = FakeCaptions()

    def captions(self):
        return self._captions


class RemoveRedundantEnglishCaptionTests(unittest.TestCase):
    def test_dry_run_matches_only_legacy_manual_english_track(self):
        service = FakeService()
        result = remove_redundant_english_tracks(service, "video-1", dry_run=True)
        self.assertEqual([item["id"] for item in result["matched"]], ["manual-en"])
        self.assertEqual(result["deleted_ids"], [])
        self.assertEqual(service._captions.deleted, [])

    def test_delete_removes_only_legacy_manual_english_track(self):
        service = FakeService()
        result = remove_redundant_english_tracks(service, "video-1")
        self.assertEqual(result["deleted_ids"], ["manual-en"])
        self.assertEqual(service._captions.deleted, ["manual-en"])


if __name__ == "__main__":
    unittest.main()
