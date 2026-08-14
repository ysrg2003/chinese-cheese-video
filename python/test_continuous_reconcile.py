import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from continuous_reconcile import parse_args, reconcile_until_complete


class ContinuousReconcileTests(unittest.TestCase):
    def test_output_cli_argument_maps_to_output_path(self) -> None:
        with patch.object(sys, "argv", ["continuous_reconcile.py", "--output", "custom.json"]):
            self.assertEqual(parse_args().output_path, "custom.json")

    def test_retries_until_publication_is_complete(self) -> None:
        reports = iter(
            [
                {"enabled": True, "selected": 1, "published": 0, "failed": 1, "error": "429 uploadRateLimitExceeded"},
                {"enabled": True, "selected": 1, "published": 1, "failed": 0},
            ]
        )
        waits: list[int] = []
        now = [0.0]

        def clock() -> float:
            return now[0]

        def sleep(seconds: int) -> None:
            waits.append(seconds)
            now[0] += seconds

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "reconcile.json"
            status = reconcile_until_complete(
                max_attempts=4,
                initial_delay_seconds=2,
                max_delay_seconds=10,
                max_runtime_minutes=5,
                output_path=output,
                runner=lambda: next(reports),
                sleeper=sleep,
                clock=clock,
            )
            self.assertEqual(status, 0)
            self.assertEqual(waits, [2])
            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "complete")
            self.assertEqual(saved["attempt_count"], 2)

    def test_non_retryable_publication_error_stops_without_waiting(self) -> None:
        waits: list[int] = []
        report = lambda: {
            "enabled": True,
            "selected": 1,
            "published": 0,
            "failed": 1,
            "items": [{"error": "authentication or permission failure: invalid_grant"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "reconcile.json"
            status = reconcile_until_complete(
                max_attempts=5,
                initial_delay_seconds=1,
                max_delay_seconds=4,
                max_runtime_minutes=5,
                output_path=output,
                runner=report,
                sleeper=waits.append,
            )
            self.assertEqual(status, 1)
            self.assertEqual(waits, [])
            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "non_retryable_failure")
            self.assertEqual(saved["attempt_count"], 1)

    def test_unresolved_rate_limit_stops_at_attempt_bound(self) -> None:
        waits: list[int] = []
        reports = lambda: {"enabled": True, "selected": 1, "published": 0, "failed": 1, "error": "429 uploadRateLimitExceeded"}
        now = [0.0]

        def clock() -> float:
            return now[0]

        def sleep(seconds: int) -> None:
            waits.append(seconds)
            now[0] += seconds

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "reconcile.json"
            status = reconcile_until_complete(
                max_attempts=3,
                initial_delay_seconds=1,
                max_delay_seconds=4,
                max_runtime_minutes=5,
                output_path=output,
                runner=reports,
                sleeper=sleep,
                clock=clock,
            )
            self.assertEqual(status, 1)
            self.assertEqual(waits, [1, 2])
            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "retry_window_exhausted")
            self.assertEqual(saved["attempt_count"], 3)


if __name__ == "__main__":
    unittest.main()
