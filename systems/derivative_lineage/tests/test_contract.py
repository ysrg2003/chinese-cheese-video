from __future__ import annotations

import unittest

from systems.derivative_lineage import build_lineage_metadata, parent_fingerprint, unused_windows, window_fingerprint


class DerivativeLineageTests(unittest.TestCase):
    def test_parent_and_window_fingerprints_are_stable(self) -> None:
        parent = {"id": "job-1", "title": "Xiangqi lesson", "metadata": {"fingerprint": "parent-fp", "claim_sources": [{"url": "https://example.invalid/source"}]}}
        self.assertEqual(parent_fingerprint(parent), "parent-fp")
        first = window_fingerprint(parent=parent, start_sec=2, end_sec=8, reason="decision")
        second = window_fingerprint(parent=parent, start_sec=2.0, end_sec=8.0, reason="decision")
        self.assertEqual(first, second)

    def test_metadata_is_preserved_and_windows_are_deduped(self) -> None:
        parent = {"id": "job-1", "metadata": {"claim_sources": ["source"], "custom": "preserve"}}
        fingerprint = window_fingerprint(parent=parent, start_sec=2, end_sec=8, reason="decision")
        metadata = build_lineage_metadata(parent=parent, start_sec=2, end_sec=8, reason="decision", child_id="short-1", child_fingerprint=fingerprint)
        self.assertEqual(metadata["custom"], "preserve")
        self.assertEqual(len(unused_windows(candidates=[{"start_sec": 2, "end_sec": 8, "reason": "decision"}, {"start_sec": 9, "end_sec": 12, "reason": "reply"}], existing=[{"source_start_sec": 2, "source_end_sec": 8, "highlight_reason": "decision"}])), 1)


if __name__ == "__main__":
    unittest.main()
