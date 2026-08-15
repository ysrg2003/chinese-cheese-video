from __future__ import annotations

import json
import os
import re
from typing import Any

from ai_router_bridge import load_router
from timing import estimate_content_duration
from sentence_visual_supervision import expand_narration_segments, validate_sentence_visual_coverage

FOUNDATION_VISUAL_MODES = {"foundation_storyboard", "board_introduction", "setup_overview"}
DISABLED_VISUAL_MODES = {"none", "disabled", "off"}
SUPPORTED_BOARD_PRIMITIVES = {
    "files", "ranks", "all_intersections", "representative_intersections", "point_anchor", "square_contrast", "piece_anchor", "legal_destinations", "path_lines",
    "dim_square_interiors", "brighten_lines", "river_band", "palace_x", "central_files",
    "intersection_pulse", "territory_split", "palace_piece_anchor", "palace_entry_points", "route_constraints",
    "piece_family_anchor", "mirror_setup", "coordinate_endpoints", "notation_sequence",
    "chariot_open_file", "cannon_screen", "horse_leg", "horse_leg_blocker", "horse_leg_target", "source_piece", "legal_path", "played_destination",
    "cannon_target", "legal_l_targets", "pressure_marker", "effect_after", "elephant_eye", "river_limit", "constraint_boundary",
    "battlefield", "two_armies", "generals_goal", "intersections", "river_palaces", "cannon_geometry", "learning_roadmap",
    "board_overview", "army_setup", "piece_movement", "move_path", "attack_line", "defense_zone", "threat_marker",
    "capture_sequence", "before_after", "comparison_split", "game_phase", "question_reveal", "result_summary", "history_timeline",
    "cultural_heritage", "board_identity", "rule_focus", "coordinate_map", "piece_spotlight", "concept_focus", "concept_bridge", "causal_bridge", "general_palace_anchor",
}

ALL_VISUAL_KINDS = {
    "battlefield",
    "two_armies",
    "generals_goal",
    "intersections",
    "river_palaces",
    "cannon_geometry",
    "learning_roadmap",
    "board_overview",
    "army_setup",
    "piece_movement",
    "move_path",
    "attack_line",
    "defense_zone",
    "threat_marker",
    "capture_sequence",
    "cannon_screen",
    "before_after",
    "comparison_split",
    "game_phase",
    "question_reveal",
    "result_summary",
    "history_timeline",
    "cultural_heritage",
    "board_identity",
    "rule_focus",
    "coordinate_map",
    "piece_spotlight",
}
FOUNDATION_ORDER = [
    "battlefield",
    "two_armies",
    "generals_goal",
    "intersections",
    "river_palaces",
    "cannon_geometry",
    "learning_roadmap",
]
ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
CJK_RE = re.compile(r"[\u3400-\u9fff]")

FIRST_LESSON_FALLBACK = [
    {
        "index": 1,
        "visualKind": "battlefield",
        "headline": "The Battlefield",
        "narration": "This is Xiangqi, or Chinese chess: two armies face each other on a battlefield of nine files and ten ranks.",
        "caption": "9 files • 10 ranks",
        "visualInstruction": "Reveal the full 9-by-10 grid and label files and ranks at the edge.",
    },
    {
        "index": 2,
        "visualKind": "two_armies",
        "headline": "Two Armies",
        "narration": "Red begins at the bottom, Black at the top, and both armies start in mirror formation.",
        "caption": "Mirrored armies",
        "visualInstruction": "Tint the two sides, label both armies, and draw small arrows toward the center.",
    },
    {
        "index": 3,
        "visualKind": "generals_goal",
        "headline": "The Goal",
        "narration": "Your mission is to checkmate the opposing General while keeping your own General safe.",
        "caption": "Checkmate the General",
        "visualInstruction": "Spotlight both Generals, add a target line toward the opposing General, and a protective ring around the home General.",
    },
    {
        "index": 4,
        "visualKind": "intersections",
        "headline": "Play on Points",
        "narration": "Unlike Western chess, pieces stand on intersections, so every line and crossing matters.",
        "caption": "Pieces stand on points",
        "visualInstruction": "Pulse all intersections, magnify one cross point, and fade the square interiors.",
    },
    {
        "index": 5,
        "visualKind": "river_palaces",
        "headline": "River and Palaces",
        "narration": "The river divides the board, and each General begins inside a small palace.",
        "caption": "River • Palaces",
        "visualInstruction": "Reveal a river band and gold palace boundaries, then point to both Generals.",
    },
    {
        "index": 6,
        "visualKind": "cannon_geometry",
        "headline": "Cannon Geometry",
        "narration": "The cannon makes Xiangqi distinctive: it captures only by firing through exactly one screen.",
        "caption": "One screen capture",
        "visualInstruction": "Draw a cannon line through one highlighted screen to a target and fade invalid lines.",
    },
    {
        "index": 7,
        "visualKind": "learning_roadmap",
        "headline": "Your Learning Path",
        "narration": "First we map the board, then set up the army, learn the pieces, play games, and build tactics.",
        "caption": "Board → setup → tactics",
        "visualInstruction": "Animate a concise roadmap from board to setup, pieces, moves, games, and tactics.",
    },
]

FOUNDATION_FALLBACK_ZH = [
    {"headline": "棋盘战场", "narration": "这就是中国象棋，双方军队在九路十线的战场上对峙。", "caption": "九路十线", "visualKind": "battlefield", "visualInstruction": "显示完整九路十线棋盘，并标出线路。"},
    {"headline": "两方军队", "narration": "红方在下方，黑方在上方，双方以镜像阵形开始。", "caption": "镜像军队", "visualKind": "two_armies", "visualInstruction": "为双方区域着色，标出红方和黑方的方向。"},
    {"headline": "胜利目标", "narration": "你的目标是将死对方的将，同时保护自己的将。", "caption": "将死对方", "visualKind": "generals_goal", "visualInstruction": "突出两个将，并用目标线说明将死的方向。"},
    {"headline": "交叉点", "narration": "棋子站在交叉点上，而不是格子里面，所以线路和交叉点都很重要。", "caption": "棋子站在点上", "visualKind": "intersections", "visualInstruction": "点亮交叉点，并淡化格子内部。"},
    {"headline": "河界九宫", "narration": "河界分开双方区域，两个将都从自己的九宫开始。", "caption": "河界与九宫", "visualKind": "river_palaces", "visualInstruction": "高亮河界和两个九宫，并标出双方的将。"},
    {"headline": "炮的线路", "narration": "炮必须隔着一个炮架吃子，这种线路几何是中国象棋的特色。", "caption": "隔一子吃子", "visualKind": "cannon_geometry", "visualInstruction": "显示炮、炮架和目标子在同一直线上。"},
    {"headline": "学习路线", "narration": "我们先学棋盘和摆法，再学棋子、走法、完整棋局和战术。", "caption": "从棋盘到战术", "visualKind": "learning_roadmap", "visualInstruction": "显示从棋盘到战术的学习路线。"},
]

VISUAL_DIRECTOR_INSTRUCTIONS = """
You are the visual director for an autonomous Xiangqi video pipeline. Return valid JSON only:
{"scenes":[{"index":1,"segmentIndex":1,"movePly":null,"narration":"natural spoken text when requested","caption":"short cue","visualKind":"one permitted kind","headline":"2 to 6 words","visualInstruction":"one concrete renderer-supported visual action","semanticTags":["specific concept"],"visualPlan":{"mode":"board_overlay","focus":"what the viewer must see","primitives":["renderer primitive"]}}]}

Create exactly one scene for every supplied narration segment. Every scene must make the current spoken idea visible through a board change, highlight, path, arrow, before/after comparison, question, controlled editorial bridge, or result marker. Do not add decorative motion with no teaching purpose. For abstract strategic language, `concept_bridge` is an editorial model only and must be labeled as not being a played move.
 Do not invent a game or move that is absent from the supplied data. Keep move scenes tied to the supplied movePly and coordinates. Keep captions short. Never write commands addressed to an animator as spoken narration. Use only the requested language and never Arabic. Use only renderer-supported primitives; if the sentence is about the river, palaces, pieces, paths, or route limits, choose the matching deterministic board primitives rather than a generic decorative scene.

Permitted visualKind values: battlefield, two_armies, generals_goal, intersections, river_palaces, cannon_geometry, learning_roadmap, board_overview, army_setup, piece_movement, move_path, attack_line, defense_zone, threat_marker, capture_sequence, cannon_screen, before_after, comparison_split, game_phase, question_reveal, result_summary, history_timeline, cultural_heritage, board_identity, rule_focus, coordinate_map, piece_spotlight.
""".strip()

VISUAL_DIRECTOR_INSTRUCTIONS_ZH = """
你是自动化中国象棋视频的视觉导演。只能返回有效 JSON：
{"scenes":[{"index":1,"segmentIndex":1,"movePly":null,"narration":"需要时写自然中文口播","caption":"简短提示","visualKind":"允许的类型","headline":"二到六个字","visualInstruction":"一个具体且可渲染的视觉动作"}]}

每个口播片段必须对应一个场景。每个场景都要用棋盘变化、标记、线路、前后对比、问题或结果标记，让当前讲解变得可见。不要加入没有教学目的的装饰动作，不要创造输入数据中不存在的棋局或走法。走法场景必须使用提供的 movePly 和坐标。字幕要短。口播不能写给动画师的命令。只能使用中文，绝不使用阿拉伯语。
""".strip()


def _is_valid_text(value: Any, language: str, *, min_units: int = 1, max_units: int = 30) -> bool:
    text = str(value or "").strip()
    if not text or ARABIC_RE.search(text):
        return False
    if language == "zh":
        units = len(CJK_RE.findall(text))
        return units >= min_units and units <= max_units
    words = re.findall(r"[A-Za-z][A-Za-z’'-]*", text)
    return not CJK_RE.search(text) and min_units <= len(words) <= max_units


def _language(puzzle: dict[str, Any], job: dict[str, Any]) -> str:
    return "zh" if str(job.get("language") or puzzle.get("language") or "en").lower() in {"zh", "cn", "chinese"} else "en"


def _segment_payload(job: dict[str, Any]) -> list[dict[str, Any]]:
    segments = job.get("narrationSegments") if isinstance(job.get("narrationSegments"), list) else []
    moves = {int(move.get("ply", 0)): move for move in job.get("moves", []) if isinstance(move, dict)}
    payload: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            continue
        move_ply = segment.get("movePly")
        move = moves.get(int(move_ply)) if move_ply is not None else None
        payload.append({
            "segmentIndex": index,
            "kind": segment.get("kind", "intro"),
            "movePhase": segment.get("movePhase"),
            "movePly": move_ply,
            "text": str(segment.get("text") or ""),
            "captionText": str(segment.get("captionText") or ""),
            "move": {key: move.get(key) for key in ("from", "to", "piece", "side", "purpose", "opponentReply", "effect", "claims") if move and key in move},
            "sentenceId": segment.get("sentenceId"),
            "visualIntent": segment.get("visualIntent") or {},
        })
    if not payload:
        payload.append({"segmentIndex": 1, "kind": "intro", "movePly": None, "text": str(job.get("narration") or ""), "captionText": "", "move": {}})
    return payload


STATIC_SCENE_COPY = {
    "history_timeline": {
        "en": ("A Living History", "Show a three-stop timeline above the board: early origins, formal development, and modern Xiangqi."),
        "zh": ("历史脉络", "在棋盘上方显示三段时间线：早期起源、定型发展和现代象棋。"),
    },
    "cultural_heritage": {
        "en": ("Cultural Legacy", "Frame the board centre with a traditional seal motif and spotlight the two Generals as opposing armies."),
        "zh": ("文化传承", "用传统印章纹样框住棋盘中央，并突出双方的将。"),
    },
    "board_identity": {
        "en": ("The Xiangqi Board", "Trace nine files and ten ranks, then brighten the central river so the board structure is immediately visible."),
        "zh": ("象棋棋盘", "描出九路十线，再点亮中间河界，让棋盘结构一目了然。"),
    },
    "rule_focus": {
        "en": ("Rule In Focus", "Place a clear rule ring on the relevant board area and add an allowed-versus-not-allowed direction cue."),
        "zh": ("规则重点", "在相关棋盘区域加上规则光圈，并显示允许与不允许的方向提示。"),
    },
    "coordinate_map": {
        "en": ("Read The Map", "Label files and ranks around the board, then pulse the intersection used in the explanation."),
        "zh": ("读懂坐标", "标出棋盘周围的线路，并脉冲讲解中的交叉点。"),
    },
    "piece_spotlight": {
        "en": ("Piece Spotlight", "Spotlight the named piece on both armies and draw its legal direction or movement geometry."),
        "zh": ("棋子聚焦", "突出双方对应的棋子，并绘制它的合法走向或移动几何。"),
    },
    "board_overview": {
        "en": ("Board Overview", "Outline the playable grid and light the exact board region named in the explanation."),
        "zh": ("棋盘概览", "勾勒可走的棋盘网格，并点亮口播提到的棋盘区域。"),
    },
    "army_setup": {
        "en": ("Army Formation", "Tint the Red and Black starting zones separately and reveal their mirrored setup."),
        "zh": ("军队阵形", "分别染色红黑双方的起始区域，并显示镜像摆法。"),
    },
    "two_armies": {
        "en": ("Two Armies", "Split the board into Black and Red territory and guide both armies toward the river."),
        "zh": ("两方军队", "将棋盘分为黑方与红方区域，并引导双方朝河界推进。"),
    },
    "intersections": {
        "en": ("Play On Points", "Pulse the intersections and fade the square interiors to show where pieces actually stand."),
        "zh": ("落子交叉点", "脉冲交叉点并淡化格内区域，显示棋子实际落点。"),
    },
    "river_palaces": {
        "en": ("River And Palaces", "Highlight the river band and both palace boundaries, then point to the two Generals."),
        "zh": ("河界与九宫", "高亮河界和两个九宫边界，再指向双方的将。"),
    },
    "cannon_geometry": {
        "en": ("Cannon Geometry", "Draw a cannon line through exactly one screen to its target and fade invalid capture lines."),
        "zh": ("炮的线路", "画出炮隔一个炮架到目标的线路，并淡化无效吃子线。"),
    },
    "generals_goal": {
        "en": ("Protect The General", "Spotlight both Generals, draw a target line toward the opponent, and add a protective ring at home."),
        "zh": ("保护自己的将", "突出双方的将，画出攻击对方的目标线，并给己方将加保护圈。"),
    },
    "learning_roadmap": {
        "en": ("What Comes Next", "Animate a short learning path from board knowledge through setup, pieces, moves, games, and tactics."),
        "zh": ("接下来学什么", "展示从棋盘、摆法、棋子、走法到对局和战术的学习路线。"),
    },
}


def _lesson_profile(puzzle: dict[str, Any], job: dict[str, Any]) -> str:
    context = " ".join(str(value or "") for value in (
        puzzle.get("curriculum_lesson_key"), job.get("title"), puzzle.get("title"),
        job.get("objective"), puzzle.get("objective"), job.get("content_type"), puzzle.get("content_type"),
    )).lower()
    if any(token in context for token in ("history", "origin", "ancient", "dynasty", "centur", "evolution", "heritage")):
        return "history"
    if any(token in context for token in ("coordinate", "rank", "file", "point", "intersection")):
        return "coordinates"
    if any(token in context for token in ("setup", "formation", "starting position", "arrange")):
        return "setup"
    if any(token in context for token in ("piece", "rook", "horse", "elephant", "advisor", "cannon", "pawn", "general")):
        return "pieces"
    if any(token in context for token in ("rule", "legal", "cannot", "must", "palace", "river")):
        return "rules"
    if any(token in context for token in ("board", "battlefield", "nine", "ten")):
        return "board"
    return "definition"


def _static_kind_for(segment: dict[str, Any], index: int, profile: str) -> str:
    text = " ".join(str(segment.get(key) or "") for key in ("text", "captionText", "kind")).lower()
    keyword_kinds = (
        (("river", "palace", "九宫", "河界"), "river_palaces"),
        (("cannon", "screen", "炮架", "炮"), "cannon_geometry"),
        (("general", "checkmate", "将死", "帅", "将"), "generals_goal"),
        (("army", "armies", "red", "black", "军队", "红方", "黑方"), "two_armies"),
        (("intersection", "point", "crossing", "交叉", "落点"), "intersections"),
        (("file", "rank", "coordinate", "坐标", "线路"), "coordinate_map"),
        (("rook", "horse", "elephant", "advisor", "pawn", "piece", "棋子", "车", "马", "相", "士", "兵"), "piece_spotlight"),
        (("rule", "legal", "must", "cannot", "规则", "必须", "不能"), "rule_focus"),
        (("next", "learn", "roadmap", "接下来", "学习"), "learning_roadmap"),
    )
    for markers, visual_kind in keyword_kinds:
        if any(marker in text for marker in markers):
            return visual_kind
    profile_orders = {
        "history": ("board_overview", "cultural_heritage", "history_timeline", "army_setup", "learning_roadmap"),
        "definition": ("board_identity", "two_armies", "generals_goal", "intersections", "learning_roadmap"),
        "board": ("board_identity", "intersections", "coordinate_map", "river_palaces", "learning_roadmap"),
        "coordinates": ("coordinate_map", "intersections", "board_identity", "river_palaces", "learning_roadmap"),
        "setup": ("army_setup", "two_armies", "board_identity", "river_palaces", "learning_roadmap"),
        "pieces": ("piece_spotlight", "rule_focus", "board_overview", "intersections", "learning_roadmap"),
        "rules": ("rule_focus", "board_identity", "river_palaces", "generals_goal", "learning_roadmap"),
    }
    order = profile_orders.get(profile, profile_orders["definition"])
    return order[(index - 1) % len(order)]


def _semantic_visual_contract(segment: dict[str, Any], default_kind: str, language: str) -> dict[str, Any]:
    text = " ".join(str(segment.get(key) or "") for key in ("text", "captionText", "kind")).lower()
    move = segment.get("move") if isinstance(segment.get("move"), dict) else {}
    if segment.get("movePly") is not None and move:
        piece = str(move.get("piece") or "piece").lower()
        phase = str(segment.get("movePhase") or ("action" if segment.get("kind") == "move" else "effect"))
        piece_label = piece.title()
        base_headline = f"Move {segment.get('movePly') or 1} • {piece_label}" if language == "en" else f"第{segment.get('movePly') or 1}手 • {piece}"
        focus_piece = piece if piece in {"king", "advisor", "bishop", "knight", "rook", "cannon", "pawn"} else None
        if phase == "reply":
            return {
                "visualKind": "threat_marker",
                "headline": f"{base_headline} • Reply" if language == "en" else f"{base_headline} • 回应",
                "visualInstruction": "Show the opponent-pressure point and legal response choices after the supplied move; do not replay the same move path.",
                "semanticTags": ["move", "reply", piece, "pressure"],
                "visualPlan": {"mode": "board_overlay", "focus": f"opponent reply pressure after move {segment.get('movePly')}", "primitives": ["piece_anchor", "pressure_marker", "legal_destinations"], "focusPiece": focus_piece, "focusSide": move.get("side")},
                "confident": True,
            }
        if phase == "effect":
            return {
                "visualKind": "before_after",
                "headline": f"{base_headline} • Position Change" if language == "en" else f"{base_headline} • 局面变化",
                "visualInstruction": "Show the resulting position around the moved piece and mark the changed defensive or attacking relationship; do not show a second move.",
                "semanticTags": ["move", "effect", piece, "position_change"],
                "visualPlan": {"mode": "board_overlay", "focus": f"position change after move {segment.get('movePly')}", "primitives": ["piece_anchor", "played_destination", "effect_after"], "focusPiece": focus_piece, "focusSide": move.get("side")},
                "confident": True,
            }
        if phase == "constraint":
            move_claims = move.get("claims") if isinstance(move.get("claims"), list) else []
            claim_types = {str(claim.get("claimType") or "") for claim in move_claims if isinstance(claim, dict)}
            if claim_types.intersection({"horse_leg_block", "horse_leg_open"}):
                primitives = ["piece_anchor", "horse_leg", "legal_destinations"]
                kind = "rule_focus"
                tags = ["constraint", "horse", "horse_leg", "legal_geometry"]
                focus = f"verified Horse Leg relation after move {segment.get('movePly')}"
            elif claim_types.intersection({"elephant_eye_block", "elephant_eye_open", "river_limit"}) or piece == "bishop" or any(marker in text for marker in ("elephant", "bishop", "eye", "river")):
                primitives = ["piece_anchor", "elephant_eye", "river_limit"]
                kind = "rule_focus"
                tags = ["constraint", "elephant", "eye", "river_limit"]
                focus = f"verified Elephant Eye or river limit after move {segment.get('movePly')}"
            elif "cannon_screen" in claim_types:
                primitives = ["piece_anchor", "cannon_screen", "cannon_target"]
                kind = "rule_focus"
                tags = ["constraint", "cannon", "screen", "legal_geometry"]
                focus = f"verified Cannon Screen relation after move {segment.get('movePly')}"
            else:
                primitives = ["piece_anchor", "constraint_boundary", "legal_destinations"]
                kind = "defense_zone"
                tags = ["constraint", piece, "legal_geometry"]
                focus = f"{piece} movement constraint after move {segment.get('movePly')}"
            return {
                "visualKind": kind,
                "headline": f"{base_headline} • Rule" if language == "en" else f"{base_headline} • 规则",
                "visualInstruction": "Show the exact piece-specific limitation that explains the spoken consequence, without inventing a move or leaving a generic rule ring.",
                "semanticTags": tags,
                "visualPlan": {"mode": "board_overlay", "focus": focus, "primitives": primitives, "focusPiece": "bishop" if "elephant_eye" in primitives else focus_piece, "focusSide": move.get("side")},
                "confident": True,
            }
        primitives = ["source_piece", "legal_path", "played_destination"]
        if piece == "cannon":
            primitives.extend(["cannon_screen", "cannon_target"])
        if piece == "knight":
            primitives.extend(["horse_leg", "legal_l_targets"])
        return {
            "visualKind": "cannon_screen" if piece == "cannon" else "move_path",
            "headline": base_headline,
            "visualInstruction": "Show the supplied legal move from its source to its destination with a fast animation, then leave the board ready for the explanation beat.",
            "semanticTags": ["move", "action", piece, "legal_geometry"],
            "visualPlan": {"mode": "board_overlay", "focus": f"legal {piece} action", "primitives": primitives, "focusPiece": focus_piece, "focusSide": move.get("side")},
            "confident": True,
        }

    def contract(kind: str, headline: str, instruction: str, tags: list[str], primitives: list[str], focus_piece: str | None = None, mode: str = "board_overlay", focus_side: str | None = None) -> dict[str, Any]:
        plan: dict[str, Any] = {"mode": mode, "focus": headline.lower(), "primitives": primitives}
        if focus_piece:
            plan["focusPiece"] = focus_piece
        if focus_side:
            plan["focusSide"] = focus_side
        return {"visualKind": kind, "headline": headline, "visualInstruction": instruction, "semanticTags": tags, "visualPlan": plan, "confident": True}

    intent = segment.get("visualIntent") if isinstance(segment.get("visualIntent"), dict) else {}
    intent_treatment = str(intent.get("visualTreatment") or "").strip()
    if intent_treatment == "multi_constraint":
        return contract("rule_focus", "Three Movement Constraints", "Show the verified Chariot open file, Cannon one-screen line, and Horse Leg blocker together as three labeled constraints; do not invent a move.", ["multi_constraint", "chariot", "cannon", "horse", "claim_proof"], ["chariot_open_file", "cannon_screen", "cannon_target", "horse_leg", "horse_leg_blocker", "horse_leg_target"])
    if intent_treatment == "horse_leg":
        return contract("rule_focus", "Horse Leg Block", "Show the verified Horse Leg geometry only: the teaching Horse, its adjacent leg point, the blocked diagonal target, and a clear occupied-point explanation without inventing a move.", ["horse_leg", "blocked_destination", "claim_proof"], ["horse_leg", "horse_leg_blocker", "horse_leg_target"])
    if intent_treatment == "cannon_screen":
        return contract("cannon_screen", "Cannon Screen", "Show the Cannon, exactly one screen, and the target line from the verified teaching geometry; do not add a second screen.", ["cannon_screen", "one_screen", "claim_proof"], ["piece_anchor", "cannon_screen", "cannon_target"], focus_piece="cannon")
    if intent_treatment == "elephant_eye":
        return contract("rule_focus", "Elephant Eye", "Show the Elephant, its eye point, and the river boundary using the verified Elephant Eye geometry; do not invent a move.", ["elephant_eye", "river_limit", "claim_proof"], ["piece_anchor", "elephant_eye", "river_limit"], focus_piece="bishop")

    if any(marker in text for marker in ("history", "historical", "origin", "origins", "centuries", "dynasty", "tradition", "culture", "heritage", "历史", "传统", "文化")):
        return contract("history_timeline", "History In Context", "Show a restrained three-stop history timeline while keeping the canonical Xiangqi board unchanged; a masked reference edit may add only a localized historical texture or inset.", ["history", "timeline", "context"], ["timeline", "board_reference"], mode="reference_edit")
    if ("thirty-two" in text or "32" in text) and "piece" in text and any(marker in text for marker in ("mirrored", "starting", "arrangement", "setup")):
        return contract("army_setup", "Mirrored Starting Setup", "Keep the full initial board still, tint the two sides separately, mark the mirror axis, and anchor each piece family at its real starting home.", ["setup", "mirror", "thirty_two_pieces", "starting_arrangement"], ["piece_family_anchor", "mirror_setup"])
    if ("one general" in text and "two advisors" in text) or ("starting homes" in text and any(marker in text for marker in ("pieces", "family", "chariots", "horses", "cannons", "soldiers"))):
        return contract("army_setup", "Piece Families And Homes", "Hold the canonical starting position and ring each named piece family at its exact home: General, Advisors, Elephants, Horses, Chariots, Cannons, and Soldiers.", ["setup", "piece_families", "starting_homes", "inventory"], ["piece_family_anchor"])
    if any(marker in text for marker in ("chariots begin", "horses stand", "cannons begin", "soldiers form", "elephants and advisors")):
        return contract("army_setup", "Starting Homes By Family", "Highlight the corners, adjacent Horses, inner Elephants and Advisors, Cannons behind Soldiers, and the Soldier line facing the river on the unchanged board.", ["setup", "chariots", "horses", "elephants", "advisors", "cannons", "soldiers", "river"], ["piece_family_anchor", "river_band", "mirror_setup"])
    if ("file" in text or "files" in text) and any(marker in text for marker in ("open", "road", "active", "route")) and "piece" in text:
        return contract("rule_focus", "Starting Routes And Open Files", "Brighten the central files and outline the two palace regions as route constraints, without inventing a move that is not in the setup data.", ["setup", "files", "routes", "open", "piece_activity", "legal_geometry"], ["central_files", "route_constraints"])
    if ("source point" in text and "destination point" in text) or ("file two" in text and "rank eight" in text) or ("file 2" in text and "rank 8" in text):
        return contract("coordinate_map", "Source To Destination", "Label files and ranks, mark the example source at file 2 rank 8 and destination at file 2 rank 5, and connect them with a neutral notation path without claiming that a game move was played.", ["coordinates", "source", "destination", "notation", "not_a_game"], ["files", "ranks", "coordinate_endpoints"])
    if ("identify the piece" in text or "name where it starts" in text or "name where it ends" in text) and any(marker in text for marker in ("legal", "route", "consistent")):
        return contract("coordinate_map", "Notation Sequence", "Show the four-part replay habit on the actual board: identify the piece, mark its start point, mark its end point, and then show the legal-route check.", ["notation", "piece", "start", "end", "legal_route"], ["coordinate_endpoints", "notation_sequence"])
    if ("visual language" in text or "easy to replay" in text) and any(marker in text for marker in ("precise", "example", "later")):
        return contract("coordinate_map", "Visual Language Foundation", "Combine files, ranks, source and destination points, and a short notation sequence so later examples can be replayed precisely.", ["visual_language", "coordinates", "replay", "precision"], ["files", "ranks", "coordinate_endpoints", "notation_sequence"])
    if ("nine" in text or "9" in text) and ("file" in text or "vertical" in text) and ("ten" in text or "10" in text or "rank" in text):
        return contract("coordinate_map", "Nine Files, Ten Ranks", "Draw all nine vertical files and ten horizontal ranks in sequence, then pulse the 90 legal intersections.", ["files", "ranks", "intersections", "board_geometry"], ["files", "ranks", "all_intersections"])
    if any(marker in text for marker in ("ninety intersections", "90 intersections", "pieces stand on intersections", "pieces stand on those intersections", "stand on intersections", "stand on those intersections", "move travels along the lines", "points and paths")):
        return contract("piece_movement", "Points And Paths", "Select one real red pawn on an intersection, pulse its origin, and show its legal destination points along the board lines.", ["intersections", "piece_anchor", "paths", "legal_destinations"], ["piece_anchor", "legal_destinations", "path_lines"], "pawn", focus_side="red")
    if "river" in text and ("palace" in text or "central files" in text or "divides" in text):
        relation_primitives = ["river_band"]
        relation_tags = ["river"]
        if "palace" in text:
            relation_primitives.append("palace_x")
            relation_tags.append("palaces")
        if "central" in text:
            relation_primitives.append("central_files")
            relation_tags.append("central_zone")
        if any(marker in text for marker in ("territor", "separat", "divid")):
            relation_primitives.append("territory_split")
            relation_tags.append("territories")
        if any(marker in text for marker in ("general", "king", "将", "帅")):
            relation_primitives.append("general_palace_anchor")
            relation_tags.extend(["general", "palace_limits"])
        elif any(marker in text for marker in ("advisor", "adviser", "士", "仕")):
            relation_primitives.append("palace_piece_anchor")
            relation_tags.append("palace_piece_limits")
        return contract("river_palaces", "River, Territories, And Palaces", "Keep the canonical board unchanged; shade the river boundary, distinguish the two territories, outline both palaces, anchor any named Generals inside their palaces, and brighten only the central zone when the narration names it.", relation_tags, list(dict.fromkeys(relation_primitives)))
    if "river" in text and any(marker in text for marker in ("separat", "territor", "soldier", "elephant", "divid")):
        return contract("river_palaces", "River Separates Territories", "Shade the river band, tint the Black and Red territories on opposite sides, and keep the river crossing visible without inventing a move.", ["river", "territories", "soldier", "elephant", "board_geometry"], ["river_band", "territory_split"])
    if "palace" in text and any(marker in text for marker in ("three-by-three", "general", "advisor", "adviser", "zone", "remain")):
        return contract("river_palaces", "Palace: General And Advisors", "Outline both 3-by-3 palaces with their X diagonals and ring the Generals and Advisors that must remain inside them.", ["palace", "general", "advisors", "three_by_three", "palace_limits"], ["palace_x", "palace_piece_anchor"])
    if "palace" in text and any(marker in text for marker in ("entry", "diagonal", "direct-line", "direct line", "danger", "safe corner")):
        return contract("rule_focus", "Palace Entry And Direct Lines", "Highlight the palace X diagonals, the central-file entry points, and the direct lines that make palace access narrow; show no unprovided move.", ["palace", "entry_points", "protected_diagonals", "direct_lines", "legal_geometry"], ["palace_x", "central_files", "palace_entry_points"])
    if "chariot" in text and "cannon" in text and ("horse" in text or "leg" in text):
        return contract("rule_focus", "Three Movement Constraints", "Show three short legal demonstrations: a chariot ray on an open file, a cannon with exactly one screen, and a horse with its leg clear versus blocked.", ["chariot", "cannon", "screen", "horse", "leg"], ["chariot_open_file", "cannon_screen", "horse_leg"])
    if any(marker in text for marker in ("route", "routes", "open", "restricted", "impossible", "predict")) and any(marker in text for marker in ("region", "regions", "palace", "river", "file", "line")):
        return contract("rule_focus", "Region-Based Route Limits", "Keep the river and palaces visible, brighten the central route lanes, and mark the region boundaries that make a route open, restricted, or impossible to evaluate.", ["routes", "open", "restricted", "impossible", "regions", "legal_geometry"], ["river_band", "palace_x", "central_files", "route_constraints"])
    if ("route map" in text or "routes" in text) and ("square" in text or "enclosed" in text or "grid" in text):
        return contract("board_identity", "Board As Route Map", "Dim square interiors, show a small representative sample of intersections, and point to one exact crossing so the board reads as routes rather than enclosed squares.", ["route_map", "intersections", "lines", "not_squares"], ["dim_square_interiors", "brighten_lines", "representative_intersections", "point_anchor", "square_contrast"])
    if "file" in text or "rank" in text or "coordinate" in text:
        return contract("coordinate_map", "Read The Board Map", "Label the files and ranks around the actual board and pulse the intersections named in the narration.", ["files", "ranks", "coordinates"], ["files", "ranks", "intersection_pulse"])
    if "intersection" in text or "point" in text or "crossing" in text:
        return contract("intersections", "Points, Not Squares", "Keep the full board readable, highlight only representative intersections, anchor one exact crossing, and mark one square interior as the contrast; do not imply that every point is an active move target.", ["intersections", "points", "not_squares", "focused_teaching"], ["representative_intersections", "point_anchor", "square_contrast", "dim_square_interiors"])
    if intent_treatment in {"strategic_bridge", "causal_bridge"}:
        default_labels = ["QUIET IDEA", "FORCING IDEA"] if intent_treatment == "strategic_bridge" else ["BASELINE", "EXCHANGE", "INITIATIVE SHIFTS"]
        labels = intent.get("bridgeLabels") if isinstance(intent.get("bridgeLabels"), list) else default_labels
        labels = [str(label).strip()[:24] for label in labels[:3] if str(label).strip()]
        while len(labels) < len(default_labels):
            labels.append(default_labels[len(labels)])
        primitive = "causal_bridge" if intent_treatment == "causal_bridge" else "concept_bridge"
        headline = "Causal Initiative Shift" if intent_treatment == "causal_bridge" else "Strategic Contrast"
        return {
            "visualKind": "comparison_split",
            "headline": headline,
            "visualInstruction": "Show a controlled editorial model that mirrors the spoken causal sequence while keeping the canonical board unchanged; explicitly label it as not a played move.",
            "semanticTags": ["abstract_concept", intent_treatment, "editorial_model", "not_a_move"],
            "visualPlan": {"mode": "board_overlay", "focus": str(intent.get("concept") or headline), "primitives": [primitive], "bridgeLabels": labels},
            "confident": True,
        }
    fallback_profile = str(segment.get("_fallbackProfile") or "").strip()
    protected_progression_kind = default_kind in {"two_armies", "learning_roadmap"} and fallback_profile in {"history", "board", "coordinates", "setup", "pieces", "rules"}
    if intent and intent_treatment == "concept_focus" and protected_progression_kind:
        return {"visualKind": default_kind, "semanticTags": [default_kind], "visualPlan": {"mode": "board_overlay", "focus": default_kind, "primitives": [default_kind]}, "confident": False}
    if intent and intent_treatment != "concept_focus" and default_kind not in {"board_overview", "board_identity", "static_board"}:
        return {"visualKind": default_kind, "semanticTags": [default_kind], "visualPlan": {"mode": "board_overlay", "focus": default_kind, "primitives": [default_kind]}, "confident": False}
    if intent:
        concept = str(intent.get("concept") or "new concept").strip()
        role = str(intent.get("semanticRole") or "concept_explanation").strip()
        treatment = str(intent.get("visualTreatment") or "concept_focus").strip()
        return {
            "visualKind": "board_overview",
            "headline": concept[:28] or "Concept Focus",
            "visualInstruction": "Keep the canonical board visible, focus the camera on the spoken concept, and use only verified board references; do not invent a move.",
            "semanticTags": ["new_concept", role, treatment],
            "visualPlan": {"mode": "board_overlay", "focus": concept or "new concept", "primitives": ["concept_focus"]},
            "confident": True,
        }
    return {"visualKind": default_kind, "semanticTags": [default_kind], "visualPlan": {"mode": "board_overlay", "focus": default_kind, "primitives": [default_kind]}, "confident": False}


def _fallback_for(puzzle: dict[str, Any], job: dict[str, Any]) -> list[dict[str, Any]]:
    language = _language(puzzle, job)
    key = str(puzzle.get("curriculum_lesson_key") or "")
    mode = str(job.get("visual_mode") or puzzle.get("visual_mode") or "")
    if mode in FOUNDATION_VISUAL_MODES or key == "en-001-what-is-xiangqi":
        if language == "zh":
            return [{"index": index, **scene} for index, scene in enumerate(FOUNDATION_FALLBACK_ZH, start=1)]
        return [dict(scene) for scene in FIRST_LESSON_FALLBACK]

    content_type = str(job.get("content_type") or puzzle.get("content_type") or "definition")
    profile = _lesson_profile(puzzle, job)
    segments = _segment_payload(job)
    fallback: list[dict[str, Any]] = []
    intro_kind = {
        "comparison": "comparison_split",
        "advanced_puzzle": "question_reveal",
        "viewer_challenge": "question_reveal",
        "full_game": "game_phase",
        "endgame": "result_summary",
        "trend_breakdown": "before_after",
        "skill_match": "comparison_split",
    }.get(content_type)
    for index, segment in enumerate(segments, start=1):
        move = segment.get("move") or {}
        is_move = segment.get("kind") == "move" and move
        if is_move:
            piece = str(move.get("piece") or "piece").title()
            kind = "cannon_screen" if piece.lower() == "cannon" else "move_path"
            headline = f"Move {segment.get('movePly') or index} • {piece}" if language == "en" else f"第{segment.get('movePly') or index}手 • {piece}"
            instruction = "Show the supplied move path from its source point to its destination, then hold the destination highlight." if language == "en" else "显示给定棋子从起点到终点的走法线路，然后保留终点高亮。"
        else:
            kind = _static_kind_for(segment, index, profile) if not intro_kind else (intro_kind if index == 1 else _static_kind_for(segment, index, profile))
            headline, instruction = STATIC_SCENE_COPY.get(kind, STATIC_SCENE_COPY["board_overview"])[language]
        caption = str(segment.get("captionText") or headline).strip()
        segment_for_contract = {**segment, "_fallbackProfile": profile}
        semantic = _semantic_visual_contract(segment_for_contract, kind, language)
        if semantic.get("confident"):
            kind = str(semantic.get("visualKind") or kind)
            headline = str(semantic.get("headline") or headline)
            instruction = str(semantic.get("visualInstruction") or instruction)
        fallback.append({
            "index": index,
            "segmentIndex": index,
            "movePly": segment.get("movePly"),
            "visualKind": kind,
            "headline": headline,
            "narration": str(segment.get("text") or "").strip(),
            "caption": caption[:80],
            "visualInstruction": instruction,
            "semanticTags": semantic.get("semanticTags") or [kind],
            "visualPlan": semantic.get("visualPlan") or {"mode": "board_overlay", "focus": kind, "primitives": [kind]},
            "sentenceId": segment.get("sentenceId"),
            "visualIntent": segment.get("visualIntent") or {},
            "_fallbackProfile": profile,
        })
    return fallback


def _request_ai_storyboard(puzzle: dict[str, Any], job: dict[str, Any], store: Any | None = None) -> dict[str, Any] | None:
    router = load_router()
    if router is None:
        return None
    language = _language(puzzle, job)
    system_prompt = VISUAL_DIRECTOR_INSTRUCTIONS_ZH if language == "zh" else VISUAL_DIRECTOR_INSTRUCTIONS
    prompt_payload = {
        "language": language,
        "lesson_key": puzzle.get("curriculum_lesson_key"),
        "title": job.get("title") or puzzle.get("title"),
        "content_type": job.get("content_type") or puzzle.get("content_type"),
        "objective": puzzle.get("objective") or job.get("objective"),
        "hook": puzzle.get("hook") or job.get("hook"),
        "analysis_focus": puzzle.get("analysis_focus") or job.get("analysis_focus"),
        "researchBundle": job.get("researchBundle") or puzzle.get("researchBundle") or {},
        "claimProof": job.get("claimProof") or {},
        "sentenceVisualIntents": job.get("sentenceVisualIntents") or [],
        "segments": _segment_payload(job),
    }
    try:
        return router.complete_json(
            system_prompt=system_prompt,
            user_prompt=json.dumps(prompt_payload, ensure_ascii=False),
            operation=f"visual_director:{puzzle.get('curriculum_lesson_key') or job.get('id')}",
            chain="default",
        )
    finally:
        router.close()


def _raw_scenes(raw: Any) -> list[dict[str, Any]] | None:
    if isinstance(raw, dict) and isinstance(raw.get("scenes"), list):
        return [scene for scene in raw["scenes"] if isinstance(scene, dict)]
    if isinstance(raw, list):
        return [scene for scene in raw if isinstance(scene, dict)]
    return None


def _normalize_storyboard(raw: Any, puzzle: dict[str, Any], job: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    language = _language(puzzle, job)
    fallback = _fallback_for(puzzle, job)
    candidates = _raw_scenes(raw)
    if not candidates or len(candidates) != len(fallback):
        return fallback, "fallback"
    normalized: list[dict[str, Any]] = []
    foundation = str(job.get("visual_mode") or puzzle.get("visual_mode") or "") in FOUNDATION_VISUAL_MODES
    moves_by_ply = {int(move.get("ply")): move for move in job.get("moves", []) if isinstance(move, dict) and move.get("ply") is not None}
    for index, default in enumerate(fallback, start=1):
        candidate = candidates[index - 1]
        narration = str(candidate.get("narration") or default.get("narration") or "").strip()
        caption = str(candidate.get("caption") or default.get("caption") or "").strip()
        headline = str(candidate.get("headline") or default.get("headline") or "").strip()
        instruction = str(candidate.get("visualInstruction") or default.get("visualInstruction") or "").strip()
        visual_kind = str(candidate.get("visualKind") or default.get("visualKind") or "")
        if not _is_valid_text(narration, language, min_units=5 if language == "zh" else 4, max_units=34):
            narration = default.get("narration", "")
        if not _is_valid_text(caption, language, min_units=1, max_units=12):
            caption = default.get("caption", headline)
        if not _is_valid_text(headline, language, min_units=1, max_units=8):
            headline = default.get("headline", "Xiangqi")
        if not _is_valid_text(instruction, language, min_units=3 if language == "en" else 5, max_units=60):
            instruction = default.get("visualInstruction", "Highlight the current board idea.")
        if visual_kind not in ALL_VISUAL_KINDS:
            visual_kind = default.get("visualKind", "board_overview")
        if foundation and index <= len(FOUNDATION_ORDER):
            visual_kind = FOUNDATION_ORDER[index - 1]
        source_segment = (job.get("narrationSegments") or [{}])[index - 1] if isinstance(job.get("narrationSegments"), list) and len(job.get("narrationSegments")) >= index and isinstance((job.get("narrationSegments") or [{}])[index - 1], dict) else {}
        segment_for_contract = {
            "kind": source_segment.get("kind", "intro"),
            "movePhase": source_segment.get("movePhase"),
            "text": narration,
            "captionText": caption,
            "movePly": candidate.get("movePly", default.get("movePly")),
            "move": moves_by_ply.get(int(candidate.get("movePly", default.get("movePly")))) if candidate.get("movePly", default.get("movePly")) is not None else {},
            "sentenceId": source_segment.get("sentenceId"),
            "visualIntent": source_segment.get("visualIntent") or {},
        }
        semantic = _semantic_visual_contract(segment_for_contract, visual_kind, language)
        if semantic.get("confident") and not foundation:
            visual_kind = str(semantic.get("visualKind") or visual_kind)
            headline = str(semantic.get("headline") or headline)
            instruction = str(semantic.get("visualInstruction") or instruction)
        normalized.append({
            "index": index,
            "segmentIndex": int(candidate.get("segmentIndex") or default.get("segmentIndex") or index),
            "movePly": candidate.get("movePly", default.get("movePly")),
            "movePhase": source_segment.get("movePhase"),
            "visualKind": visual_kind,
            "headline": headline,
            "narration": narration,
            "caption": caption,
            "visualInstruction": instruction,
            "semanticTags": semantic.get("semanticTags") or candidate.get("semanticTags") or default.get("semanticTags") or [visual_kind],
            "visualPlan": semantic.get("visualPlan") or candidate.get("visualPlan") or default.get("visualPlan") or {"mode": "board_overlay", "focus": visual_kind, "primitives": [visual_kind]},
            "sentenceId": candidate.get("sentenceId") or default.get("sentenceId"),
            "visualIntent": candidate.get("visualIntent") or default.get("visualIntent") or source_segment.get("visualIntent") or {},
            "_fallbackProfile": _lesson_profile(puzzle, job),
        })
    return normalized, "ai_router"


REQUIRED_PRIMITIVE_VISUAL_KIND: dict[str, str] = {
    "horse_leg": "rule_focus",
    "horse_leg_blocker": "rule_focus",
    "horse_leg_target": "rule_focus",
    "cannon_screen": "cannon_screen",
    "elephant_eye": "rule_focus",
    "river_limit": "rule_focus",
}


RELATION_PRIMITIVE_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "river_separates_territories": ("river_band", "territory_split"),
    "generals_restricted_to_palaces": ("palace_x", "general_palace_anchor"),
    "palaces_define_central_zone": ("palace_x", "central_files"),
}


def _preserve_intent_relations(job: dict[str, Any], scenes: list[dict[str, Any]], puzzle: dict[str, Any]) -> list[dict[str, Any]]:
    """Repair relation primitives after either AI or fallback storyboard planning.

    The sentence intent is authoritative for entities and relations. Missing
    relation primitives are restored deterministically; no new move or board
    state is invented.
    """
    source_segments = [segment for segment in job.get("narrationSegments", []) if isinstance(segment, dict)]
    language = _language(puzzle, job)
    repaired: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes):
        current = dict(scene)
        source = source_segments[index] if index < len(source_segments) else {}
        current_intent = current.get("visualIntent") if isinstance(current.get("visualIntent"), dict) else {}
        source_intent = source.get("visualIntent") if isinstance(source.get("visualIntent"), dict) else {}
        intent = {**source_intent, **current_intent}
        relations = {str(value) for value in intent.get("relations", []) if str(value).strip()} if isinstance(intent.get("relations"), list) else set()
        intent_treatment = str(intent.get("visualTreatment") or "").strip()
        explicit_required = {str(value) for value in intent.get("requiredPrimitives", []) if str(value).strip()} if isinstance(intent.get("requiredPrimitives"), list) else set()
        if intent_treatment == "concept_focus" and str(current.get("visualKind") or "") not in {"board_overview", "board_identity", "static_board"}:
            explicit_required.discard("concept_focus")
        required = explicit_required | {primitive for relation in relations for primitive in RELATION_PRIMITIVE_REQUIREMENTS.get(relation, ())}
        plan = dict(current.get("visualPlan") or {})
        primitives = [str(value) for value in plan.get("primitives", []) if str(value).strip()]
        missing = [primitive for primitive in required if primitive not in primitives]
        if missing:
            plan["primitives"] = primitives + sorted(missing)
            current["visualPlan"] = plan
            target_kinds = {REQUIRED_PRIMITIVE_VISUAL_KIND[primitive] for primitive in required if primitive in REQUIRED_PRIMITIVE_VISUAL_KIND}
            if target_kinds and (str(current.get("visualKind") or "") in {"board_overview", "board_identity", "piece_spotlight", "comparison_split"} or not str(current.get("visualKind") or "")):
                current["visualKind"] = sorted(target_kinds)[0]
            tags = list(current.get("semanticTags") or [])
            for relation in sorted(relations):
                tag = f"relation:{relation}"
                if tag not in tags:
                    tags.append(tag)
            current["semanticTags"] = tags
            if relations.intersection({"river_separates_territories", "generals_restricted_to_palaces", "palaces_define_central_zone"}):
                current["visualKind"] = "river_palaces"
                current["headline"] = "River, Territories, And Palaces" if language == "en" else "河界、区域与九宫"
                current["visualInstruction"] = "Show the verified river boundary, both territories, both palaces, and the named General restriction on the unchanged canonical board."
        repaired.append(current)
    return repaired


def _attach_scenes_to_segments(job: dict[str, Any], scenes: list[dict[str, Any]]) -> None:
    segments = [dict(segment) for segment in job.get("narrationSegments", []) if isinstance(segment, dict)]
    if not segments:
        segments = [{"kind": "intro", "text": job.get("narration", ""), "captionPosition": "bottom"}]
    by_index = {int(scene.get("segmentIndex", scene.get("index", 0))): scene for scene in scenes}
    for index, segment in enumerate(segments, start=1):
        scene = by_index.get(index) or scenes[min(index - 1, len(scenes) - 1)]
        segment["sceneId"] = scene.get("index", index)
        if scene.get("movePhase"):
            segment["movePhase"] = scene.get("movePhase")
        segment["visualKind"] = scene.get("visualKind", "board_overview")
        segment["headline"] = scene.get("headline", "Xiangqi")
        segment["visualInstruction"] = scene.get("visualInstruction", "Highlight the current board idea.")
        segment["semanticTags"] = list(scene.get("semanticTags") or [segment["visualKind"]])
        segment["visualPlan"] = dict(scene.get("visualPlan") or {"mode": "board_overlay", "focus": segment["visualKind"], "primitives": [segment["visualKind"]]})
        segment["sentenceId"] = scene.get("sentenceId") or segment.get("sentenceId")
        segment["visualIntent"] = dict(scene.get("visualIntent") or segment.get("visualIntent") or {})
        if scene.get("movePly") is not None:
            segment["movePly"] = scene.get("movePly")
        segment["captionText"] = str(scene.get("caption") or segment.get("captionText") or segment.get("text") or "").strip()
        segment.setdefault("captionPosition", "board" if segment.get("kind") == "move" else "bottom")
    job["narrationSegments"] = segments


def add_visual_storyboard(job: dict[str, Any], puzzle: dict[str, Any], store: Any | None = None) -> dict[str, Any]:
    """Attach one meaningful visual beat to every spoken segment in unattended production."""
    mode = str(job.get("visual_mode") or puzzle.get("visual_mode") or "storyboard").strip().lower()
    if mode in DISABLED_VISUAL_MODES or str(puzzle.get("visual_storyboard_enabled", "1")).lower() in {"0", "false", "no"}:
        return job
    foundation = mode in FOUNDATION_VISUAL_MODES
    if not foundation:
        job = expand_narration_segments(job)
        coverage_errors = validate_sentence_visual_coverage(job)
        if coverage_errors:
            raise ValueError("Sentence visual supervision failed: " + "; ".join(coverage_errors))
    raw = puzzle.get("visualStoryboard")
    source_hint = "provided_ai" if raw is not None else ""
    if raw is None and os.getenv("AI_ROUTER_REQUIRE_KEYS", "1").lower() not in {"0", "false", "no"}:
        try:
            raw = _request_ai_storyboard(puzzle, job, store)
        except Exception as exc:
            print(f"Visual director provider failed: {exc}")
    scenes, source = _normalize_storyboard(raw, puzzle, job)
    if not foundation:
        scenes = _preserve_intent_relations(job, scenes, puzzle)
    if source_hint and source == "ai_router":
        source = source_hint
    if foundation:
        job["visual_mode"] = "foundation_storyboard"
        job["visualStoryboard"] = scenes
        job["visualStoryboardSource"] = source
        segments = [
            {
                "kind": "intro",
                "sceneId": scene["index"],
                "visualKind": scene["visualKind"],
                "headline": scene["headline"],
                "text": scene["narration"],
                "captionText": scene["caption"],
                "captionPosition": "bottom",
                "semanticTags": list(scene.get("semanticTags") or [scene["visualKind"]]),
                "visualPlan": dict(scene.get("visualPlan") or {"mode": "board_overlay", "focus": scene["visualKind"], "primitives": [scene["visualKind"]]}),
            }
            for scene in scenes
        ]
        job["narrationSegments"] = segments
        job["narration"] = " ".join(scene["narration"] for scene in scenes)
        job["captions"] = []
        job["durationInSeconds"] = estimate_content_duration(
            job["narration"], [], job.get("language", "en"), requested_duration=float(puzzle.get("target_seconds") or 0) or None
        )
        return job

    job["visual_mode"] = "storyboard"
    job["visualStoryboard"] = scenes
    job["visualStoryboardSource"] = source
    _attach_scenes_to_segments(job, scenes)
    return job


def validate_visual_storyboard(job: dict[str, Any], audio_duration: float | None = None) -> list[str]:
    """Return blocking defects before render/publication; an empty list means valid."""
    mode = str(job.get("visual_mode") or "").strip().lower()
    if mode not in FOUNDATION_VISUAL_MODES and mode != "storyboard":
        return []
    errors: list[str] = []
    supervision_ready = mode == "storyboard" and isinstance(job.get("sentenceVisualSupervision"), dict)
    if supervision_ready:
        errors.extend(validate_sentence_visual_coverage(job))
    strict_semantic_contract = bool(job.get("visualStoryboardSource"))
    scenes = job.get("visualStoryboard")
    segments = [segment for segment in job.get("narrationSegments", []) if isinstance(segment, dict)]
    if not isinstance(scenes, list) or not scenes:
        errors.append("visual storyboard is missing")
        return errors
    if len(scenes) != len(segments):
        errors.append(f"scene_count={len(scenes)} does not match narration_segment_count={len(segments)}")
    allowed = ALL_VISUAL_KINDS
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            errors.append(f"scene_{index} is not an object")
            continue
        if str(scene.get("visualKind") or "") not in allowed:
            errors.append(f"scene_{index} has unsupported visualKind")
        headline = str(scene.get("headline") or "").strip()
        if not headline:
            errors.append(f"scene_{index} has no headline")
        if headline.casefold() == "what changes next":
            errors.append(f"scene_{index} uses the retired generic fallback headline")
        if not str(scene.get("visualInstruction") or "").strip():
            errors.append(f"scene_{index} has no visualInstruction")
        plan = scene.get("visualPlan")
        if strict_semantic_contract and (not isinstance(plan, dict) or str(plan.get("mode") or "") not in {"board_overlay", "reference_edit", "none"}):
            errors.append(f"scene_{index} has no valid visualPlan")
        elif strict_semantic_contract and (not str(plan.get("focus") or "").strip() or not isinstance(plan.get("primitives"), list) or not plan.get("primitives")):
            errors.append(f"scene_{index} visualPlan is not actionable")
        if strict_semantic_contract and isinstance(plan, dict) and str(plan.get("mode") or "") == "board_overlay":
            unknown_primitives = sorted({str(primitive) for primitive in plan.get("primitives", []) if str(primitive) not in SUPPORTED_BOARD_PRIMITIVES})
            if unknown_primitives:
                errors.append(f"scene_{index} visualPlan has unsupported primitives={unknown_primitives}")
            intent_for_scene = scene.get("visualIntent") if isinstance(scene.get("visualIntent"), dict) else {}
            required_primitives = {str(value) for value in intent_for_scene.get("requiredPrimitives", []) if str(value).strip()} if isinstance(intent_for_scene.get("requiredPrimitives"), list) else set()
            if str(intent_for_scene.get("visualTreatment") or "") == "concept_focus" and str(scene.get("visualKind") or "") not in {"board_overview", "board_identity", "static_board"}:
                required_primitives.discard("concept_focus")
            relation_values = {str(value) for value in intent_for_scene.get("relations", []) if str(value).strip()} if isinstance(intent_for_scene.get("relations"), list) else set()
            required_primitives |= {primitive for relation in relation_values for primitive in RELATION_PRIMITIVE_REQUIREMENTS.get(relation, ())}
            missing_required = sorted(required_primitives - {str(value) for value in plan.get("primitives", [])})
            if missing_required:
                errors.append(f"scene_{index} visualPlan dropped required primitives={missing_required}")

        if strict_semantic_contract and (not isinstance(scene.get("semanticTags"), list) or not scene.get("semanticTags")):
            errors.append(f"scene_{index} has no semanticTags")
        asset = scene.get("generatedAsset")
        if asset is not None:
            if not isinstance(asset, dict):
                errors.append(f"scene_{index} generatedAsset is not an object")
            else:
                src = str(asset.get("src") or "")
                role = str(asset.get("assetRole") or "")
                if scene.get("movePly") is not None:
                    errors.append(f"scene_{index} attaches generatedAsset to a move scene")
                if not src.startswith("generated/") or ".." in src:
                    errors.append(f"scene_{index} generatedAsset has unsafe source")
                if role not in {"editorial_backdrop", "historical_inset", "cultural_inset", "concept_inset"}:
                    errors.append(f"scene_{index} generatedAsset has unsupported role")
    move_plies = {int(move.get("ply")) for move in job.get("moves", []) if isinstance(move, dict) and move.get("ply") is not None}
    latest_end = 0.0
    previous_static_kind: str | None = None
    previous_static_signature: tuple[str, str, tuple[str, ...]] | None = None
    fallback_source = str(job.get("visualStoryboardSource") or "") == "fallback"
    for index, segment in enumerate(segments, start=1):
        if supervision_ready and not str(segment.get("sentenceId") or "").strip():
            errors.append(f"segment_{index} has no sentenceId")
        if supervision_ready and not isinstance(segment.get("visualIntent"), dict):
            errors.append(f"segment_{index} has no visualIntent")
        visual_kind = str(segment.get("visualKind") or "")
        if not visual_kind:
            errors.append(f"segment_{index} has no visualKind")
        is_static_segment = segment.get("kind") != "move" and segment.get("movePly") is None
        plan_for_signature = segment.get("visualPlan") if isinstance(segment.get("visualPlan"), dict) else {}
        primitive_signature = tuple(str(value) for value in plan_for_signature.get("primitives", []) if str(value).strip())
        visual_signature = (visual_kind, str(plan_for_signature.get("focus") or ""), primitive_signature)
        if fallback_source and is_static_segment and visual_kind and visual_kind == previous_static_kind:
            concept_focus_changed = "concept_focus" in primitive_signature and visual_signature != previous_static_signature
            if not concept_focus_changed:
                errors.append(f"segment_{index} repeats fallback visualKind={visual_kind} without a visual change")
        if is_static_segment and visual_kind:
            previous_static_kind = visual_kind
            previous_static_signature = visual_signature
        elif not is_static_segment:
            previous_static_kind = None
            previous_static_signature = None
        if segment.get("movePly") is not None and int(segment["movePly"]) not in move_plies:
            errors.append(f"segment_{index} references missing movePly={segment['movePly']}")
        try:
            start = float(segment.get("startSec", 0.0))
            end = float(segment.get("endSec", 0.0))
            if end < start or start < -0.01:
                errors.append(f"segment_{index} has invalid time window")
            latest_end = max(latest_end, end)
        except (TypeError, ValueError):
            errors.append(f"segment_{index} has non-numeric time window")
    if audio_duration and audio_duration > 0 and latest_end > float(audio_duration) + 0.08:
        errors.append(f"latest_scene_end={latest_end:.3f} exceeds_audio_duration={float(audio_duration):.3f}")
    if strict_semantic_contract:
        move_groups: dict[int, list[dict[str, Any]]] = {}
        for segment in segments:
            if segment.get("movePly") is not None:
                move_groups.setdefault(int(segment["movePly"]), []).append(segment)
        required_phases = {"action", "reply", "effect", "constraint"}
        for ply, group in sorted(move_groups.items()):
            phases = {str(item.get("movePhase") or "") for item in group}
            if not required_phases.issubset(phases):
                errors.append(f"movePly={ply} lacks beat phases; required={sorted(required_phases)}, actual={sorted(phases)}")
            total_window = sum(max(0.0, float(item.get("endSec", 0.0)) - float(item.get("startSec", 0.0))) for item in group)
            action_window = sum(max(0.0, float(item.get("endSec", 0.0)) - float(item.get("startSec", 0.0))) for item in group if item.get("movePhase") == "action")
            if total_window > 0 and action_window / total_window > 0.42:
                errors.append(f"movePly={ply} action beat dominates its teaching window: {action_window / total_window:.3f}")
    return errors
