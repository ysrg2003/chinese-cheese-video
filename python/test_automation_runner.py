import argparse
import unittest
from unittest.mock import patch

from automation_runner import PublicationPendingError, is_reconciliation_only, run_one


class AutomationModeTests(unittest.TestCase):
    def test_zero_daily_count_is_reconciliation_only(self) -> None:
        args = argparse.Namespace(daily_count=0, reconcile_only=False)
        self.assertTrue(is_reconciliation_only(args))

    def test_explicit_reconcile_only_is_true_even_with_positive_count(self) -> None:
        args = argparse.Namespace(daily_count=1, reconcile_only=True)
        self.assertTrue(is_reconciliation_only(args))

    def test_normal_daily_run_can_produce_content(self) -> None:
        args = argparse.Namespace(daily_count=1, reconcile_only=False)
        self.assertFalse(is_reconciliation_only(args))

    def test_public_pending_publication_never_rerenders(self) -> None:
        class PendingStore:
            def get_youtube_publication(self, job_id: str) -> dict[str, str]:
                return {
                    "status": "published_thumbnail_pending",
                    "video_id": "dw6V8q69hY8",
                }

        candidate = {"id": "curriculum-en-013", "title": "The Horse and the Blocked Eye"}
        with patch("automation_runner.subprocess.run") as render:
            with self.assertRaises(PublicationPendingError):
                run_one(candidate, "en", PendingStore(), "test-run")
        render.assert_not_called()


if __name__ == "__main__":
    unittest.main()
