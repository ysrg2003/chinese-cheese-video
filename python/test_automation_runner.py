import argparse
import unittest

from automation_runner import is_reconciliation_only


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


if __name__ == "__main__":
    unittest.main()
