from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

from automation_runner import run_one
from self_repair import repair_failure

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / os.getenv("SELF_REPAIR_TEST_OUTPUT_DIR", "self-repair-output")
OUTPUT.mkdir(parents=True, exist_ok=True)


class ProbeStore:
    def get_publication_reset_history(self, job_id: str):
        return None

    def get_youtube_publication(self, job_id: str):
        return None


class FakeRouter:
    def __init__(self, response: dict):
        self.response = response

    def complete_json(self, **kwargs):
        return self.response

    def close(self):
        return None


def main() -> int:
    job_id = "isolated-self-repair-candidate-en"
    diagnosis_response = {
        "repairable": True,
        "failure_class": "content_claim",
        "root_cause": "The effect wording is not supported by the supplied legal claim.",
        "diagnosis": "Keep the legal move and replace the unsafe causal effect wording.",
        "affected_stage": "director",
    }
    plan_response = {
        "schema": "xiangqi_self_repair_v1",
        "disposition": "apply_patch",
        "failure_class": "content_claim",
        "patch_type": "director_patch",
        "resume_stage": "director",
        "patch": {
            "replace_move_fields": {
                "1": {
                    "effect": "The position changes; no unsupported causal claim is made.",
                    "claims": [{"claimType": "legal_move", "ply": 1, "position": "after", "statement": "The supplied move is legal."}],
                }
            }
        },
    }
    responses = [diagnosis_response, plan_response]

    def router_factory():
        return FakeRouter(responses.pop(0))

    with patch.dict(os.environ, {"SELF_REPAIR_ENABLED": "1", "SELF_REPAIR_MAX_ATTEMPTS": "1", "YOUTUBE_PUBLISH_ENABLED": "0", "XIANGQI_REVIEW_ONLY": "1", "XIANGQI_OUTPUT_ROOT": str(OUTPUT)}, clear=False):
        precomputed = repair_failure(
            job_id=job_id,
            candidate_id="isolated-self-repair-candidate",
            attempt=1,
            stage="director",
            error_text="Xiangqi causal claim verification failed: unsupported effect",
            candidate_payload={"language": "en", "fen": "valid", "moves": ["0,6-0,5"]},
            director_data={"title": "Probe", "moves": [{"ply": 1, "from": [0, 6], "to": [0, 5], "piece": "pawn", "side": "red", "effect": "unsafe"}]},
            output_root=OUTPUT,
            router_factory=router_factory,
        )
        if precomputed.get("status") != "patched":
            raise RuntimeError(f"precomputed self-repair did not patch: {precomputed}")
        calls: list[list[str]] = []
        failed = subprocess.CalledProcessError(1, ["isolated-production"])

        def fake_run(command, **kwargs):
            calls.append(list(command))
            if len(calls) == 1:
                raise failed
            return subprocess.CompletedProcess(command, 0)

        with patch("automation_runner.subprocess.run", side_effect=fake_run) as mocked_run:
            with patch("self_repair.repair_failure", return_value=precomputed):
                result = run_one(
                    {"id": "isolated-self-repair-candidate", "title": "Probe", "content_type": "trend_breakdown", "language": "en", "payload": {"fen": "valid", "moves": ["0,6-0,5"]}},
                    "en",
                    ProbeStore(),
                    "isolated-self-repair-run",
                )

    if result != job_id:
        raise RuntimeError(f"unexpected result={result}")
    if len(calls) != 2:
        raise RuntimeError(f"expected two production calls, got {len(calls)}")
    if "--director-override" not in calls[1]:
        raise RuntimeError(f"second call did not contain director override: {calls[1]}")
    if mocked_run.call_count != 2:
        raise RuntimeError("unexpected subprocess call count")
    if responses:
        raise RuntimeError("diagnosis and repair planner were not both invoked")

    report = {
        "test": "isolated_self_repair_cycle",
        "status": "passed",
        "job_id": job_id,
        "first_attempt": "synthetic production failure",
        "diagnosis_and_plan": "real self_repair contract with fake router responses",
        "second_attempt": "same job_id with validated director override",
        "youtube_publications": 0,
        "output_dir": str(OUTPUT),
        "repair_checkpoint": precomputed.get("checkpoint"),
        "override_path": precomputed.get("override_path"),
    }
    (OUTPUT / "repair-probe-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
