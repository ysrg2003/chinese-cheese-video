from __future__ import annotations

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
    raw_moves = puzzle.get("moves") or ["0,6-0,5", "0,3-0,4", "1,7-1,4"]
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
    narration = _safe_text(puzzle.get("narration"), fallback["narration"], language)
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
        "hook": puzzle.get("hook"),
        "pairing": puzzle.get("pairing", {}),
    }
