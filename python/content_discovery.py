from __future__ import annotations

import html
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from local_store import DEFAULT_FEN, LocalStore
from ai_router_bridge import load_router

SKILL_LEVELS = ["beginner", "intermediate", "advanced", "expert", "professional", "legendary"]
CONTENT_TYPES = [
    "definition",
    "rules",
    "opening",
    "tactics",
    "endgame",
    "full_game",
    "advanced_puzzle",
    "comparison",
    "trend_breakdown",
    "skill_match",
    "viewer_challenge",
]


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def _rss_url(query: str) -> str:
    params = urllib.parse.urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    return f"https://news.google.com/rss/search?{params}"


def _score(title: str, published: str = "") -> float:
    text = f"{title} {published}".lower()
    score = 1.0
    for keyword, weight in {
        "xiangqi": 5,
        "chinese chess": 5,
        "championship": 4,
        "final": 3,
        "tournament": 3,
        "world": 2,
        "grandmaster": 2,
        "checkmate": 2,
        "puzzle": 2,
        "viral": 2,
    }.items():
        if keyword in text:
            score += weight
    return score


def discover_rss(store: LocalStore, limit: int = 20) -> int:
    query = os.getenv("DISCOVERY_RSS_QUERY", "xiangqi OR \"Chinese chess\" OR 象棋")
    urls = [item.strip() for item in os.getenv("DISCOVERY_RSS_FEEDS", "").split(",") if item.strip()]
    if not urls:
        urls = [_rss_url(query)]
    inserted = 0
    for feed_url in urls:
        try:
            response = requests.get(feed_url, timeout=20, headers={"User-Agent": "ChineseCheeseVideoBot/1.0"})
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except (requests.RequestException, ET.ParseError) as exc:
            print(f"RSS discovery failed for {feed_url}: {exc}")
            continue
        for item in root.findall(".//item")[:limit]:
            title = _clean(item.findtext("title", default=""))
            link = _clean(item.findtext("link", default=""))
            published = _clean(item.findtext("pubDate", default=""))
            if not title or not link:
                continue
            candidate = {
                "id": "news-" + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50],
                "content_type": "trend_breakdown",
                "title": f"Trending Xiangqi: {title}",
                "language": "en",
                "source_kind": "rss",
                "source_url": link,
                "priority_score": _score(title, published),
                "payload": {
                    "fen": DEFAULT_FEN,
                    "moves": ["0,6-0,5", "0,3-0,4", "1,7-1,4"],
                    "trend_title": title,
                    "published": published,
                    "source_url": link,
                    "rights_note": "Use public metadata as inspiration; do not re-upload source footage without rights.",
                },
            }
            inserted += int(store.add_candidate(candidate))
    return inserted


def discover_youtube(store: LocalStore, limit: int = 10) -> int:
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return 0
    query = os.getenv("YOUTUBE_SEARCH_QUERY", "xiangqi Chinese chess")
    published_after = (datetime.now(timezone.utc) - timedelta(days=int(os.getenv("YOUTUBE_LOOKBACK_DAYS", "7")))).isoformat().replace("+00:00", "Z")
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "viewCount",
        "publishedAfter": published_after,
        "maxResults": min(limit, 50),
        "key": api_key,
    }
    try:
        response = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, timeout=20)
        response.raise_for_status()
        items = response.json().get("items", [])
    except (requests.RequestException, ValueError) as exc:
        print(f"YouTube discovery failed: {exc}")
        return 0
    inserted = 0
    for item in items:
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        title = _clean(snippet.get("title", ""))
        if not video_id or not title:
            continue
        candidate = {
            "id": f"youtube-{video_id}",
            "content_type": "trend_breakdown",
            "title": f"Trending Xiangqi Video: {title}",
            "language": "en",
            "source_kind": "youtube_search",
            "source_url": f"https://www.youtube.com/watch?v={video_id}",
            "priority_score": _score(title) + 3,
            "payload": {
                "fen": DEFAULT_FEN,
                "moves": ["0,6-0,5", "0,3-0,4", "1,7-1,4"],
                "trend_title": title,
                "source_url": f"https://www.youtube.com/watch?v={video_id}",
                "rights_note": "Use public metadata as inspiration; do not download or re-upload source footage without rights.",
            },
        }
        inserted += int(store.add_candidate(candidate))
    return inserted


def _pairing_candidates(store: LocalStore, count: int = 12) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    inserted = 0
    pairings = [(a, b) for a in SKILL_LEVELS for b in SKILL_LEVELS]
    offset = int(datetime.now(timezone.utc).strftime("%j")) % len(pairings)
    for step in range(min(count, len(pairings))):
        a, b = pairings[(offset + step) % len(pairings)]
        title = f"Can a {a.title()} Beat a {b.title()}? Xiangqi Match {today}"
        candidate = {
            "id": f"pairing-{today}-{a}-{b}",
            "content_type": "skill_match",
            "title": title,
            "language": "en",
            "source_kind": "generated_pairing",
            "priority_score": 4.0 + (step / 100.0),
            "payload": {
                "fen": DEFAULT_FEN,
                "moves": ["0,6-0,5", "0,3-0,4", "1,7-1,4"],
                "pairing": {"red": a, "black": b},
                "series_date": today,
                "hook": f"A structured Xiangqi match between {a} and {b} skill profiles, with a clear lesson for viewers.",
            },
        }
        inserted += int(store.add_candidate(candidate))
    return inserted


def _perpetual_candidates(store: LocalStore, count: int = 8) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    week = datetime.now(timezone.utc).isocalendar().week
    ideas = [
        ("opening", "The Opening Mistake That Gives Away the Center"),
        ("tactics", "One Cannon Pattern Every New Xiangqi Player Should Know"),
        ("endgame", "The Endgame Test: Can You Convert This Advantage?"),
        ("comparison", "Xiangqi vs Western Chess: The Rule That Changes Everything"),
        ("advanced_puzzle", "Solve This Three-Move Xiangqi Puzzle Before the Reveal"),
        ("full_game", "A Complete Xiangqi Game Explained Move by Move"),
        ("viewer_challenge", "Comment Your Move: The Audience Chooses the Continuation"),
        ("definition", "Why the River and Palace Define Xiangqi Strategy"),
    ]
    inserted = 0
    for index, (content_type, title) in enumerate(ideas[:count]):
        candidate = {
            "id": f"evergreen-{week}-{index}-{today}",
            "content_type": content_type,
            "title": f"{title} — Series {week}.{index + 1}",
            "language": "en",
            "source_kind": "generated_evergreen",
            "priority_score": 3.0 - index / 100.0,
            "payload": {
                "fen": DEFAULT_FEN,
                "moves": ["0,6-0,5", "0,3-0,4", "1,7-1,4"],
                "series_week": week,
                "content_type": content_type,
            },
        }
        inserted += int(store.add_candidate(candidate))
    return inserted


def generate_ai_candidate(store: LocalStore, language: str = "en") -> dict[str, Any] | None:
    router = load_router()
    if router is None:
        return None
    system = """You are a professional Xiangqi YouTube programming editor. Return JSON only. Create one original, rights-safe content idea that can be explained with a Xiangqi board. Never suggest re-uploading copyrighted footage. Use English for the fields. Required keys: title, content_type, hook, fen, moves, pairing, source_kind, priority_score. content_type must be one of definition, rules, opening, tactics, endgame, full_game, advanced_puzzle, comparison, trend_breakdown, skill_match, viewer_challenge. moves must be an array of coordinate move strings or move objects. pairing must be an object, even when empty."""
    user = """Generate a fresh idea that is not a generic duplicate. Rotate among teaching, puzzles, complete games, comparisons, current-topic commentary, audience challenges, and skill-profile matches. Include a strong first-five-seconds hook and a practical lesson. Use this date as the series marker: """ + datetime.now(timezone.utc).date().isoformat()
    try:
        result = router.complete_json(
            chain=os.getenv("AI_ROUTER_CHAIN", "creative"),
            system_prompt=system,
            user_prompt=user,
            operation="idea_generation",
        )
    except Exception as exc:
        print(f"AI idea generation unavailable: {exc}")
        return None
    finally:
        router.close()
    result.setdefault("language", language)
    result.setdefault("source_kind", "ai_generated")
    result.setdefault("priority_score", 5.0)
    result.setdefault("fen", DEFAULT_FEN)
    result.setdefault("moves", ["0,6-0,5", "0,3-0,4", "1,7-1,4"])
    result.setdefault("pairing", {})
    return result


def discover_all(store: LocalStore, limit: int = 20) -> dict[str, int]:
    metrics = {
        "rss_inserted": discover_rss(store, limit),
        "youtube_inserted": discover_youtube(store, min(limit, 10)),
        "pairing_inserted": _pairing_candidates(store, min(limit, 12)),
        "evergreen_inserted": _perpetual_candidates(store, min(limit, 8)),
        "ai_inserted": 0,
    }
    ai_candidate = generate_ai_candidate(store)
    if ai_candidate:
        ai_candidate["payload"] = dict(ai_candidate)
        metrics["ai_inserted"] = int(store.add_candidate(ai_candidate))
    return metrics
