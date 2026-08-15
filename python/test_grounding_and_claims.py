from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from director import _fallback, _sanitize_director_data, make_job
from curriculum import DEFAULT_FEN, TEMPLATES
from research_grounding import ResearchGroundingError, attach_research_bundle
from xiangqi_claims import build_position_trace, verify_claims


STANDARD_FEN = "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR r"
HORSE_LESSON_MOVES = [
    {"ply": 1, "from": [1, 9], "to": [2, 7], "piece": "knight", "side": "red"},
    {"ply": 2, "from": [1, 0], "to": [2, 2], "piece": "knight", "side": "black"},
    {"ply": 3, "from": [2, 6], "to": [2, 5], "piece": "pawn", "side": "red"},
]


class GroundingAndClaimsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_required = os.environ.get("XIANGQI_RESEARCH_REQUIRED")
        os.environ["XIANGQI_RESEARCH_REQUIRED"] = "1"

    def tearDown(self) -> None:
        if self.previous_required is None:
            os.environ.pop("XIANGQI_RESEARCH_REQUIRED", None)
        else:
            os.environ["XIANGQI_RESEARCH_REQUIRED"] = self.previous_required

    def test_horse_lesson_moves_are_legal_but_false_block_claim_is_rejected(self) -> None:
        trace = build_position_trace(STANDARD_FEN, HORSE_LESSON_MOVES)
        self.assertTrue(trace["ok"], trace["errors"])
        wrong_claims = {
            3: [{
                "claimType": "horse_leg_block",
                "ply": 3,
                "position": "after",
                "subject": {"at": [2, 2]},
                "target": [4, 3],
                "blocker": {"at": [2, 5]},
                "statement": "The red pawn blocks the black horse leg.",
            }]
        }
        result = verify_claims(STANDARD_FEN, HORSE_LESSON_MOVES, wrong_claims)
        self.assertFalse(result["ok"])
        self.assertTrue(any("Horse Leg is not blocked" in error for error in result["errors"]))

    def test_horse_leg_curriculum_template_is_mechanically_grounded(self) -> None:
        puzzle = {
            "language": "en",
            "fen": STANDARD_FEN,
            "moves": TEMPLATES["horse-leg-block"],
            "title": "The Horse and the Horse Leg",
            "content_type": "rules",
            "position_template": "horse-leg-block",
            "curriculum_lesson_key": "en-013-the-horse-and-blocked-eye",
            "durationInSeconds": 90,
            "analysis_focus": "Show the exact Horse Leg coordinate and the blocked destination.",
            "researchBundle": {"status": "grounded", "sourceHash": "test"},
        }
        clean = _sanitize_director_data(_fallback(puzzle, "en"), "en", puzzle)
        job = make_job("horse-leg-template-test", puzzle, clean)
        self.assertEqual(len(job["moves"]), 7)
        self.assertTrue(job["claimProof"]["ok"], job["claimProof"].get("errors"))
        self.assertEqual(job["claimsByPly"][7][-1]["claimType"], "horse_leg_block")
        self.assertEqual(job["claimsByPly"][7][-1]["subject"]["at"], [2, 2])
        self.assertNotIn("horse eye", str(job).lower())

    def test_legal_move_claim_can_pass_without_inventing_causal_effect(self) -> None:
        claims = {
            index: [{"claimType": "legal_move", "ply": index, "position": "after", "statement": "The supplied move is legal."}]
            for index in (1, 2, 3)
        }
        result = verify_claims(STANDARD_FEN, HORSE_LESSON_MOVES, claims)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(len(result["proofs"]), 3)

    def test_make_job_accepts_grounded_legal_claim(self) -> None:
        puzzle = {
            "language": "en",
            "fen": STANDARD_FEN,
            "content_type": "rules",
            "researchBundle": {"status": "grounded", "sourceHash": "test"},
        }
        director_data = {
            "title": "Legal Pawn Move",
            "narration": "Watch the legal move.",
            "moves": [{
                "ply": 1,
                "from": [0, 6],
                "to": [0, 5],
                "piece": "pawn",
                "side": "red",
                "purpose": "demonstrate the supplied legal move",
                "claims": [{"claimType": "legal_move", "ply": 1, "position": "after", "statement": "The supplied move is legal."}],
            }],
        }
        job = make_job("grounded-claim-test", puzzle, director_data)
        self.assertEqual(job["groundingStatus"], None)
        self.assertTrue(job["claimProof"]["ok"])
        self.assertEqual(job["claimsByPly"][1][0]["claimType"], "legal_move")

    def test_make_job_rejects_causal_language_without_claim(self) -> None:
        puzzle = {
            "language": "en",
            "fen": STANDARD_FEN,
            "content_type": "rules",
            "researchBundle": {"status": "grounded", "sourceHash": "test"},
        }
        director_data = {
            "title": "Horse Leg Test",
            "narration": "Watch the horse rule.",
            "moves": [{
                **HORSE_LESSON_MOVES[0],
                "purpose": "block the opponent",
            }],
        }
        with self.assertRaisesRegex(ValueError, "causal/rule language requires structured Xiangqi claims"):
            make_job("claim-test", puzzle, director_data)

    @patch("research_grounding.requests.get")
    def test_grounding_collects_sources_and_marks_bundle_grounded(self, mock_get) -> None:
        class Response:
            headers = {"content-type": "text/html"}
            text = "World Xiangqi Rules: the board has intersections, a river, palaces. The horse's leg is blocked by an intervening piece. The elephant cannot cross the river. The cannon captures with a screen."

            def raise_for_status(self) -> None:
                return None

        mock_get.return_value = Response()
        with patch.dict(os.environ, {"GOOGLE_GROUNDING_ENABLED": "0", "GOOGLE_GROUNDING_REQUIRED": "0"}, clear=False):
            bundle = attach_research_bundle({"title": "Horse Leg", "content_type": "rules"})["researchBundle"]
        self.assertEqual(bundle["status"], "grounded")
        self.assertTrue(bundle["sourceHash"])
        self.assertIn("horse_leg", bundle["requiredTopics"])
        self.assertTrue(bundle["evidence"]["horse_leg"])

    @patch("research_grounding.requests.post")
    @patch("research_grounding.requests.get")
    def test_google_search_grounding_is_required_and_recorded(self, mock_get, mock_post) -> None:
        class Response:
            headers = {"content-type": "text/html"}
            text = "World Xiangqi Rules: the board has intersections, a river, palaces. The horse's leg is blocked by an intervening piece. The elephant cannot cross the river. The cannon captures with a screen."

            def raise_for_status(self) -> None:
                return None

        class GroundingResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"steps": [{"type": "google_search_call", "arguments": {"queries": ["Xiangqi Horse Leg"]}}, {"type": "model_output", "content": [{"type": "text", "text": "Grounded facts"}]}]}

        mock_get.return_value = Response()
        mock_post.return_value = GroundingResponse()
        with patch.dict(os.environ, {"GOOGLE_GROUNDING_ENABLED": "1", "GOOGLE_GROUNDING_REQUIRED": "1", "GOOGLE_GROUNDING_API_KEY": "test-key"}, clear=False):
            bundle = attach_research_bundle({"title": "Horse Leg", "content_type": "rules"})["researchBundle"]
        self.assertEqual(bundle["googleGrounding"]["status"], "retrieved")
        call = mock_post.call_args
        self.assertEqual(call.kwargs["headers"]["x-goog-api-key"], "test-key")
        self.assertEqual([tool["type"] for tool in call.kwargs["json"]["tools"]], ["google_search", "url_context"])

    @patch("research_grounding.requests.get")
    def test_cache_fallback_preserves_stable_rules_when_https_fails(self, mock_get) -> None:
        mock_get.side_effect = TimeoutError("temporary HTTPS failure")
        with patch.dict(os.environ, {"GOOGLE_GROUNDING_ENABLED": "0", "GOOGLE_GROUNDING_REQUIRED": "0", "RESEARCH_ALLOW_CACHE": "1"}, clear=False):
            bundle = attach_research_bundle({"title": "Horse Leg", "content_type": "rules"})["researchBundle"]
        self.assertEqual(bundle["status"], "grounded")
        self.assertTrue(any(source.get("status") == "cached" for source in bundle["sources"]))
        self.assertTrue(bundle["evidence"]["horse_leg"])

    @patch("research_grounding.requests.get")
    def test_grounding_fails_closed_when_required_topic_is_missing(self, mock_get) -> None:
        class Response:
            headers = {"content-type": "text/html"}
            text = "This page contains unrelated text only."

            def raise_for_status(self) -> None:
                return None

        mock_get.return_value = Response()
        with patch.dict(os.environ, {"GOOGLE_GROUNDING_ENABLED": "0", "GOOGLE_GROUNDING_REQUIRED": "0", "RESEARCH_ALLOW_CACHE": "0"}, clear=False):
            with self.assertRaises(ResearchGroundingError):
                attach_research_bundle({"title": "Horse Leg", "content_type": "rules"})


if __name__ == "__main__":
    unittest.main()
