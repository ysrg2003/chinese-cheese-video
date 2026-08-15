from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Callable

import requests

from ai_router_bridge import load_router
from timing import clamp_captions, estimate_content_duration, retime_moves
from xiangqi_rules import parse_fen, validate_move_sequence
from xiangqi_claims import suspicious_claim_language, verify_claims
from research_grounding import research_required
from curriculum import piece_learning_intro

SUPPORTED_LANGUAGES = ("en", "zh")
DEFAULT_LANGUAGE = "en"

DIRECTOR_INSTRUCTIONS = {
    "en": """
You are the director of short Xiangqi Chinese-chess videos. Return valid JSON only with this schema:
{
  "title": "short, compelling title",
  "narration": "natural English introduction and bridge only; per-move explanations belong in the move purpose/opponentReply/effect fields",
  "moves": [
    {"ply": 1, "from": [0, 6], "to": [0, 5], "piece": "pawn", "side": "red", "startSec": 2.0, "endSec": 3.0, "label": "move description", "purpose": "why this move is played", "opponentReply": "the likely reply", "effect": "what changed after the reply", "claims": [{"claimType": "legal_move", "ply": 1, "position": "after", "statement": "source-backed or mechanically verified claim"}]}
  ],
  "captions": [{"startSec": 0.0, "endSec": 2.0, "text": "short English caption"}],
  "durationInSeconds": 0
}
Rules: columns are 0..8 and rows are 0..9 from the top of the board. Use only king, advisor, bishop, knight, rook, cannon, pawn and red or black. The supplied researchBundle is mandatory evidence: use it before writing the script and cite source ids in claims. Every causal or rule statement must have at least one structured claim. Allowed claimType values are legal_move, horse_leg_block, horse_leg_open, elephant_eye_block, elephant_eye_open, cannon_screen, river_limit, flying_general, and legal_destinations. A claim must specify ply, position, subject.at when relevant, target or blocker when relevant, and a precise statement. Do not use words such as blocks, blocked, Horse Eye, opens, unblocks, screen, mount, cannot, or river limit unless the corresponding claim is mechanically true in the supplied board trace. For every move, write a natural spoken explanation that includes what the move tries to do, the opponent's likely reply, what changed after that reply, and the next plan. Do not merely list coordinates. Keep each move explanation concise enough for one or two caption lines. Do not force a fixed short duration; the rendering pipeline calculates the final duration from narration, audio, captions, and move count. Do not output Markdown or any text outside JSON. Never output Arabic.
""".strip(),
    "zh": """
你是中国象棋短视频导演。只能返回有效 JSON，格式如下：
{
  "title": "简短、有吸引力的标题",
  "narration": "自然、连贯的中文开场和过渡；每一步的解释写入该步的目的、回应和效果字段",
  "moves": [
    {"ply": 1, "from": [0, 6], "to": [0, 5], "piece": "pawn", "side": "red", "startSec": 2.0, "endSec": 3.0, "label": "走法说明", "purpose": "这步棋的目的", "opponentReply": "对手的可能回应", "effect": "回应后的局面变化"}
  ],
  "captions": [{"startSec": 0.0, "endSec": 2.0, "text": "简短中文字幕"}],
  "durationInSeconds": 0
}
规则：列坐标为 0..8，行坐标为 0..9，从棋盘顶部开始计算。棋子类型只能使用 king、advisor、bishop、knight、rook、cannon、pawn，阵营只能使用 red 或 black。必须先使用 researchBundle 中的来源证据，再写脚本；每个规则或因果陈述都必须有结构化 claim 和精确坐标。马使用 Horse Leg 的概念，不得把马的阻挡称为 Horse Eye。不要输出 Markdown 或 JSON 之外的任何内容。绝不输出阿拉伯语。
""".strip(),
}

FALLBACKS = {
    "en": {
        "title": "The Quiet Trap on the Left Wing",
        "narration": "The first move looks ordinary, but it changes which routes are available. When the natural reply arrives, compare the position before and after. Follow only the legal geometry that the board actually proves.",
        "captions": [
            "The idea starts with a legal move.",
            "The reply changes the position.",
            "Compare the new routes.",
            "Follow the geometry the board proves.",
        ],
        "labels": ["Make the legal move", "The reply", "The position change"],
    },
    "zh": {
        "title": "左翼的安静陷阱",
        "narration": "第一步看起来很普通，但它会改变局面中的可用路线。对手作出自然回应后，比较回应前后的棋盘，只讲棋盘实际证明的合法几何关系。",
        "captions": [
            "这个构想从一手合法的棋开始。",
            "对手的回应改变了局面。",
            "比较新的路线。",
            "只讲棋盘证明的几何关系。",
        ],
        "labels": ["走出合法的一步", "对手回应", "局面变化"],
    },
}


ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
HORSE_EYE_RE = re.compile(r"\bhorse(?:['’]s)?\s+eye\b|\bblocked\s+eye\b", re.IGNORECASE)


def _canonicalize_xiangqi_terms(value: Any) -> Any:
    """Replace the deprecated Horse terminology throughout director payload text."""
    if isinstance(value, str):
        return HORSE_EYE_RE.sub("Horse Leg", value)
    if isinstance(value, list):
        return [_canonicalize_xiangqi_terms(item) for item in value]
    if isinstance(value, dict):
        return {key: _canonicalize_xiangqi_terms(item) for key, item in value.items()}
    return value
CURRICULUM_INTROS = {
    "en-001-what-is-xiangqi": "Xiangqi, often called Chinese chess, is a two-player strategy game played by two armies on a battlefield of nine files and ten ranks. The goal is to checkmate the opposing general, but the path to that goal is shaped by a river, two palaces, open lines, and the special geometry of the cannon. In this first lesson, nothing moves yet. Take a moment to read the starting position: two mirrored armies face one another, each with a general at the center of a palace. The pieces are not placed inside squares; they stand on intersections. That single detail changes how lines, attacks, and defenses work. We will first learn the board, the river, the palaces, the complete setup, and every piece movement. Only after that foundation will we play training positions, opening ideas, tactics, full games, and advanced puzzles.",
    "en-003-a-short-history-of-xiangqi": "Xiangqi has a long Chinese tradition and remains a living strategy game played casually, competitively, and online. Its familiar vocabulary is part of its identity: generals command from palaces, soldiers cross a river, and cannons use a screen to capture. Historians discuss the game’s development across different periods, so we will avoid reducing that history to one unsupported origin story. Instead, notice how the board itself preserves a battlefield language. The two sides begin in mirror formation, the river separates their territories, and the palace gives the generals a protected but restricted home. In the next lessons, we will turn that visual language into practical knowledge: first the board, then the setup, then the movement of each piece.",
    "en-005-the-9x10-point-board": "Before you study a move, learn where a move happens. A Xiangqi board has nine vertical files and ten horizontal ranks, creating ninety intersections. The pieces stand on those intersections, and a move travels along the lines between them. The horizontal river divides the two sides, while the central files connect the battlefield from one palace to the other. Think of the board as a map of routes rather than a collection of enclosed squares. A chariot values an open file, a cannon values a line with the right screen, and a horse needs an unobstructed leg. Keep this starting position on screen and practice seeing the points, files, ranks, and central routes before we play a single training move.",
    "en-006-the-river-and-palaces": "The river and the two palaces are the first special regions to recognize. The river separates the red and black territories and changes what soldiers and elephants can do. Each palace is a three-by-three zone where its general and advisors must remain. The palace is not just a safe corner: it creates narrow entry points, protected diagonals, and direct-line dangers. Later, you will learn the flying-general rule, but for now simply locate both palaces and the river on the still board. When you can point to those regions immediately, many Xiangqi explanations become easier because you can predict which routes are open, restricted, or impossible.",
    "en-007-set-up-all-32-pieces": "A Xiangqi game begins with thirty-two pieces in a mirrored starting arrangement. Each side has one general, two advisors, two elephants, two horses, two chariots, two cannons, and five soldiers. The chariots begin on the corners, the horses stand beside them, the elephants and advisors protect the route toward the general, the cannons begin behind the soldiers, and the soldiers form a line facing the river. This arrangement is not decoration: it explains which files open first and which pieces need a road before they can become active. In this lesson the army stays still. Learn the names and starting homes now; the next lessons will show how each family moves with clear, isolated examples.",
    "en-008-xiangqi-coordinates": "To follow a Xiangqi lesson, you need a simple way to name two points. We will use files one through nine from left to right on the displayed board and ranks one through ten from top to bottom. A move therefore has a source point and a destination point, such as file two, rank eight to file two, rank five. The exact orientation can be stated for the side being discussed, but the important habit is consistent: identify the piece, name where it starts, name where it ends, and then explain why the route is legal. No game is played in this lesson. We are building the visual language that will make every later example precise and easy to replay.",
}

FALLBACK_NARRATION_BY_TYPE = {
    "en": {
        "definition": "The board is more than a grid: the river, palaces, and open files determine which plans are possible. This lesson turns one position into a practical rule you can use immediately.",
        "rules": "One Xiangqi rule changes the value of every move that follows. Learn the rule, see the legal consequence on the board, and use it to avoid a common beginner mistake.",
        "opening": "A strong Xiangqi opening is a plan, not a memorized move list. Develop with purpose, protect the critical line, and watch how the first exchanges shape the middlegame.",
        "tactics": "This tactical pattern begins with a threat that looks small. Count the forcing replies, keep the cannon line open, and calculate the final move before you capture anything.",
        "endgame": "An endgame advantage only matters if you can convert it. Improve the king and remaining pieces, restrict the opponent's choices, and make each final move serve the win.",
        "full_game": "Follow this complete Xiangqi game as a compact story: the opening plan, the turning point, and the final conversion. The goal is to understand why each phase leads to the next.",
        "advanced_puzzle": "Pause before the reveal and search for the forcing sequence. Look for checks, captures, and threats in that order, then compare the winning line with the tempting mistake.",
        "comparison": "Xiangqi shares ideas with other board games, but its river, palaces, and cannon geometry change the calculation. Compare the two systems through one concrete position.",
        "trend_breakdown": "We turn this current Xiangqi topic into a board lesson: identify the key idea, test the natural reply, and follow the tactical change that matters to players.",
        "skill_match": "Two skill profiles meet in this structured Xiangqi lesson. Watch how the stronger plan handles space, tempo, and threats, then take one practical improvement for your own games.",
        "viewer_challenge": "Your move comes first. Pause the position, choose the most forcing continuation, and use the reveal to compare your calculation with the board's best idea.",
    },
    "zh": {
        "definition": "棋盘不只是九条直线：河界、九宫和开放线路决定了计划。这个课程把一个局面变成可以马上使用的实战原则。",
        "rules": "一条中国象棋规则会改变后续每一步的价值。先理解规则，再观察它在棋盘上的结果，避免常见的入门错误。",
        "opening": "好的中国象棋开局不是死记着法，而是清晰的计划。带着目的出子，保护关键线路，观察交换如何影响中局。",
        "tactics": "这个战术从一个看似微小的威胁开始。按将军、吃子和威胁计算，保持炮路畅通，再决定是否交换。",
        "endgame": "残局优势只有转化为胜势才有意义。改善将帅和剩余棋子的协调，限制对手选择，让每一步都服务于胜利。",
        "full_game": "跟随这盘完整棋局，观察开局计划、转折点和最后的取胜过程，理解每个阶段为什么会进入下一个阶段。",
        "advanced_puzzle": "揭晓之前先暂停思考，按将军、吃子和威胁寻找强制手段，再比较最佳变化与诱人的错误。",
        "comparison": "中国象棋与其他棋类有共同思想，但河界、九宫和炮的几何关系改变了计算。通过一个具体局面比较它们。",
        "trend_breakdown": "我们把这个中国象棋热点转化为棋盘课程：找出核心观点，测试自然回应，再观察真正重要的战术变化。",
        "skill_match": "两个水平档次在这堂结构化课程中相遇。观察更强的计划如何处理空间、节奏和威胁，再带走一个实战改进。",
        "viewer_challenge": "先轮到你走。暂停局面，选择最有强制力的续着，再用答案比较自己的计算与最佳思路。",
    },
}


DEFAULT_MOVE_VARIANTS = [
    ["0,6-0,5", "0,3-0,4", "1,7-1,4"],
    ["1,9-2,7", "1,0-2,2", "1,7-1,4"],
    ["1,7-1,4", "2,3-2,4", "7,9-6,7"],
    ["0,9-0,8", "0,0-0,1", "2,6-2,5"],
    ["3,9-4,8", "3,0-4,1", "7,7-7,4"],
]

PIECE_NAMES = {
    "pawn": {"en": "pawn", "zh": "兵"},
    "rook": {"en": "rook", "zh": "车"},
    "knight": {"en": "horse", "zh": "马"},
    "bishop": {"en": "elephant", "zh": "象"},
    "advisor": {"en": "advisor", "zh": "士"},
    "king": {"en": "general", "zh": "将"},
    "cannon": {"en": "cannon", "zh": "炮"},
}


def _coordinate_label(point: Any, language: str) -> str:
    try:
        column, row = int(point[0]), int(point[1])
    except (TypeError, ValueError, IndexError):
        return "the marked square" if language == "en" else "标记位置"
    if language == "zh":
        return f"{column + 1}路{row + 1}行"
    return f"file {column + 1}, rank {row + 1}"


def _move_spoken_text(
    move: dict[str, Any],
    language: str,
    content_type: str,
    analysis_focus: str = "",
) -> tuple[str, str]:
    ply = int(move.get("ply", 1))
    piece = PIECE_NAMES.get(str(move.get("piece", "pawn")), PIECE_NAMES["pawn"])[language]
    side = "red" if str(move.get("side", "red")) == "red" else "black"
    purpose_defaults = {
        "opening": "open a useful line",
        "tactics": "create a forcing threat",
        "endgame": "improve the winning plan",
        "advanced_puzzle": "start the forcing sequence",
        "full_game": "carry out the game plan",
        "comparison": "show the different board geometry",
        "skill_match": "test the opponent's plan",
        "viewer_challenge": "find the best reply",
        "definition": "make the board rule visible",
        "rules": "demonstrate the legal rule",
        "trend_breakdown": "turn the position into a practical lesson",
    }
    purpose = str(move.get("purpose") or move.get("label") or purpose_defaults.get(content_type, "improve the position")).strip().rstrip(".").lower()
    opponent_reply = str(move.get("opponentReply") or ("contest the new line" if side == "red" else "answer the pressure")).strip().rstrip(".").lower()
    effect_defaults = {
        "opening": "the next piece can join the attack",
        "tactics": "the opponent has fewer safe replies",
        "endgame": "the advantage becomes easier to convert",
        "advanced_puzzle": "the forcing sequence becomes visible",
        "full_game": "the game enters its next phase",
        "comparison": "the different board geometry becomes concrete",
        "skill_match": "the stronger plan gains a tempo",
        "viewer_challenge": "the reply becomes the key decision",
        "definition": "the board rule changes the available plans",
        "rules": "the legal rule removes a tempting reply",
        "trend_breakdown": "the practical lesson becomes clear",
    }
    effect = str(move.get("effect") or effect_defaults.get(content_type, "the opponent's choices change")).strip().rstrip(".").lower()
    focus_defaults = {
        "opening": "the plan behind development",
        "tactics": "the forcing replies",
        "endgame": "the conversion technique",
        "advanced_puzzle": "the complete calculation",
        "full_game": "the next phase of the game",
        "comparison": "the difference in board geometry",
        "skill_match": "the quality of the plan",
        "viewer_challenge": "the best reply",
        "definition": "the board rule in action",
        "rules": "the legal consequence",
        "trend_breakdown": "the practical idea",
    }
    focus = focus_defaults.get(content_type, "the next plan")
    source = _coordinate_label(move.get("from"), language)
    target = _coordinate_label(move.get("to"), language)
    if language == "zh":
        spoken = f"第{ply}步，{side}方{piece}从{source}走到{target}，目的是{purpose}。对手很可能{opponent_reply}，这样局面就会{effect}。接下来我们继续关注{focus}。"
        caption = f"第{ply}步：{piece}{source}到{target}——{purpose}。"
    else:
        reply_sentence = f"The likely reply is to {opponent_reply}." if not opponent_reply.startswith(("the ", "a ", "an ", "black ", "red ", "they ", "it ")) else f"The likely reply is {opponent_reply}."
        purpose_sentence = purpose[:1].upper() + purpose[1:] if purpose else "The move improves the position"
        spoken = (
            f"Move {ply}. {side.title()} {piece} moves from {source} to {target}. "
            f"{purpose_sentence}. {reply_sentence} That changes the position: {effect}. "
            f"Next, watch {focus}."
        )
        caption = f"Move {ply}: {piece.title()} {source} → {target}. {purpose.capitalize()}."
    return spoken, caption


def _short_caption(text: str, prefix: str, maximum_words: int = 10) -> str:
    words = str(text or "").strip().rstrip(".").split()
    clipped = " ".join(words[:maximum_words]).strip()
    return f"{prefix}: {clipped}" if clipped else prefix


def _move_beats(move: dict[str, Any], language: str, content_type: str, analysis_focus: str = "") -> list[dict[str, Any]]:
    spoken_text, caption_text = _move_spoken_text(move, language, content_type, analysis_focus)
    ply = int(move.get("ply", 1))
    piece_key = str(move.get("piece") or "pawn")
    piece = PIECE_NAMES.get(piece_key, PIECE_NAMES["pawn"])[language]
    side = "red" if str(move.get("side", "red")) == "red" else "black"
    purpose = str(move.get("purpose") or move.get("label") or "improve the position").strip().rstrip(".")
    reply = str(move.get("opponentReply") or ("contest the new line" if side == "red" else "answer the pressure")).strip().rstrip(".")
    effect = str(move.get("effect") or "the available choices change").strip().rstrip(".")
    focus = str(analysis_focus or "the legal consequence").strip().rstrip(".")
    source = _coordinate_label(move.get("from"), language)
    target = _coordinate_label(move.get("to"), language)
    if language == "zh":
        action_text = f"第{ply}步，{side}方{piece}从{source}走到{target}，目的是{purpose}。"
        reply_text = f"接着看对手的回应：对手很可能{reply}。"
        effect_text = f"回应之后，局面发生变化：{effect}。"
        constraint_text = f"最后记住这个限制：{focus}。"
        reply_caption = _short_caption(reply, "回应")
        effect_caption = _short_caption(effect, "变化")
        constraint_caption = _short_caption(focus, "规则")
    else:
        purpose_sentence = purpose[:1].upper() + purpose[1:] if purpose else "The move improves the position"
        action_text = f"Move {ply}: {side.title()} {piece}, {source} to {target}. {purpose_sentence}."
        reply_text = f"Now watch the reply. The likely response is to {reply}."
        effect_text = f"After that response, the position changes: {effect}."
        constraint_text = f"The rule to remember is {focus}."
        reply_caption = _short_caption(reply, "Likely reply")
        effect_caption = _short_caption(effect, "Position change")
        constraint_caption = _short_caption(focus, "Rule")
    return [
        {"kind": "move", "movePhase": "action", "movePly": ply, "text": action_text, "captionText": caption_text, "captionPosition": "board"},
        {"kind": "move_reply", "movePhase": "reply", "movePly": ply, "text": reply_text, "captionText": reply_caption, "captionPosition": "board"},
        {"kind": "move_effect", "movePhase": "effect", "movePly": ply, "text": effect_text, "captionText": effect_caption, "captionPosition": "board"},
        {"kind": "move_constraint", "movePhase": "constraint", "movePly": ply, "text": constraint_text, "captionText": constraint_caption, "captionPosition": "board"},
    ]


def build_narration_segments(
    base_narration: str,
    moves: list[dict[str, Any]],
    language: str,
    content_type: str,
    analysis_focus: str = "",
    split_intro: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    segments: list[dict[str, Any]] = []
    intro = str(base_narration or "").strip()
    if intro:
        intro_parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", intro) if part.strip()] if split_intro else [intro]
        for intro_part in intro_parts:
            segments.append({"kind": "intro", "text": intro_part, "captionText": intro_part, "captionPosition": "bottom"})
    for move in moves:
        beats = _move_beats(move, language, content_type, analysis_focus)
        move["spokenText"] = " ".join(str(beat["text"]) for beat in beats)
        move["captionText"] = beats[0]["captionText"]
        segments.extend(beats)
    return " ".join(segment["text"] for segment in segments).strip(), segments


def _segment_captions_without_audio(segments: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    if not segments or duration <= 0:
        return []
    weights = [max(1, len(str(segment.get("captionText") or segment.get("text") or "").split())) for segment in segments]
    total = float(sum(weights)) or 1.0
    cursor = 0.0
    captions: list[dict[str, Any]] = []
    for index, (segment, weight) in enumerate(zip(segments, weights)):
        end = duration if index == len(segments) - 1 else cursor + duration * weight / total
        text = str(segment.get("captionText") or segment.get("text") or "").strip()
        if text:
            captions.append({
                "startSec": round(cursor, 3),
                "endSec": round(max(cursor + 0.05, end), 3),
                "text": text,
                "kind": segment.get("kind", "speech"),
                "movePly": segment.get("movePly"),
                "captionPosition": segment.get("captionPosition", "board" if segment.get("kind") == "move" else "bottom"),
                "source": "narration_segments_fallback",
            })
        cursor = end
    return captions


def normalize_language(value: Any) -> str:
    value = str(value or DEFAULT_LANGUAGE).lower().strip()
    if value in {"zh", "cn", "chinese", "中文", "简体中文"}:
        return "zh"
    return "en"


def contains_arabic(value: Any) -> bool:
    return bool(ARABIC_RE.search(str(value or "")))


def _safe_text(value: Any, fallback: str, language: str = "en") -> str:
    text = str(value or "").strip()
    language_mismatch = language == "en" and bool(CJK_RE.search(text))
    return fallback if not text or contains_arabic(text) or language_mismatch else text


def _text_is_invalid(value: Any, language: str) -> bool:
    text = str(value or "")
    return contains_arabic(text) or (language == "en" and bool(CJK_RE.search(text)))


def _strip_code_fences(raw: str) -> str:
    clean = raw.strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*```$", "", clean)
    return clean.strip()


def _request_ai(puzzle: dict[str, Any], language: str, store: Any | None = None, operation: str = "director") -> dict[str, Any] | None:
    router = load_router()
    if router is None:
        return None
    prompt = f"{DIRECTOR_INSTRUCTIONS[language]}\n\nMANDATORY RESEARCH AND GROUNDING BUNDLE:\n{json.dumps(puzzle.get('researchBundle') or {}, ensure_ascii=False)}\n\nPuzzle data:\n{json.dumps(puzzle, ensure_ascii=False)}"
    try:
        return router.complete_json(
            chain=os.getenv("AI_ROUTER_CHAIN", "default"),
            system_prompt=DIRECTOR_INSTRUCTIONS[language],
            user_prompt=prompt,
            operation=operation,
        )
    finally:
        router.close()


def _request_ollama(puzzle: dict[str, Any], language: str) -> dict[str, Any] | None:
    base_url = os.getenv("OLLAMA_BASE_URL")
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    if not base_url:
        return None
    response = requests.post(
        f"{base_url.rstrip('/')}/api/chat",
        json={
            "model": model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": DIRECTOR_INSTRUCTIONS[language]},
                {"role": "user", "content": json.dumps(puzzle, ensure_ascii=False)},
            ],
        },
        timeout=120,
    )
    response.raise_for_status()
    return json.loads(response.json()["message"]["content"])


def _parse_move_token(token: str, ply: int, language: str, fen: str | None = None) -> dict[str, Any]:
    match = re.match(r"\s*([0-8])\s*,?\s*([0-9])\s*(?:-|>|:)\s*([0-8])\s*,?\s*([0-9])\s*", token)
    if not match:
        raise ValueError(f"Unsupported move token: {token}")
    x1, y1, x2, y2 = [int(value) for value in match.groups()]
    label = FALLBACKS[language]["labels"][min(ply - 1, 2)]
    piece = "pawn"
    side = "red" if ply % 2 else "black"
    if fen:
        try:
            board, _ = parse_fen(fen)
            actual = board.get((x1, y1))
            if actual:
                piece = actual.type
                side = actual.side
        except Exception:
            pass
    return {
        "ply": ply,
        "from": [x1, y1],
        "to": [x2, y2],
        "piece": piece,
        "side": side,
        "startSec": 0.0,
        "endSec": 0.0,
        "label": label,
    }


def _fallback(puzzle: dict[str, Any], language: str) -> dict[str, Any]:
    topic = _safe_text(
        puzzle.get("trend_title") or puzzle.get("topic_title") or puzzle.get("title"),
        FALLBACKS[language]["title"],
        language,
    )
    source_kind = str(puzzle.get("source_kind") or "")
    topic_key = str(puzzle.get("topic_key") or topic).strip().lower()
    variant_index = int(hashlib.sha256(topic_key.encode("utf-8")).hexdigest()[:8], 16) % len(DEFAULT_MOVE_VARIANTS)
    supplied_moves = puzzle.get("moves")
    static_visual = str(puzzle.get("visual_mode") or "") in {"static_board", "foundation_storyboard", "board_introduction", "setup_overview"}
    raw_moves = [] if static_visual else (supplied_moves or DEFAULT_MOVE_VARIANTS[variant_index])
    if source_kind in {"rss", "youtube_search"} and (not supplied_moves or supplied_moves == DEFAULT_MOVE_VARIANTS[0]):
        raw_moves = DEFAULT_MOVE_VARIANTS[variant_index]
    moves: list[dict[str, Any]] = []
    for index, raw_move in enumerate(raw_moves, start=1):
        if isinstance(raw_move, dict):
            move = dict(raw_move)
            move.setdefault("ply", index)
            move.setdefault("startSec", 1.8 + (index - 1) * 1.7)
            move.setdefault("endSec", move["startSec"] + 1.0)
            move.setdefault("piece", "pawn")
            move.setdefault("side", "red" if index % 2 else "black")
            move.setdefault("label", FALLBACKS[language]["labels"][min(index - 1, 2)])
        else:
            move = _parse_move_token(str(raw_move), index, language, str(puzzle.get("fen") or ""))
        moves.append(move)

    fallback = FALLBACKS[language]
    title = _safe_text(puzzle.get("title"), fallback["title"], language)
    content_type = str(puzzle.get("content_type") or "definition")
    curriculum_hook = _safe_text(puzzle.get("hook"), "", language)
    analysis_focus = _safe_text(puzzle.get("analysis_focus"), "the next plan", language)
    supplied_segments = puzzle.get("narrationSegments") if isinstance(puzzle.get("narrationSegments"), list) else []
    supplied_narration = next(
        (str(segment.get("text", "")).strip() for segment in supplied_segments if isinstance(segment, dict) and segment.get("kind") == "intro" and str(segment.get("text", "")).strip()),
        puzzle.get("narration"),
    )
    if source_kind in {"rss", "youtube_search"} and topic and topic != fallback["title"]:
        if language == "zh":
            narration = f"今天的中国象棋话题是：{topic}。{FALLBACK_NARRATION_BY_TYPE['zh'].get('trend_breakdown', '')}"
        else:
            narration = f"Today’s Xiangqi topic is {topic}. {FALLBACK_NARRATION_BY_TYPE['en'].get('trend_breakdown', '')}"
    elif static_visual and language == "en" and str(puzzle.get("curriculum_lesson_key") or "") in CURRICULUM_INTROS:
        narration = CURRICULUM_INTROS[str(puzzle.get("curriculum_lesson_key"))]
    elif supplied_narration:
        narration = _safe_text(supplied_narration, FALLBACK_NARRATION_BY_TYPE.get(language, {}).get(content_type, fallback["narration"]), language)
    else:
        narration = FALLBACK_NARRATION_BY_TYPE.get(language, {}).get(content_type, fallback["narration"])
    if curriculum_hook and curriculum_hook.lower() not in narration.lower():
        narration = f"{curriculum_hook} {narration}"
    narration, narration_segments = build_narration_segments(narration, moves, language, content_type, analysis_focus, split_intro=static_visual)
    duration = estimate_content_duration(
        narration,
        moves,
        language,
        requested_duration=float(puzzle["durationInSeconds"]) if puzzle.get("durationInSeconds") else None,
    )
    moves = retime_moves(moves, duration)
    captions = _segment_captions_without_audio(narration_segments, duration)
    return {"title": title, "narration": narration, "moves": moves, "captions": captions, "narrationSegments": narration_segments, "durationInSeconds": duration}


def _apply_horse_leg_template_contract(result: dict[str, Any], puzzle: dict[str, Any]) -> dict[str, Any]:
    """Use a fixed, mechanically verified Horse Leg teaching line for curriculum lessons."""
    if str(puzzle.get("position_template") or "") != "horse-leg-block":
        return result
    from curriculum import TEMPLATES

    template_moves = [dict(item) for item in TEMPLATES["horse-leg-block"]]
    safe_text = [
        ("Develop the Horse", "continue developing a piece", "the position shows a visible Horse route"),
        ("Develop the opposing Horse", "answer the development", "both Horses now have a visible route"),
        ("Advance the Pawn", "keep the reply legal", "the Pawn moves toward the Horse route"),
        ("Make a waiting reply", "continue development elsewhere", "the route remains visible for now"),
        ("Advance again", "keep the reply legal", "the Pawn reaches the file beside the route"),
        ("Keep the reply legal", "continue development elsewhere", "the position is ready for the final route demonstration"),
        ("Occupy the Horse Leg", "try to continue the Horse route", "the red Pawn occupies the Horse Leg at file 3, rank 4 and removes the Black Horse destination at file 4, rank 5"),
    ]
    for index, move in enumerate(template_moves, start=1):
        purpose, reply, effect = safe_text[index - 1]
        move.update({
            "ply": index,
            "purpose": purpose,
            "opponentReply": reply,
            "effect": effect,
            "label": purpose,
            "claims": [{
                "claimType": "legal_move",
                "ply": index,
                "position": "after",
                "statement": f"The supplied move at ply {index} is legal in the traced position.",
            }],
        })
    template_moves[-1]["claims"].append({
        "claimType": "horse_leg_block",
        "ply": 7,
        "position": "after",
        "subject": {"at": [2, 2]},
        "target": [3, 4],
        "blocker": {"at": [2, 3]},
        "statement": "The red Pawn occupies the Horse Leg at file 3, rank 4, so the Black Horse at file 3, rank 3 cannot reach file 4, rank 5.",
    })
    result["moves"] = template_moves
    return result


def _normalise_move_entries(raw_moves: Any, language: str, puzzle: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(raw_moves, list):
        return []
    normalised: list[dict[str, Any]] = []
    fen = str(puzzle.get("fen") or "")
    for index, raw_move in enumerate(raw_moves, start=1):
        if isinstance(raw_move, dict):
            move = dict(raw_move)
            move.setdefault("ply", index)
            move.setdefault("startSec", 1.8 + (index - 1) * 1.7)
            move.setdefault("endSec", move["startSec"] + 1.0)
            move.setdefault("piece", "pawn")
            move.setdefault("side", "red" if index % 2 else "black")
            move.setdefault("label", FALLBACKS[language]["labels"][min(index - 1, 2)])
        else:
            move = _parse_move_token(str(raw_move), index, language, fen)
        normalised.append(move)
    return normalised


def _sanitize_director_data(data: dict[str, Any], language: str, puzzle: dict[str, Any]) -> dict[str, Any]:
    fallback = _fallback(puzzle, language)
    result = _canonicalize_xiangqi_terms(dict(data))
    static_visual = str(puzzle.get("visual_mode") or "") in {"static_board", "foundation_storyboard", "board_introduction", "setup_overview"}
    if static_visual:
        result["moves"] = []
        result["title"] = _safe_text(puzzle.get("title"), result.get("title"), language)
        lesson_key = str(puzzle.get("curriculum_lesson_key") or "")
        intro = CURRICULUM_INTROS.get(lesson_key) if language == "en" else None
        intro = _safe_text(intro or result.get("narration"), fallback["narration"], language)
        result["narration"], result["narrationSegments"] = build_narration_segments(intro, [], language, str(puzzle.get("content_type") or "definition"), _safe_text(puzzle.get("analysis_focus"), "the board", language), split_intro=True)
        result["durationInSeconds"] = estimate_content_duration(result["narration"], [], language, requested_duration=float(puzzle["durationInSeconds"]) if puzzle.get("durationInSeconds") else None)
        result["captions"] = _segment_captions_without_audio(result["narrationSegments"], result["durationInSeconds"])
        return result
    result["title"] = _safe_text(result.get("title"), fallback["title"], language)
    result["narration"] = _safe_text(result.get("narration"), fallback["narration"], language)
    if str(puzzle.get("source_kind") or "") in {"rss", "youtube_search"}:
        if result["narration"].strip() == FALLBACKS[language]["narration"].strip() or not result["narration"].strip():
            result["narration"] = fallback["narration"]
        if not isinstance(result.get("moves"), list) or result.get("moves") == [
            {"from": [0, 6], "to": [0, 5]},
        ]:
            result["moves"] = fallback["moves"]
    raw_captions = result.get("captions")
    if not isinstance(raw_captions, list) or any(_text_is_invalid(cue.get("text", ""), language) for cue in raw_captions if isinstance(cue, dict)):
        result["captions"] = fallback["captions"]
    result["moves"] = _normalise_move_entries(
        result.get("moves") if isinstance(result.get("moves"), list) else fallback["moves"],
        language,
        puzzle,
    )
    for move in result["moves"]:
        for field in ("purpose", "opponentReply", "effect", "label"):
            if contains_arabic(move.get(field, "")) or (language == "en" and CJK_RE.search(str(move.get(field, "")))):
                move.pop(field, None)
    result = _apply_horse_leg_template_contract(result, puzzle)
    analysis_focus = _safe_text(puzzle.get("analysis_focus"), "the next plan", language)
    existing_segments = result.get("narrationSegments") if isinstance(result.get("narrationSegments"), list) else []
    intro_source = next(
        (str(segment.get("text", "")).strip() for segment in existing_segments if isinstance(segment, dict) and segment.get("kind") == "intro" and str(segment.get("text", "")).strip()),
        str(result.get("narration", "")).strip(),
    )
    piece_intro = piece_learning_intro(puzzle, language)
    if piece_intro and not intro_source.startswith(piece_intro):
        intro_source = f"{piece_intro} {intro_source}".strip()
    result["narration"], result["narrationSegments"] = build_narration_segments(
        intro_source, result["moves"], language, str(puzzle.get("content_type") or "definition"), analysis_focus
    )
    result["durationInSeconds"] = estimate_content_duration(
        result["narration"],
        result["moves"],
        language,
        requested_duration=float(puzzle["durationInSeconds"]) if puzzle.get("durationInSeconds") else None,
    )
    result["moves"] = retime_moves(result["moves"], result["durationInSeconds"])
    for index, move in enumerate(result["moves"], start=1):
        if isinstance(move, dict) and contains_arabic(move.get("label", "")):
            move["label"] = fallback["labels"][min(index - 1, 2)]
    result["captions"] = _segment_captions_without_audio(result["narrationSegments"], result["durationInSeconds"])
    return result


def generate_director_data(puzzle: dict[str, Any], store: Any | None = None, operation: str = "director") -> dict[str, Any]:
    language = normalize_language(puzzle.get("language"))
    providers: list[Callable[..., dict[str, Any] | None]] = []
    if (
        os.getenv("AI_ROUTER_PATH")
        or os.getenv("AI_ROUTER_GEMINI_KEYS_JSON")
        or os.getenv("AI_ROUTER_HF_KEYS_JSON")
        or os.getenv("GEMINI_KEYS_JSON")
        or os.getenv("GEMINI_API_KEYS")
        or os.getenv("GOOGLE_API_KEYS")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("HF_TOKEN")
    ):
        providers.append(lambda current_puzzle, current_language: _request_ai(current_puzzle, current_language, store, operation))
    if os.getenv("OLLAMA_BASE_URL"):
        providers.append(_request_ollama)
    for provider in providers:
        try:
            result = provider(puzzle, language)
            if result:
                return _sanitize_director_data(result, language, puzzle)
        except Exception as exc:
            print(f"Director provider failed: {exc}")
    if research_required() and str(os.getenv("YOUTUBE_PUBLISH_ENABLED", "0")).lower() in {"1", "true", "yes"}:
        raise RuntimeError("Grounded production requires an available AI director; refusing ungrounded fallback")
    return _fallback(puzzle, language)


def _recoverable_dynamic_puzzle(puzzle: dict[str, Any]) -> bool:
    return not str(puzzle.get("curriculum_lesson_key") or "").strip() and str(puzzle.get("visual_mode") or "") not in {
        "static_board",
        "foundation_storyboard",
        "board_introduction",
        "setup_overview",
    }


def _deterministic_legal_fallback(puzzle: dict[str, Any], language: str) -> dict[str, Any]:
    recovered = dict(puzzle)
    topic_key = str(recovered.get("topic_key") or recovered.get("title") or "dynamic-xiangqi").strip().lower()
    variant_index = int(hashlib.sha256(topic_key.encode("utf-8")).hexdigest()[:8], 16) % len(DEFAULT_MOVE_VARIANTS)
    recovered["moves"] = list(DEFAULT_MOVE_VARIANTS[variant_index])
    recovered["source_kind"] = recovered.get("source_kind") or "generated"
    fallback_data = _fallback(recovered, language)
    return _sanitize_director_data(fallback_data, language, recovered)


def _build_verified_claims(clean_data: dict[str, Any], puzzle: dict[str, Any], canonical_moves: list[dict[str, Any]]) -> tuple[dict[int, list[dict[str, Any]]], dict[str, Any]]:
    claims_by_ply: dict[int, list[dict[str, Any]]] = {}
    for raw_move, canonical_move in zip(clean_data.get("moves", []), canonical_moves):
        raw_move["piece"] = canonical_move["piece"]
        raw_move["side"] = canonical_move["side"]
        raw_move["captured"] = canonical_move["captured"]
        ply = int(canonical_move["ply"])
        raw_claims = raw_move.get("claims") if isinstance(raw_move.get("claims"), list) else []
        if suspicious_claim_language(raw_move) and not raw_claims:
            raise ValueError(f"ply {ply}: causal/rule language requires structured Xiangqi claims")
        claims_by_ply[ply] = [dict(claim) for claim in raw_claims if isinstance(claim, dict)]
        if suspicious_claim_language(raw_move) and claims_by_ply[ply] and all(str(claim.get("claimType") or "") == "legal_move" for claim in claims_by_ply[ply]):
            raise ValueError(f"Xiangqi causal claim verification failed: ply {ply}: causal language has only a legal_move claim")
        if not claims_by_ply[ply]:
            claims_by_ply[ply] = [{"claimType": "legal_move", "ply": ply, "position": "after", "statement": "validated legal move"}]
    claim_proof = verify_claims(str(puzzle.get("fen") or ""), canonical_moves, claims_by_ply)
    if not claim_proof.get("ok"):
        raise ValueError("Xiangqi causal claim verification failed: " + "; ".join(claim_proof.get("errors") or []))
    return claims_by_ply, claim_proof


def make_job(job_id: str, puzzle: dict[str, Any], director_data: dict[str, Any]) -> dict[str, Any]:
    language = normalize_language(puzzle.get("language"))
    clean_data = _sanitize_director_data(director_data, language, puzzle)
    research_bundle = puzzle.get("researchBundle") if isinstance(puzzle.get("researchBundle"), dict) else {}
    if os.getenv("XIANGQI_RESEARCH_REQUIRED", "1").lower() in {"1", "true", "yes"} and research_bundle.get("status") != "grounded":
        raise ValueError("Xiangqi research grounding is required before script acceptance")
    move_validation = validate_move_sequence(str(puzzle.get("fen") or ""), clean_data.get("moves", []))
    if not move_validation["ok"] and _recoverable_dynamic_puzzle(puzzle):
        clean_data = _deterministic_legal_fallback(puzzle, language)
        move_validation = validate_move_sequence(str(puzzle.get("fen") or ""), clean_data.get("moves", []))
    if not move_validation["ok"]:
        raise ValueError("Xiangqi legal-move validation failed: " + "; ".join(move_validation["errors"]))
    canonical_moves = move_validation["moves"]
    try:
        claims_by_ply, claim_proof = _build_verified_claims(clean_data, puzzle, canonical_moves)
    except ValueError as claim_error:
        if not _recoverable_dynamic_puzzle(puzzle) or not str(claim_error).startswith("Xiangqi causal claim verification failed:"):
            raise
        # AI-generated dynamic ideas may contain a plausible-sounding but
        # mechanically unverifiable causal claim. Keep the research bundle and
        # legal trace, but replace only the unsafe director prose with the
        # deterministic legal fallback instead of publishing or retrying the
        # same invalid claim indefinitely.
        print(f"Director claim proof failed; using deterministic legal fallback: {claim_error}")
        clean_data = _deterministic_legal_fallback(puzzle, language)
        fallback_validation = validate_move_sequence(str(puzzle.get("fen") or ""), clean_data.get("moves", []))
        if not fallback_validation["ok"]:
            raise ValueError("Deterministic fallback also failed Xiangqi legal-move validation: " + "; ".join(fallback_validation["errors"]))
        canonical_moves = fallback_validation["moves"]
        claims_by_ply, claim_proof = _build_verified_claims(clean_data, puzzle, canonical_moves)
    clean_data["claimProof"] = claim_proof
    clean_data["claimsByPly"] = claims_by_ply
    duration = float(clean_data.get("durationInSeconds") or estimate_content_duration(clean_data.get("narration", ""), clean_data.get("moves", []), language))
    return {
        "id": job_id,
        "title": clean_data.get("title") or FALLBACKS[language]["title"],
        "language": language,
        "fen": puzzle["fen"],
        "narration": clean_data.get("narration", FALLBACKS[language]["narration"]),
        "moves": clean_data.get("moves", []),
        "captions": clean_data.get("captions", []),
        "narrationSegments": clean_data.get("narrationSegments", []),
        "claimProof": clean_data.get("claimProof"),
        "claimsByPly": clean_data.get("claimsByPly", {}),
        "audioSrc": "",
        "durationInSeconds": duration,
        "theme": puzzle.get("theme", "wood"),
        "content_type": puzzle.get("content_type", "definition"),
        "source_url": puzzle.get("source_url"),
        "source_kind": puzzle.get("source_kind", "generated"),
        "researchBundle": puzzle.get("researchBundle"),
        "groundingStatus": puzzle.get("groundingStatus"),
        "topic_key": puzzle.get("topic_key"),
        "hook": puzzle.get("hook"),
        "objective": puzzle.get("objective"),
        "analysis_focus": puzzle.get("analysis_focus"),
        "curriculum_lesson_key": puzzle.get("curriculum_lesson_key"),
        "curriculum_sequence": puzzle.get("curriculum_sequence"),
        "curriculum_stage": puzzle.get("curriculum_stage"),
        "difficulty": puzzle.get("difficulty"),
        "format": puzzle.get("format"),
        "playlist_key": puzzle.get("playlist_key"),
        "visual_mode": puzzle.get("visual_mode"),
        "visual_focus": puzzle.get("visual_focus"),
        "pairing": puzzle.get("pairing", {}),
    }
