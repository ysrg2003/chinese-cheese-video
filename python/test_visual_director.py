import unittest

from visual_director import FIRST_LESSON_FALLBACK, add_visual_storyboard, validate_visual_storyboard


class VisualDirectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.puzzle = {
            "curriculum_lesson_key": "en-001-what-is-xiangqi",
            "visual_mode": "foundation_storyboard",
            "target_seconds": 55,
            "language": "en",
            "title": "What Is Xiangqi?",
        }
        self.job = {
            "id": "storyboard-test",
            "title": "What Is Xiangqi?",
            "language": "en",
            "visual_mode": "foundation_storyboard",
            "narration": "placeholder",
            "narrationSegments": [],
            "captions": [],
        }

    def test_fallback_storyboard_replaces_static_intro_with_seven_visual_scenes(self) -> None:
        storyboard_job = add_visual_storyboard(dict(self.job), self.puzzle)
        self.assertEqual(storyboard_job["visualStoryboardSource"], "fallback")
        self.assertEqual(len(storyboard_job["visualStoryboard"]), 7)
        self.assertEqual(len(storyboard_job["narrationSegments"]), 7)
        self.assertEqual(storyboard_job["moves"] if "moves" in storyboard_job else [], [])
        self.assertEqual(
            [segment["visualKind"] for segment in storyboard_job["narrationSegments"]],
            [scene["visualKind"] for scene in FIRST_LESSON_FALLBACK],
        )
        self.assertTrue(all(segment["captionPosition"] == "bottom" for segment in storyboard_job["narrationSegments"]))
        self.assertGreater(storyboard_job["durationInSeconds"], 40)

    def test_disabled_job_is_unchanged(self) -> None:
        ordinary = {**self.job, "visual_mode": "none", "narration": "Normal lesson"}
        result = add_visual_storyboard(dict(ordinary), {**self.puzzle, "visual_mode": "none"})
        self.assertEqual(result, ordinary)

    def test_storyboard_validation_passes_for_synced_move(self) -> None:
        job = {
            "visual_mode": "storyboard",
            "visualStoryboard": [{"index": 1, "visualKind": "move_path", "headline": "Move One", "visualInstruction": "Show the supplied path."}],
            "moves": [{"ply": 1, "from": [1, 7], "to": [1, 4]}],
            "narrationSegments": [{"kind": "move", "movePly": 1, "visualKind": "move_path", "startSec": 0.0, "endSec": 4.0}],
        }
        self.assertEqual(validate_visual_storyboard(job, audio_duration=4.0), [])

    def test_storyboard_validation_blocks_generated_asset_on_move_scene(self) -> None:
        job = {
            "visual_mode": "storyboard",
            "visualStoryboard": [{"index": 1, "visualKind": "move_path", "headline": "Move One", "visualInstruction": "Show the supplied path.", "movePly": 1, "generatedAsset": {"src": "generated/example/assets/scene.png", "assetRole": "editorial_backdrop"}}],
            "moves": [{"ply": 1, "from": [1, 7], "to": [1, 4]}],
            "narrationSegments": [{"kind": "move", "movePly": 1, "visualKind": "move_path", "startSec": 0.0, "endSec": 4.0}],
        }
        errors = validate_visual_storyboard(job, audio_duration=4.0)
        self.assertTrue(any("generatedAsset to a move scene" in error for error in errors))

    def test_storyboard_validation_blocks_scene_past_audio(self) -> None:
        job = {
            "visual_mode": "storyboard",
            "visualStoryboard": [{"index": 1, "visualKind": "move_path", "headline": "Move One", "visualInstruction": "Show the supplied path."}],
            "moves": [{"ply": 1, "from": [1, 7], "to": [1, 4]}],
            "narrationSegments": [{"kind": "move", "movePly": 1, "visualKind": "move_path", "startSec": 0.0, "endSec": 7.0}],
        }
        errors = validate_visual_storyboard(job, audio_duration=5.0)
        self.assertTrue(any("exceeds_audio_duration" in error for error in errors))

    def test_generic_move_job_gets_visual_beat_without_rewriting_audio(self) -> None:
        ordinary = {
            "id": "tactics-test",
            "title": "Cannon Tactic",
            "language": "en",
            "visual_mode": "storyboard",
            "content_type": "tactics",
            "narration": "The cannon opens a forcing line.",
            "moves": [{"ply": 1, "from": [1, 7], "to": [1, 4], "piece": "cannon", "side": "red", "purpose": "open the line"}],
            "narrationSegments": [{"kind": "move", "movePly": 1, "text": "The cannon opens a forcing line.", "captionText": "Open the line", "captionPosition": "board"}],
            "captions": [],
        }
        result = add_visual_storyboard(dict(ordinary), {"language": "en", "content_type": "tactics", "visual_mode": "storyboard"})
        self.assertEqual(result["visual_mode"], "storyboard")
        self.assertEqual(result["narration"], ordinary["narration"])
        self.assertEqual(len(result["visualStoryboard"]), 1)
        self.assertEqual(result["visualStoryboard"][0]["visualKind"], "cannon_screen")
        self.assertEqual(result["narrationSegments"][0]["visualKind"], "cannon_screen")

    def test_move_beats_receive_distinct_semantic_visual_plans(self) -> None:
        job = {
            "id": "move-beat-test",
            "language": "en",
            "visual_mode": "storyboard",
            "content_type": "rules",
            "moves": [{"ply": 1, "from": [2, 9], "to": [4, 7], "piece": "bishop", "side": "red", "purpose": "guard the diagonal", "opponentReply": "block the elephant eye", "effect": "the bishop becomes restricted"}],
            "narrationSegments": [
                {"kind": "move", "movePhase": "action", "movePly": 1, "text": "Move 1. Red elephant moves from file 3, rank 10 to file 5, rank 8."},
                {"kind": "move_reply", "movePhase": "reply", "movePly": 1, "text": "Now watch the reply. The likely response is to block the elephant eye."},
                {"kind": "move_effect", "movePhase": "effect", "movePly": 1, "text": "After that response, the position changes: the bishop becomes restricted."},
                {"kind": "move_constraint", "movePhase": "constraint", "movePly": 1, "text": "The rule to remember is the elephant eye and the river limit."},
            ],
        }
        result = add_visual_storyboard(dict(job), {"visualStoryboard": []})
        self.assertEqual([segment["movePhase"] for segment in result["narrationSegments"]], ["action", "action", "reply", "reply", "effect", "constraint"])
        self.assertEqual([scene["visualKind"] for scene in result["visualStoryboard"]], ["move_path", "move_path", "threat_marker", "threat_marker", "before_after", "rule_focus"])
        self.assertEqual(result["visualStoryboard"][0]["visualPlan"]["primitives"], ["source_piece", "legal_path", "played_destination"])
        self.assertEqual(result["visualStoryboard"][1]["visualPlan"]["primitives"], ["source_piece", "legal_path", "played_destination"])
        self.assertIn("pressure_marker", result["visualStoryboard"][2]["visualPlan"]["primitives"])
        self.assertIn("pressure_marker", result["visualStoryboard"][3]["visualPlan"]["primitives"])
        self.assertIn("effect_after", result["visualStoryboard"][4]["visualPlan"]["primitives"])
        self.assertEqual(result["visualStoryboard"][5]["visualPlan"]["primitives"], ["piece_anchor", "elephant_eye", "river_limit"])

    def test_storyboard_validation_requires_all_move_explanation_beats(self) -> None:
        base_scene = {"index": 1, "visualKind": "move_path", "headline": "Move", "visualInstruction": "Show the legal move.", "semanticTags": ["move"], "visualPlan": {"mode": "board_overlay", "focus": "move", "primitives": ["source_piece"]}}
        job = {
            "visual_mode": "storyboard",
            "visualStoryboardSource": "ai_router",
            "moves": [{"ply": 1, "from": [2, 9], "to": [4, 7]}],
            "visualStoryboard": [base_scene],
            "narrationSegments": [{"kind": "move", "movePly": 1, "startSec": 0.0, "endSec": 5.0, "visualKind": "move_path", "semanticTags": ["move"], "visualPlan": base_scene["visualPlan"]}],
        }
        errors = validate_visual_storyboard(job, audio_duration=5.0)
        self.assertTrue(any("lacks beat phases" in error for error in errors))

    def test_storyboard_validation_rejects_action_dominance(self) -> None:
        phases = [("action", 0.0, 4.0), ("reply", 4.0, 4.3), ("effect", 4.3, 4.6), ("constraint", 4.6, 5.0)]
        scenes = []
        segments = []
        for index, (phase, start, end) in enumerate(phases, start=1):
            plan = {"mode": "board_overlay", "focus": phase, "primitives": ["piece_anchor"]}
            scenes.append({"index": index, "visualKind": "move_path", "headline": phase, "visualInstruction": "Show this teaching beat.", "semanticTags": [phase], "visualPlan": plan, "movePly": 1})
            segments.append({"kind": "move" if phase == "action" else f"move_{phase}", "movePhase": phase, "movePly": 1, "startSec": start, "endSec": end, "visualKind": "move_path", "semanticTags": [phase], "visualPlan": plan})
        errors = validate_visual_storyboard({"visual_mode": "storyboard", "visualStoryboardSource": "ai_router", "moves": [{"ply": 1}], "visualStoryboard": scenes, "narrationSegments": segments}, audio_duration=5.0)
        self.assertTrue(any("action beat dominates" in error for error in errors))

    def test_semantic_visual_plan_tracks_each_technical_sentence(self) -> None:
        job = {
            "id": "semantic-board-test",
            "title": "The 9x10 Point Board",
            "language": "en",
            "visual_mode": "storyboard",
            "content_type": "definition",
            "moves": [],
            "narrationSegments": [
                {"kind": "intro", "text": "A Xiangqi board has nine vertical files and ten horizontal ranks, creating ninety intersections."},
                {"kind": "intro", "text": "The pieces stand on those intersections, and a move travels along the lines between them."},
                {"kind": "intro", "text": "The horizontal river divides the two sides, while the central files connect the battlefield from one palace to the other."},
                {"kind": "intro", "text": "A chariot values an open file, a cannon values a line with the right screen, and a horse needs an unobstructed leg."},
            ],
        }
        result = add_visual_storyboard(dict(job), {"curriculum_lesson_key": "en-005-the-9x10-point-board", "language": "en", "visual_mode": "storyboard"})
        scenes = result["visualStoryboard"]
        self.assertEqual([scene["visualKind"] for scene in scenes], ["coordinate_map", "piece_movement", "river_palaces", "rule_focus"])
        self.assertIn("all_intersections", scenes[0]["visualPlan"]["primitives"])
        self.assertIn("legal_destinations", scenes[1]["visualPlan"]["primitives"])
        self.assertIn("palace_x", scenes[2]["visualPlan"]["primitives"])
        self.assertEqual(set(["chariot_open_file", "cannon_screen", "horse_leg"]), set(scenes[3]["visualPlan"]["primitives"]))
        self.assertTrue(all(scene["semanticTags"] and scene["visualPlan"]["primitives"] for scene in scenes))
        self.assertEqual(validate_visual_storyboard(result), [])

    def test_ai_storyboard_en006_sentences_get_specific_board_contracts(self) -> None:
        texts = [
            "The river separates the red and black territories and changes what soldiers and elephants can do.",
            "Each palace is a three-by-three zone where its general and advisors must remain.",
            "The palace is not just a safe corner: it creates narrow entry points, protected diagonals, and direct-line dangers.",
            "When you can point to those regions immediately, you can predict which routes are open, restricted, or impossible.",
        ]
        job = {
            "id": "en006-ai-storyboard-contract-test",
            "title": "The River and the Two Palaces",
            "language": "en",
            "visual_mode": "storyboard",
            "content_type": "rules",
            "moves": [],
            "narrationSegments": [{"kind": "intro", "text": text} for text in texts],
        }
        raw = [{"index": index, "segmentIndex": index, "narration": text, "caption": "Short cue", "headline": "AI suggestion", "visualInstruction": "Highlight the board."} for index, text in enumerate(texts, start=1)]
        result = add_visual_storyboard(dict(job), {"curriculum_lesson_key": "en-006-the-river-and-palaces", "language": "en", "visual_mode": "storyboard", "visualStoryboard": raw})
        scenes = result["visualStoryboard"]
        self.assertEqual(result["visualStoryboardSource"], "provided_ai")
        self.assertEqual([scene["visualKind"] for scene in scenes], ["river_palaces", "river_palaces", "rule_focus", "rule_focus"])
        self.assertEqual(scenes[0]["visualPlan"]["primitives"], ["river_band", "territory_split"])
        self.assertEqual(scenes[1]["visualPlan"]["primitives"], ["palace_x", "palace_piece_anchor"])
        self.assertEqual(scenes[2]["visualPlan"]["primitives"], ["palace_x", "central_files", "palace_entry_points"])
        self.assertEqual(scenes[3]["visualPlan"]["primitives"], ["river_band", "palace_x", "central_files", "route_constraints"])
        self.assertEqual(validate_visual_storyboard(result), [])

    def test_ai_storyboard_en007_setup_sentences_get_piece_family_contracts(self) -> None:
        texts = [
            "A Xiangqi game begins with thirty-two pieces in a mirrored starting arrangement.",
            "Each side has one general, two advisors, two elephants, two horses, two chariots, two cannons, and five soldiers.",
            "The chariots begin on the corners, the horses stand beside them, the elephants and advisors protect the route toward the general, the cannons begin behind the soldiers, and the soldiers form a line facing the river.",
            "This arrangement explains which files open first and which pieces need a road before they become active.",
        ]
        job = {
            "id": "en007-ai-storyboard-contract-test",
            "title": "Set Up All 32 Pieces",
            "language": "en",
            "visual_mode": "storyboard",
            "content_type": "rules",
            "moves": [],
            "narrationSegments": [{"kind": "intro", "text": text} for text in texts],
        }
        raw = [{"index": index, "segmentIndex": index, "narration": text, "caption": "Short cue", "headline": "AI suggestion", "visualInstruction": "Highlight the board."} for index, text in enumerate(texts, start=1)]
        result = add_visual_storyboard(dict(job), {"curriculum_lesson_key": "en-007-set-up-all-32-pieces", "language": "en", "visual_mode": "storyboard", "visualStoryboard": raw})
        scenes = result["visualStoryboard"]
        self.assertEqual([scene["visualKind"] for scene in scenes], ["army_setup", "army_setup", "army_setup", "rule_focus"])
        self.assertEqual(scenes[0]["visualPlan"]["primitives"], ["piece_family_anchor", "mirror_setup"])
        self.assertEqual(scenes[1]["visualPlan"]["primitives"], ["piece_family_anchor"])
        self.assertEqual(scenes[2]["visualPlan"]["primitives"], ["piece_family_anchor", "river_band", "mirror_setup"])
        self.assertEqual(scenes[3]["visualPlan"]["primitives"], ["central_files", "route_constraints"])
        self.assertEqual(validate_visual_storyboard(result), [])

    def test_ai_storyboard_en008_coordinate_sentences_get_endpoint_contracts(self) -> None:
        texts = [
            "A move therefore has a source point and a destination point, such as file two, rank eight to file two, rank five.",
            "The important habit is consistent: identify the piece, name where it starts, name where it ends, and then explain why the route is legal.",
            "We are building the visual language that will make every later example precise and easy to replay.",
        ]
        job = {
            "id": "en008-ai-storyboard-contract-test",
            "title": "How Xiangqi Coordinates Work",
            "language": "en",
            "visual_mode": "storyboard",
            "content_type": "definition",
            "moves": [],
            "narrationSegments": [{"kind": "intro", "text": text} for text in texts],
        }
        raw = [{"index": index, "segmentIndex": index, "narration": text, "caption": "Short cue", "headline": "AI suggestion", "visualInstruction": "Highlight the board."} for index, text in enumerate(texts, start=1)]
        result = add_visual_storyboard(dict(job), {"curriculum_lesson_key": "en-008-xiangqi-coordinates", "language": "en", "visual_mode": "storyboard", "visualStoryboard": raw})
        scenes = result["visualStoryboard"]
        self.assertEqual([scene["visualKind"] for scene in scenes], ["coordinate_map", "coordinate_map", "coordinate_map"])
        self.assertEqual(scenes[0]["visualPlan"]["primitives"], ["files", "ranks", "coordinate_endpoints"])
        self.assertEqual(scenes[1]["visualPlan"]["primitives"], ["coordinate_endpoints", "notation_sequence"])
        self.assertEqual(scenes[2]["visualPlan"]["primitives"], ["files", "ranks", "coordinate_endpoints", "notation_sequence"])
        self.assertEqual(validate_visual_storyboard(result), [])

    def test_history_fallback_uses_specialized_visual_progression(self) -> None:
        job = {
            "id": "history-test",
            "title": "A Short History of Xiangqi",
            "language": "en",
            "visual_mode": "storyboard",
            "content_type": "definition",
            "narration": "History introduction.",
            "moves": [],
            "captions": [],
            "narrationSegments": [
                {"kind": "intro", "text": "Xiangqi developed across centuries of Chinese culture."},
                {"kind": "intro", "text": "The game became a contest between two disciplined armies."},
                {"kind": "intro", "text": "Its board preserved a distinctive river and palace structure."},
                {"kind": "intro", "text": "Today, players learn the board before the tactics."},
            ],
        }
        result = add_visual_storyboard(dict(job), {"curriculum_lesson_key": "en-002-history-of-xiangqi", "language": "en", "visual_mode": "storyboard"})
        kinds = [scene["visualKind"] for scene in result["visualStoryboard"]]
        self.assertEqual(kinds[0], "history_timeline")
        self.assertIn("two_armies", kinds)
        self.assertIn("river_palaces", kinds)
        self.assertEqual(kinds[-1], "learning_roadmap")
        self.assertNotIn("before_after", kinds)
        self.assertTrue(all(scene["headline"] != "What Changes Next" for scene in result["visualStoryboard"]))
        self.assertEqual(validate_visual_storyboard(result), [])

    def test_definition_fallback_maps_board_terms_to_rendered_visuals(self) -> None:
        job = {
            "id": "definition-test",
            "title": "How the Xiangqi Board Works",
            "language": "en",
            "visual_mode": "storyboard",
            "content_type": "definition",
            "narration": "Board lesson.",
            "moves": [],
            "captions": [],
            "narrationSegments": [
                {"kind": "intro", "text": "The board has nine files and ten ranks."},
                {"kind": "intro", "text": "Pieces stand on intersections, not inside squares."},
                {"kind": "intro", "text": "The river separates the two sides."},
                {"kind": "intro", "text": "Next, we learn the setup."},
            ],
        }
        result = add_visual_storyboard(dict(job), {"curriculum_lesson_key": "en-005-the-9x10-point-board", "language": "en", "visual_mode": "storyboard"})
        self.assertEqual(
            [scene["visualKind"] for scene in result["visualStoryboard"]],
            ["coordinate_map", "piece_movement", "river_palaces", "learning_roadmap"],
        )


if __name__ == "__main__":
    unittest.main()
