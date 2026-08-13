from __future__ import annotations

import json
import re
from typing import Any

from ai_router_bridge import load_router
from timing import estimate_content_duration

FOUNDATION_VISUAL_MODES = {"foundation_storyboard", "board_introduction", "setup_overview"}
ALLOWED_VISUAL_KINDS = {
    "battlefield",
    "two_armies",
    "generals_goal",
    "intersections",
    "river_palaces",
    "cannon_geometry",
    "learning_roadmap",
}
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
        "visualInstruction": "Animate a concise road map from board to setup, pieces, moves, games, and tactics.",
    },
]


VISUAL_DIRECTOR_INSTRUCTIONS = """
You are the visual director for a short English Xiangqi lesson. Return valid JSON only with this schema:
{
  "scenes": [
    {
      "index": 1,
      "narration": "natural spoken English for one idea",
      "caption": "short English cue",
      "visualKind": "one permitted visual kind",
      "headline": "2 to 5 English words",
      "visualInstruction": "concrete on-board visual action"
    }
  ]
}

Rules: Create exactly seven scenes for the first beginner lesson. Every scene must teach one fact and give the renderer one meaningful on-board visual action. Narration must sound like an educator speaking to a learner; never write commands to the animator such as 'label this now'. Use only English and never Arabic. Do not play an unexplained game. Do not add decorative movement that does not explain the current spoken fact. Keep narration between 10 and 22 words and captions at ten words or fewer. The permitted kinds, in this exact order, are battlefield, two_armies, generals_goal, intersections, river_palaces, cannon_geometry, learning_roadmap.
""".strip()


def _is_valid_english(value: Any, *, min_words: int = 1, max_words: int = 30) -> bool:
    text = str(value or "").strip()
    words = re.findall(r"[A-Za-z][A-Za-z’'-]*", text)
    return bool(text) and not ARABIC_RE.search(text) and not CJK_RE.search(text) and min_words <= len(words) <= max_words


def _fallback_for(puzzle: dict[str, Any]) -> list[dict[str, Any]]:
    key = str(puzzle.get("curriculum_lesson_key") or "")
    if key == "en-001-what-is-xiangqi":
        return [dict(scene) for scene in FIRST_LESSON_FALLBACK]
    focus = str(puzzle.get("visual_focus") or puzzle.get("objective") or "Learn the Xiangqi board one idea at a time.").strip()
    kinds = ["battlefield", "two_armies", "intersections", "river_palaces", "generals_goal", "cannon_geometry", "learning_roadmap"]
    headlines = ["Board Map", "Two Sides", "Key Points", "Special Regions", "Protect the General", "Line Geometry", "Next Steps"]
    return [
        {
            "index": index,
            "visualKind": kind,
            "headline": headline,
            "narration": focus if index == 1 else f"Keep this visual idea in mind as you learn Xiangqi step by step.",
            "caption": headline,
            "visualInstruction": f"Use the {kind} overlay to make the current board idea visible.",
        }
        for index, (kind, headline) in enumerate(zip(kinds, headlines), start=1)
    ]


def _request_ai_storyboard(puzzle: dict[str, Any], job: dict[str, Any], store: Any | None = None) -> dict[str, Any] | None:
    router = load_router()
    if router is None:
        return None
    prompt_payload = {
        "lesson_key": puzzle.get("curriculum_lesson_key"),
        "title": job.get("title") or puzzle.get("title"),
        "objective": puzzle.get("objective"),
        "hook": puzzle.get("hook"),
        "visual_focus": puzzle.get("visual_focus"),
        "required_facts": [
            "Xiangqi is Chinese chess.",
            "Two mirrored armies face each other.",
            "The objective is checkmate of the opposing General.",
            "The board has nine files and ten ranks.",
            "Pieces stand on intersections.",
            "The river divides the board and palaces contain the Generals.",
            "The cannon captures through exactly one screen.",
            "The course progresses from board and setup to pieces, moves, games, and tactics.",
        ],
    }
    try:
        return router.complete_json(
            system_prompt=VISUAL_DIRECTOR_INSTRUCTIONS,
            user_prompt=json.dumps(prompt_payload, ensure_ascii=False),
            operation=f"visual_director:{puzzle.get('curriculum_lesson_key') or job.get('id')}",
            chain="default",
        )
    finally:
        router.close()


def _normalize_storyboard(raw: dict[str, Any] | None, puzzle: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    fallback = _fallback_for(puzzle)
    scenes = raw.get("scenes") if isinstance(raw, dict) else None
    if not isinstance(scenes, list) or len(scenes) != len(fallback):
        return fallback, "fallback"
    normalized: list[dict[str, Any]] = []
    for index, default in enumerate(fallback, start=1):
        candidate = scenes[index - 1] if isinstance(scenes[index - 1], dict) else {}
        narration = str(candidate.get("narration") or "").strip()
        caption = str(candidate.get("caption") or "").strip()
        headline = str(candidate.get("headline") or "").strip()
        visual_instruction = str(candidate.get("visualInstruction") or "").strip()
        visual_kind = str(candidate.get("visualKind") or "")
        if not _is_valid_english(narration, min_words=10, max_words=22):
            narration = default["narration"]
        if not _is_valid_english(caption, min_words=1, max_words=10):
            caption = default["caption"]
        if not _is_valid_english(headline, min_words=1, max_words=6):
            headline = default["headline"]
        if not _is_valid_english(visual_instruction, min_words=3, max_words=50):
            visual_instruction = default["visualInstruction"]
        if visual_kind not in ALLOWED_VISUAL_KINDS or visual_kind != default["visualKind"]:
            visual_kind = default["visualKind"]
        normalized.append(
            {
                "index": index,
                "visualKind": visual_kind,
                "headline": headline,
                "narration": narration,
                "caption": caption,
                "visualInstruction": visual_instruction,
            }
        )
    return normalized, "ai_router"


def add_visual_storyboard(job: dict[str, Any], puzzle: dict[str, Any], store: Any | None = None) -> dict[str, Any]:
    """Attach a sentence-level visual storyboard to an introductory video job.

    The AI router proposes narration and visual treatment. Validation constrains the
    output to the renderer's supported educational overlays, and a deterministic
    storyboard keeps unattended production usable if all external models fail.
    """
    mode = str(job.get("visual_mode") or puzzle.get("visual_mode") or "")
    if mode not in FOUNDATION_VISUAL_MODES:
        return job
    raw = puzzle.get("visualStoryboard") if isinstance(puzzle.get("visualStoryboard"), dict) else None
    source_hint = "provided_ai" if raw is not None else ""
    if raw is None:
        try:
            raw = _request_ai_storyboard(puzzle, job, store)
        except Exception as exc:
            print(f"Visual director provider failed: {exc}")
    scenes, source = _normalize_storyboard(raw, puzzle)
    if source_hint and source == "ai_router":
        source = source_hint
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
    job["visual_mode"] = "foundation_storyboard"
    job["visualStoryboard"] = scenes
    job["visualStoryboardSource"] = source
    job["narrationSegments"] = segments
    job["narration"] = " ".join(scene["narration"] for scene in scenes)
    job["captions"] = []
    job["durationInSeconds"] = estimate_content_duration(
        job["narration"], [], job.get("language", "en"), requested_duration=float(puzzle.get("target_seconds") or 0) or None
    )
    return job
