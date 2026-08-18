from __future__ import annotations

import json
from pathlib import Path
import unittest


class ConfigDrivenAutomationContractTests(unittest.TestCase):
    def test_contract_is_portable_and_versioned(self) -> None:
        path = Path(__file__).resolve().parents[1] / "contract.json"
        contract = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(contract["name"], "config_driven_automation")
        self.assertTrue(contract["inputs"])
        self.assertTrue(contract["outputs"])
        self.assertIn("selected", contract["statuses"])
        self.assertTrue(contract["errors"])


if __name__ == "__main__":
    unittest.main()
