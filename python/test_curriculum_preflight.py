from __future__ import annotations

import unittest

from curriculum_preflight import run_preflight


class CurriculumPreflightTests(unittest.TestCase):
    def test_entire_curriculum_passes_template_and_claim_contracts(self) -> None:
        result = run_preflight()
        self.assertTrue(result["ok"], result["errors"][:10])
        self.assertEqual(result["lesson_count"], 72)
        self.assertEqual(result["template_count"], 10)
        self.assertEqual(result["errors"], [])

    def test_every_template_group_has_at_least_one_validated_lesson_or_is_explicitly_unreferenced(self) -> None:
        result = run_preflight()
        self.assertTrue(result["ok"], result["errors"][:10])
        for template_name, details in result["validated_template_groups"].items():
            self.assertIn("moves", details)
            self.assertIsInstance(details["lessons"], list)


if __name__ == "__main__":
    unittest.main()
