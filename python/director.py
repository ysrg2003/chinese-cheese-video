from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Callable

import requests

from ai_router_bridge import load_router
from timing import clamp_captions, estimate_content_duration, retime_moves

SUPPORTED_LANGUAGES = ("en", "zh")
DEFAULT_LANGUAGE = "en"

DIRECTOR_INSTRUCTIONS = {
    "en": """
You are the director of short Xiangqi Chinese-chess videos. Return valid JSON only with this schema:
{
  "title": "short, compelling title",
  "narration": "energetic English narration of 35 to 80 words",
  "moves": [
    {"ply": 1, "from": [0, 6], "to": [0, 5], "piece": "pawn", "side": "red", "startSec": 2.0, "endSec": 3.0, "label": "move description"}
  ],
  "captions": [{"startSec": 0.0, "endSec": 2.0, "text": "short English caption"}],
  "durationInSeconds": 0
}
Rules: columns are 0..8 and rows are 0..9 from the top of the board. Use only king, advisor, bishop, knight, rook, cannon, pawn and red or black. Do not force a fixed short duration; the rendering pipeline calculates the final duration from narration, audio, captions, and move count. Do not output Markdown or any text outside JSON. Never output Arabic.
""".strip(),
    "zh": """
你是中国象棋短视频导演。只能返回有效 JSON，格式如下：
{
  "title": "简短、有吸引力的标题",
  "narration": "35 到 80 字的中文激情解说",
  "moves": [
    {"ply": 1, "from": [0, 6], "to": [0, 5], "piece": "pawn", "side": "red", "startSec": 2.0, "endSec": 3.0, "label": "走法说明"}
  ],
  "captions": [{"startSec": 0.0, "endSec": 2.0, "text": "简短中文字幕"}],
  "durationInSeconds": 0
}
规则：列坐标为 0..8，行坐标为 0..9，从棋盘顶部开始计算。棋子类型只能使用 king、advisor、bishop、knight、rook、cannon、pawn，阵营只能使用 red 或 black。不要强制使用固定的短时长，最终时长将由渲染系统根据解说、音频、字幕和步数计算。不要输出 Markdown 或 JSON 之外的任何内容。绝不输出阿拉伯语。
""".strip(),
}

FALLBACKS = {
    "en": {
        "title": "The Quiet Trap on the Left Wing",
        "narration": "The first pawn push looks harmless, but it opens a tactical file for the cannon. When the natural reply arrives, the quiet pressure turns into a direct threat. Watch the line before you chase the piece.",
        "captions": [
            "The idea starts with a move that looks ordinary.",
            "The pawn push opens a file for the cannon.",
            "The natural reply leaves a tactical weakness.",
            "Now the decisive idea appears.",
        ],
        "labels": ["Advance the pawn", "The counter-push", "The cannon takes the file"],
    },
    "zh": {
        "title": "左翼的安静陷阱",
        "narration": "第一步兵看起来很普通，却为大炮打开了战术线路。当对手作出自然回应时，安静的压力立刻变成直接威胁。先观察线路，再追逐棋子。",
        "captions": [
            "这个构想从一手普通的棋开始。",
            "兵的推进为大炮打开线路。",
            "自然的回应留下了战术弱点。",
            "现在，决定性的构想出现了。",
        ],
        "labels": ["兵向前推进", "对手回应", "大炮占据线路"],
    },
}


ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
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
    ["0,9-0,5", "0,0-0,4", "2,6-2,5"],
    ["3,9-4,8", "3,0-4,1", "7,7-7,4"],
]


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
    prompt = f"{DIRECTOR_INSTRUCTIONS[language]}\n\nPuzzle data:\n{json.dumps(puzzle, ensure_ascii=False)}"
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


def _parse_move_token(token: str, ply: int, language: str) -> dict[str, Any]:
    match = re.match(r"\s*([0-8])\s*,?\s*([0-9])\s*(?:-|>|:)\s*([0-8])\s*,?\s*([0-9])\s*", token)
    if not match:
        raise ValueError(f"Unsupported move token: {token}")
    x1, y1, x2, y2 = [int(value) for value in match.groups()]
    label = FALLBACKS[language]["labels"][min(ply - 1, 2)]
    return {
        "ply": ply,
        "from": [x1, y1],
        "to": [x2, y2],
        "piece": "pawn",
        "side": "red" if ply % 2 else "black",
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
    raw_moves = supplied_moves or DEFAULT_MOVE_VARIANTS[variant_index]
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
            move = _parse_move_token(str(raw_move), index, language)
        moves.append(move)

    fallback = FALLBACKS[language]
    title = _safe_text(puzzle.get("title"), fallback["title"], language)
    content_type = str(puzzle.get("content_type") or "definition")
    supplied_narration = puzzle.get("narration")
    if source_kind in {"rss", "youtube_search"} and topic and topic != fallback["title"]:
        if language == "zh":
            narration = f"今天的中国象棋话题是：{topic}。{FALLBACK_NARRATION_BY_TYPE['zh'].get('trend_breakdown', '')}"
        else:
            narration = f"Today’s Xiangqi topic is {topic}. {FALLBACK_NARRATION_BY_TYPE['en'].get('trend_breakdown', '')}"
    elif supplied_narration:
        narration = _safe_text(supplied_narration, FALLBACK_NARRATION_BY_TYPE.get(language, {}).get(content_type, fallback["narration"]), language)
    else:
        narration = FALLBACK_NARRATION_BY_TYPE.get(language, {}).get(content_type, fallback["narration"])
    duration = estimate_content_duration(
        narration,
        moves,
        language,
        requested_duration=float(puzzle["durationInSeconds"]) if puzzle.get("durationInSeconds") else None,
    )
    supplied_captions = puzzle.get("captions")
    captions = supplied_captions if isinstance(supplied_captions, list) and all(not _text_is_invalid(c.get("text", ""), language) for c in supplied_captions if isinstance(c, dict)) else [
        {"startSec": 0.2, "endSec": 2.0, "text": fallback["captions"][0]},
        {"startSec": 2.0, "endSec": duration - 1.0, "text": fallback["captions"][1]},
        {"startSec": duration - 1.0, "endSec": duration, "text": fallback["captions"][3]},
    ]
    moves = retime_moves(moves, duration)
    captions = clamp_captions(captions, duration)
    return {"title": title, "narration": narration, "moves": moves, "captions": captions, "durationInSeconds": duration}


def _sanitize_director_data(data: dict[str, Any], language: str, puzzle: dict[str, Any]) -> dict[str, Any]:
    fallback = _fallback(puzzle, language)
    result = dict(data)
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
    result["moves"] = result.get("moves") if isinstance(result.get("moves"), list) else fallback["moves"]
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
    result["captions"] = clamp_captions(result.get("captions", []), result["durationInSeconds"])
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
    return _fallback(puzzle, language)


def make_job(job_id: str, puzzle: dict[str, Any], director_data: dict[str, Any]) -> dict[str, Any]:
    language = normalize_language(puzzle.get("language"))
    clean_data = _sanitize_director_data(director_data, language, puzzle)
    duration = float(clean_data.get("durationInSeconds") or estimate_content_duration(clean_data.get("narration", ""), clean_data.get("moves", []), language))
    return {
        "id": job_id,
        "title": clean_data.get("title") or FALLBACKS[language]["title"],
        "language": language,
        "fen": puzzle["fen"],
        "narration": clean_data.get("narration", FALLBACKS[language]["narration"]),
        "moves": clean_data.get("moves", []),
        "captions": clean_data.get("captions", []),
        "audioSrc": "",
        "durationInSeconds": duration,
        "theme": puzzle.get("theme", "wood"),
        "content_type": puzzle.get("content_type", "definition"),
        "source_url": puzzle.get("source_url"),
        "source_kind": puzzle.get("source_kind", "generated"),
        "topic_key": puzzle.get("topic_key"),
        "hook": puzzle.get("hook"),
        "pairing": puzzle.get("pairing", {}),
    }
