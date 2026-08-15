from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from self_repair import (
    _safe_scene_repairs_from_evidence,
    apply_director_patch,
    classify_failure,
    repair_failure,
    validate_plan,
)


class FakeRouter:
    def __init__(self, response: dict):
        self.response = response

    def complete_json(self, **kwargs):
        return self.response

    def close(self):
        return None


class SelfRepairTests(unittest.TestCase):
    def test_failure_classification_is_stage_aware(self):
        self.assertEqual(classify_failure("ply 3 causal claim has no proof", "director"), "content_claim")
        self.assertEqual(classify_failure("Error loading image with src", "render"), "render")
        self.assertEqual(classify_failure("HTTP 503 temporarily unavailable", "tts"), "tts_audio")
        self.assertEqual(classify_failure("invalid_grant", "publication"), "publication")
        self.assertEqual(classify_failure("prepublication creative review failed: visual storyboard mismatch", "render"), "visual_storyboard")

    def test_plan_rejects_gate_bypass_and_publication_keys(self):
        valid, errors = validate_plan(
            {
                "schema": "xiangqi_self_repair_v1",
                "disposition": "apply_patch",
                "failure_class": "content_claim",
                "patch_type": "director_patch",
                "resume_stage": "director",
                "patch": {"fen": "unsafe"},
            },
            {"failure_class": "content_claim", "affected_stage": "director"},
        )
        self.assertFalse(valid)
        self.assertTrue(any("forbidden" in error for error in errors))

    def test_director_patch_changes_only_allowlisted_move_fields(self):
        original = {
            "title": "Original",
            "moves": [{
                "ply": 1,
                "from": [0, 6],
                "to": [0, 5],
                "piece": "pawn",
                "side": "red",
                "purpose": "unsafe causal sentence",
                "claims": [{"claimType": "legal_move", "ply": 1}],
            }],
        }
        patched = apply_director_patch(
            original,
            {
                "patch": {
                    "replace_move_fields": {
                        "1": {
                            "purpose": "Describe only the legal pawn move.",
                            "claims": [{"claimType": "legal_move", "ply": 1, "position": "after", "statement": "The supplied move is legal."}],
                        }
                    }
                }
            },
        )
        self.assertEqual(patched["moves"][0]["from"], [0, 6])
        self.assertEqual(patched["moves"][0]["to"], [0, 5])
        self.assertEqual(patched["moves"][0]["piece"], "pawn")
        self.assertEqual(patched["moves"][0]["purpose"], "Describe only the legal pawn move.")
        self.assertEqual(original["moves"][0]["purpose"], "unsafe causal sentence")

    def test_two_stage_diagnosis_plan_and_patch_are_checkpointed(self):
        diagnosis_response = {
            "repairable": True,
            "failure_class": "content_claim",
            "root_cause": "The causal sentence is unsupported by claim proof.",
            "diagnosis": "The move is legal but its effect wording is unsafe.",
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
                        "effect": "The position changes; no extra causal claim is made.",
                        "claims": [{"claimType": "legal_move", "ply": 1, "position": "after", "statement": "The supplied move is legal."}],
                    }
                }
            },
        }
        responses = [diagnosis_response, plan_response]

        def router_factory():
            return FakeRouter(responses.pop(0))

        with tempfile.TemporaryDirectory() as directory:
            result = repair_failure(
                job_id="repair-job-en",
                candidate_id="candidate-1",
                attempt=1,
                stage="render",
                error_text="creative critic rejected unsupported causal claim",
                candidate_payload={"language": "en", "fen": "valid", "moves": []},
                director_data={
                    "title": "Repair me",
                    "moves": [{"ply": 1, "from": [0, 6], "to": [0, 5], "piece": "pawn", "side": "red", "effect": "unsafe"}],
                },
                output_root=directory,
                router_factory=router_factory,
            )
            self.assertEqual(result["status"], "patched")
            override = json.loads(Path(result["override_path"]).read_text(encoding="utf-8"))
            self.assertIn("no extra causal claim", override["moves"][0]["effect"])
            checkpoint = Path(result["checkpoint"])
            self.assertTrue(checkpoint.exists())
            checkpoint_payload = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(checkpoint_payload["status"], "patched")
            self.assertEqual(len(responses), 0)

    def test_planner_plan_array_is_normalised_to_visual_scene_patch(self):
        from self_repair import propose_repair_plan

        responses = [{
            "plan": [{
                "action": "patch_director",
                "scene_id": 4,
                "patch": {
                    "visualKind": "rule_focus",
                    "visualInstruction": "Highlight the rook and its legal destinations.",
                    "visualPlan": {"mode": "board_overlay", "focus": "red rook legal destinations", "primitives": ["piece_anchor", "legal_destinations", "threat_marker"]},
                    "semanticTags": ["rook", "legal_geometry"],
                    "headline": "Show Rook Routes",
                },
            }],
            "failure_class": "visual_storyboard",
            "resume_stage": "storyboard",
        }]

        def router_factory():
            return FakeRouter(responses.pop(0))

        plan = propose_repair_plan(
            {"job_id": "wrapper", "attempt": 1},
            {"failure_class": "visual_storyboard", "affected_stage": "storyboard"},
            router_factory,
        )
        self.assertEqual(plan["patch_type"], "visual_scene_patch")
        self.assertEqual(plan["disposition"], "apply_patch")
        self.assertEqual(plan["patch"]["scene_repairs"][0]["sceneId"], 4)

    def test_nested_visual_action_plan_is_normalised(self):
        from self_repair import propose_repair_plan

        responses = [{
            "plan": [{
                "actions": [{"type": "director_patch", "path": "review_context.scene_repairs[0].repair.visualKind", "value": "move_path"}],
            }],
            "failure_class": "content_schema",
            "resume_stage": "director",
        }]

        def router_factory():
            return FakeRouter(responses.pop(0))

        plan = propose_repair_plan(
            {
                "job_id": "nested",
                "attempt": 1,
                "review_context": {"discarded_unsafe_repairs": [{"repair": {"sceneId": 6, "visualKind": "legal_moves", "visualPlan": {"mode": "board_overlay", "focus": "file 1", "primitives": ["piece_anchor"]}}}]},
                "job_context": {"scenes": [{"index": 6, "movePhase": "action", "visualKind": "board_overview", "visualPlan": {"mode": "board_overlay", "focus": "board", "primitives": ["piece_anchor"]}, "move": {"ply": 2, "piece": "rook", "side": "black"}}]},
            },
            {"failure_class": "content_schema", "affected_stage": "director"},
            router_factory,
        )
        self.assertEqual(plan["patch_type"], "visual_scene_patch")
        self.assertEqual(plan["failure_class"], "content_schema")
        self.assertEqual(plan["patch"]["scene_repairs"][0]["visualKind"], "move_path")

    def test_field_path_visual_repair_plan_is_normalised(self):
        from self_repair import propose_repair_plan

        responses = [{
            "repair_plan": [{
                "patch_type": "director_patch",
                "scene_id": 6,
                "field_path": "visualPlan.focusSide",
                "value": "black",
            }],
            "failure_class": "visual_storyboard",
            "resume_stage": "storyboard",
        }]

        def router_factory():
            return FakeRouter(responses.pop(0))

        plan = propose_repair_plan(
            {
                "job_id": "field-path",
                "attempt": 1,
                "job_context": {"scenes": [{"index": 6, "visualPlan": {"mode": "board_overlay", "focus": "file 1", "primitives": ["piece_anchor"]}}]},
            },
            {"failure_class": "visual_storyboard", "affected_stage": "storyboard"},
            router_factory,
        )
        self.assertEqual(plan["patch_type"], "visual_scene_patch")
        self.assertEqual(plan["patch"]["scene_repairs"][0]["visualPlan"]["focusSide"], "black")
        self.assertEqual(plan["patch"]["scene_repairs"][0]["visualPlan"]["primitives"], ["piece_anchor"])

    def test_bounded_visual_adapter_builds_safe_repair_from_rejected_ai_scene(self):
        evidence = {
            "review_context": {
                "discarded_unsafe_repairs": [{
                    "repair": {
                        "sceneId": 6,
                        "visualKind": "legal_moves",
                        "visualInstruction": "Highlight the rook and its legal paths.",
                        "visualPlan": {"mode": "board_overlay", "focus": "file 1 rook routes", "primitives": ["highlight_file_0", "piece_anchor", "legal_destinations"]},
                    }
                }]
            },
            "job_context": {
                "scenes": [{
                    "index": 6,
                    "movePly": 2,
                    "movePhase": "action",
                    "visualKind": "board_overview",
                    "visualPlan": {"focus": "board overview"},
                    "move": {"ply": 2, "piece": "rook", "side": "black"},
                }]
            },
        }
        repairs = _safe_scene_repairs_from_evidence(evidence, {"failure_class": "visual_storyboard"})
        self.assertEqual(len(repairs), 1)
        self.assertEqual(repairs[0]["visualKind"], "move_path")
        self.assertEqual(repairs[0]["visualPlan"]["focusPiece"], "rook")
        self.assertEqual(repairs[0]["visualPlan"]["focusSide"], "black")
        self.assertNotIn("highlight_file_0", repairs[0]["visualPlan"]["primitives"])

    def test_visual_scene_patch_is_written_as_separate_override(self):
        diagnosis_response = {
            "repairable": True,
            "failure_class": "visual_storyboard",
            "root_cause": "The reply scene is too generic.",
            "diagnosis": "A protected scene repair can make the visual plan concrete.",
            "affected_stage": "storyboard",
        }
        plan_response = {
            "schema": "xiangqi_self_repair_v1",
            "disposition": "apply_patch",
            "failure_class": "visual_storyboard",
            "patch_type": "visual_scene_patch",
            "resume_stage": "storyboard",
            "patch": {
                "scene_repairs": [{
                    "sceneId": 1,
                    "headline": "Show the reply route",
                    "visualInstruction": "Highlight the legal reply destinations for the defending piece.",
                    "visualKind": "threat_marker",
                    "semanticTags": ["reply", "legal_destinations"],
                    "visualPlan": {"mode": "board_overlay", "focus": "defending piece reply routes", "primitives": ["piece_anchor", "legal_destinations"]},
                }]
            },
        }
        responses = [diagnosis_response, plan_response]

        def router_factory():
            return FakeRouter(responses.pop(0))

        with tempfile.TemporaryDirectory() as directory:
            result = repair_failure(
                job_id="visual-repair-job-en",
                candidate_id="candidate-visual",
                attempt=1,
                stage="storyboard",
                error_text="visual storyboard validation failed",
                candidate_payload={"language": "en"},
                director_data=None,
                output_root=directory,
                router_factory=router_factory,
            )
            self.assertEqual(result["status"], "patched")
            self.assertEqual(result["override_kind"], "scene")
            payload = json.loads(Path(result["override_path"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["scene_repairs"][0]["sceneId"], 1)

    def test_publication_failure_is_not_sent_to_content_repair(self):
        diagnosis_response = {
            "repairable": True,
            "failure_class": "publication",
            "root_cause": "YouTube publication failed.",
            "diagnosis": "This belongs to reconciliation.",
            "affected_stage": "publication",
        }
        with tempfile.TemporaryDirectory() as directory:
            responses = [diagnosis_response]

            def router_factory():
                return FakeRouter(responses.pop(0))

            result = repair_failure(
                job_id="publication-job-en",
                candidate_id="candidate-2",
                attempt=1,
                stage="publication",
                error_text="invalid_grant from YouTube",
                candidate_payload={"language": "en"},
                director_data=None,
                output_root=directory,
                router_factory=router_factory,
            )
            self.assertEqual(result["status"], "quarantined")
            self.assertEqual(result["plan"]["patch_type"], "no_safe_repair")


if __name__ == "__main__":
    unittest.main()
