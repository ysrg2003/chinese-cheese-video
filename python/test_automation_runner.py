import argparse
import tempfile
import unittest
from pathlib import Path
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

    def test_failed_production_invokes_self_repair_and_reuses_job_id(self) -> None:
        class CleanStore:
            def get_publication_reset_history(self, job_id: str):
                return None

            def get_youtube_publication(self, job_id: str):
                return None

        candidate = {"id": "dynamic-repair-candidate", "title": "Repair Candidate", "content_type": "trend_breakdown", "language": "en", "payload": {"fen": "valid"}}
        with tempfile.TemporaryDirectory() as directory:
            override = Path(directory) / "director-override.json"
            override.write_text('{"title":"Repaired","moves":[]}', encoding="utf-8")
            repair_report = {"status": "patched", "override_path": str(override), "override_kind": "director"}
            failed = __import__("subprocess").CalledProcessError(1, ["pipeline"])
            with patch.dict("os.environ", {"YOUTUBE_PUBLISH_ENABLED": "0", "XIANGQI_REVIEW_ONLY": "0", "SELF_REPAIR_ENABLED": "1", "SELF_REPAIR_MAX_ATTEMPTS": "1", "XIANGQI_OUTPUT_ROOT": directory}, clear=False):
                with patch("automation_runner.subprocess.run", side_effect=[failed, None]) as render:
                    with patch("self_repair.repair_failure", return_value=repair_report) as repair:
                        result = run_one(candidate, "en", CleanStore(), "test-run")
            self.assertEqual(result, "dynamic-repair-candidate-en")
            self.assertEqual(render.call_count, 2)
            self.assertIn("--director-override", render.call_args_list[1].args[0])
            repair.assert_called_once()

    def test_full_channel_restart_allows_regeneration_after_verified_deletion(self) -> None:
        class RestartStore:
            def get_publication_reset_history(self, job_id: str) -> dict[str, str]:
                return {
                    "reset_group": "full_channel_restart_2026-08-15",
                    "original_video_id": "D-o77HngwOU",
                }

            def get_youtube_publication(self, job_id: str) -> None:
                return None

        candidate = {"id": "curriculum-en-001", "title": "What Is Xiangqi?", "content_type": "definition"}
        with patch("automation_runner.subprocess.run") as render:
            with patch.dict("os.environ", {"YOUTUBE_PUBLISH_ENABLED": "0", "XIANGQI_REVIEW_ONLY": "0"}, clear=False):
                result = run_one(candidate, "en", RestartStore(), "test-run")
        self.assertEqual(result, "curriculum-en-001-en")
        render.assert_called_once()

    def test_individual_remediation_quarantine_still_blocks_regeneration(self) -> None:
        class RemediationStore:
            def get_publication_reset_history(self, job_id: str) -> dict[str, str]:
                return {
                    "reset_group": "en013-grounded-review-regeneration-2026-08-15",
                    "original_video_id": "dw6V8q69hY8",
                }

            def get_youtube_publication(self, job_id: str) -> None:
                return None

        candidate = {"id": "curriculum-en-013", "title": "The Horse and the Horse Leg", "content_type": "rules"}
        with patch("automation_runner.subprocess.run") as render:
            with self.assertRaises(PublicationPendingError):
                run_one(candidate, "en", RemediationStore(), "test-run")
        render.assert_not_called()


if __name__ == "__main__":
    unittest.main()
