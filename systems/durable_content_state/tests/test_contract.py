from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from systems.durable_content_state import DurableStateStore, candidate_fingerprint


class DurableContentStateTests(unittest.TestCase):
    def test_fingerprint_is_stable(self) -> None:
        payload = {"domainId": "xiangqi", "contentType": "lesson", "language": "en", "title": "The River", "topic": "river"}
        self.assertEqual(candidate_fingerprint(payload), candidate_fingerprint(dict(payload)))

    def test_namespaced_state_is_restart_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "state.db"
            store = DurableStateStore(db_path)
            store.record_variant(fingerprint="fp-1", domain_id="xiangqi", variant_kind="lesson", job_id="job-1", signature={"topic": "river"})
            store.record_variant(fingerprint="fp-1", domain_id="xiangqi", variant_kind="lesson", job_id="job-1", signature={"topic": "river", "revision": 2})
            restored = DurableStateStore(db_path)
            variant = restored.get_variant("fp-1")
            self.assertEqual(variant["job_id"], "job-1")
            self.assertEqual(variant["signature"]["revision"], 2)
            lineage = restored.record_lineage(short_id="short-1", short_fingerprint="short-fp", parent_job_id="job-1", parent_fingerprint="parent-fp", source_kind="lesson", source_start_sec=1, source_end_sec=5, highlight_reason="decision")
            self.assertEqual(lineage["parent_job_id"], "job-1")
            run = restored.record_automation_run(run_id="run-1", domain_id="xiangqi", status="selected", result={"stage": "queue"})
            self.assertEqual(run["result"]["stage"], "queue")


if __name__ == "__main__":
    unittest.main()
