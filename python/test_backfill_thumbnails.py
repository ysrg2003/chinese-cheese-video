import unittest

from backfill_thumbnails import _known_dimensions


class BackfillThumbnailTests(unittest.TestCase):
    def test_known_dimensions_accepts_comma_separated_verified_artifacts(self):
        parsed = _known_dimensions([
            "curriculum-en-015-the-cannon-and-its-mount-en=1080x1920,curriculum-en-016-soldiers-before-and-after-river-en=1080x1920"
        ])
        self.assertEqual(parsed["curriculum-en-015-the-cannon-and-its-mount-en"], (1080, 1920))
        self.assertEqual(parsed["curriculum-en-016-soldiers-before-and-after-river-en"], (1080, 1920))

    def test_known_dimensions_ignores_malformed_entries(self):
        parsed = _known_dimensions(["bad-entry,also-bad=0x0,valid=1920x1080"])
        self.assertEqual(parsed, {"valid": (1920, 1080)})


if __name__ == "__main__":
    unittest.main()
