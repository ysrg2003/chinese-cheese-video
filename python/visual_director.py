from __future__ import annotations

import json
import os
import re
from typing import Any

from ai_router_bridge import load_router
from timing import estimate_content_duration

FOUNDATION_VISUAL_MODES = {"foundation_storyboard", "board_introduction", "setup_overview"}
DISABLED_VISUAL_MODES = {"none", "disabled", "off"}
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
{"scenes":[{"index":1,"segmentIndex":1,"movePly":null,"narration":"natural spoken text when requested","caption":"short cue","visualKind":"one permitted kind","headline":"2 to 6 words","visualInstruction":"one concrete renderer-supported visual action"}]}

Create exactly one scene for every supplied narration segment. Every scene must make the current spoken idea visible through a board change, highlight, path, arrow, before/after comparison, question, or result marker. Do not add decorative motion with no teaching purpose. Do not invent a game or move that is absent from the supplied data. Keep move scenes tied to the supplied movePly and coordinates. Keep captions short. Never write commands addressed to an animator as spoken narration. Use only the requested language and never Arabic.

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
            "movePly": move_ply,
            "text": str(segment.get("text") or ""),
            "captionText": str(segment.get("captionText") or ""),
            "move": {key: move.get(key) for key in ("from", "to", "piece", "side", "purpose", "opponentReply", "effect") if move and key in move},
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
        fallback.append({
            "index": index,
            "segmentIndex": index,
            "movePly": segment.get("movePly"),
            "visualKind": kind,
            "headline": headline,
            "narration": str(segment.get("text") or "").strip(),
            "caption": caption[:80],
            "visualInstruction": instruction,
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
        normalized.append({
            "index": index,
            "segmentIndex": int(candidate.get("segmentIndex") or default.get("segmentIndex") or index),
            "movePly": candidate.get("movePly", default.get("movePly")),
            "visualKind": visual_kind,
            "headline": headline,
            "narration": narration,
            "caption": caption,
            "visualInstruction": instruction,
        })
    return normalized, "ai_router"


def _attach_scenes_to_segments(job: dict[str, Any], scenes: list[dict[str, Any]]) -> None:
    segments = [dict(segment) for segment in job.get("narrationSegments", []) if isinstance(segment, dict)]
    if not segments:
        segments = [{"kind": "intro", "text": job.get("narration", ""), "captionPosition": "bottom"}]
    by_index = {int(scene.get("segmentIndex", scene.get("index", 0))): scene for scene in scenes}
    for index, segment in enumerate(segments, start=1):
        scene = by_index.get(index) or scenes[min(index - 1, len(scenes) - 1)]
        segment["sceneId"] = scene.get("index", index)
        segment["visualKind"] = scene.get("visualKind", "board_overview")
        segment["headline"] = scene.get("headline", "Xiangqi")
        segment["visualInstruction"] = scene.get("visualInstruction", "Highlight the current board idea.")
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
    raw = puzzle.get("visualStoryboard")
    source_hint = "provided_ai" if raw is not None else ""
    if raw is None and os.getenv("AI_ROUTER_REQUIRE_KEYS", "1").lower() not in {"0", "false", "no"}:
        try:
            raw = _request_ai_storyboard(puzzle, job, store)
        except Exception as exc:
            print(f"Visual director provider failed: {exc}")
    scenes, source = _normalize_storyboard(raw, puzzle, job)
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
    fallback_source = str(job.get("visualStoryboardSource") or "") == "fallback"
    for index, segment in enumerate(segments, start=1):
        visual_kind = str(segment.get("visualKind") or "")
        if not visual_kind:
            errors.append(f"segment_{index} has no visualKind")
        is_static_segment = segment.get("kind") != "move" and segment.get("movePly") is None
        if fallback_source and is_static_segment and visual_kind and visual_kind == previous_static_kind:
            errors.append(f"segment_{index} repeats fallback visualKind={visual_kind} without a visual change")
        if is_static_segment and visual_kind:
            previous_static_kind = visual_kind
        elif not is_static_segment:
            previous_static_kind = None
        if segment.get("kind") == "move" and segment.get("movePly") is not None and int(segment["movePly"]) not in move_plies:
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
    return errors
