from __future__ import annotations

import hashlib
import html
import json
import os
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests


RESEARCH_CONTRACT = "xiangqi_grounding_v1"
DEFAULT_TIMEOUT_SECONDS = 25
DEFAULT_SOURCES = [
    {
        "id": "wxf_rules_index",
        "title": "World Xiangqi Federation — World Xiangqi Rules",
        "url": "https://www.wxf-xiangqi.org/index.php?option=com_content&view=article&id=269&Itemid=291&lang=en",
        "authority": "primary_rules_provenance",
    },
    {
        "id": "wxf_rules_pdf",
        "title": "World Xiangqi Rules — English PDF",
        "url": "https://www.wxf-xiangqi.org/images/wxf-rules/2018_World_XiangQi_Rules_English2018.pdf",
        "authority": "primary_rules_document",
    },
    {
        "id": "xiangqi_com_pieces",
        "title": "Xiangqi.com — Learning the Xiangqi Pieces and Moves",
        "url": "https://www.xiangqi.com/help/pieces-and-moves",
        "authority": "specialist_reference",
    },
    {
        "id": "chess_com_xiangqi",
        "title": "Chess.com — How To Play Chinese Chess (Xiangqi)",
        "url": "https://www.chess.com/blog/SamCopeland/how-to-play-chinese-chess",
        "authority": "secondary_reference",
    },
]


class ResearchGroundingError(RuntimeError):
    pass


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        elif self._skip_depth == 0 and tag.lower() in {"p", "li", "h1", "h2", "h3", "h4", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        elif self._skip_depth == 0 and tag.lower() in {"p", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)

    def text(self) -> str:
        raw = html.unescape(" ".join(self.parts))
        return re.sub(r"\s+", " ", raw).strip()


def _truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def research_required() -> bool:
    return _truthy(os.getenv("XIANGQI_RESEARCH_REQUIRED"), True)


def _required_topics(puzzle: dict[str, Any]) -> list[str]:
    context = " ".join(
        str(puzzle.get(key) or "")
        for key in (
            "title",
            "objective",
            "analysis_focus",
            "content_type",
            "hook",
            "research_question",
            "curriculum_lesson_key",
        )
    ).lower()
    topics: list[str] = ["board_geometry", "piece_rules"]
    if any(marker in context for marker in ("horse", "knight", "blocked leg", "ma tui", "马")):
        topics.append("horse_leg")
    if any(marker in context for marker in ("elephant", "bishop", "eye", "xiang yan", "象")):
        topics.append("elephant_eye")
    if any(marker in context for marker in ("cannon", "screen", "mount", "炮")):
        topics.append("cannon_screen")
    if any(marker in context for marker in ("general", "king", "flying", "palace", "将", "帅")):
        topics.append("general_palace")
    if any(marker in context for marker in ("river", "soldier", "pawn", "crossing", "河")):
        topics.append("river_restrictions")
    if any(marker in context for marker in ("history", "origin", "dynasty", "heritage", "历史")):
        topics.append("history")
    if any(marker in context for marker in ("trend", "current", "news", "2026", "recent")):
        topics.append("current_topic")
    return sorted(set(topics))


def _source_specs(puzzle: dict[str, Any]) -> list[dict[str, Any]]:
    specs = [dict(item) for item in DEFAULT_SOURCES]
    custom = puzzle.get("research_sources") or puzzle.get("research_urls") or []
    if isinstance(custom, str):
        custom = [custom]
    for index, value in enumerate(custom):
        if isinstance(value, dict) and value.get("url"):
            specs.append({
                "id": str(value.get("id") or f"custom_{index + 1}"),
                "title": str(value.get("title") or value["url"]),
                "url": str(value["url"]),
                "authority": str(value.get("authority") or "provided_source"),
            })
        elif isinstance(value, str) and value.startswith(("http://", "https://")):
            specs.append({"id": f"custom_{index + 1}", "title": value, "url": value, "authority": "provided_source"})
    source_url = str(puzzle.get("source_url") or "").strip()
    if source_url.startswith(("http://", "https://")) and not any(item["url"] == source_url for item in specs):
        specs.append({"id": "candidate_source", "title": source_url, "url": source_url, "authority": "candidate_source"})
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in specs:
        if item["url"] not in seen:
            unique.append(item)
            seen.add(item["url"])
    return unique


def _fetch_source(spec: dict[str, Any], timeout: int) -> dict[str, Any]:
    url = str(spec["url"])
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "XiangqiLab-GroundedResearch/1.0 (+https://github.com/ysrg2003/chinese-cheese-video)"},
            timeout=(timeout, timeout),
            stream=True,
        )
        response.raise_for_status()
        content_type = str(response.headers.get("content-type") or "")
        if "pdf" in content_type or url.lower().endswith(".pdf"):
            text = "PDF source retrieved; use the linked PDF as primary provenance."
        else:
            if hasattr(response, "iter_content"):
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    remaining = 1_500_000 - total
                    if remaining <= 0:
                        break
                    data = bytes(chunk[:remaining])
                    chunks.append(data)
                    total += len(data)
                    if total >= 1_500_000:
                        break
                raw_html = b"".join(chunks).decode("utf-8", errors="replace")
            else:
                raw_html = str(response.text or "")[:1_500_000]
            parser = _TextExtractor()
            parser.feed(raw_html)
            text = parser.text()
        if hasattr(response, "close"):
            response.close()
        if len(text) < 80:
            raise ResearchGroundingError("source returned insufficient readable text")
        return {
            **spec,
            "status": "retrieved",
            "content_type": content_type,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "text_excerpt": text[:2400],
            "text_length": len(text),
        }
    except Exception as exc:
        return {**spec, "status": "failed", "error": str(exc)[:500]}


def _load_cached_sources() -> list[dict[str, Any]]:
    cache_path = Path(__file__).resolve().parents[1] / "data" / "grounding_source_cache.json"
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    result: list[dict[str, Any]] = []
    for source in payload.get("sources", []) if isinstance(payload, dict) else []:
        if not isinstance(source, dict) or not source.get("id") or not source.get("excerpt"):
            continue
        result.append({
            **source,
            "status": "cached",
            "text_excerpt": str(source.get("excerpt")),
            "text_sha256": hashlib.sha256(str(source.get("excerpt")).encode("utf-8")).hexdigest(),
            "cacheRetrievedAt": payload.get("retrieved_at"),
        })
    return result


def _topic_evidence(sources: list[dict[str, Any]], topics: list[str]) -> dict[str, list[dict[str, str]]]:
    patterns = {
        "board_geometry": ("intersection", "river", "palace", "9x10", "9 x 10", "board"),
        "piece_rules": ("horse", "elephant", "cannon", "advisor", "general", "soldier", "chariot"),
        "horse_leg": ("horse", "leg", "block", "cannot jump"),
        "elephant_eye": ("elephant", "diagonal", "block", "river"),
        "cannon_screen": ("cannon", "screen", "mount", "capture"),
        "general_palace": ("general", "palace", "face", "flying"),
        "river_restrictions": ("river", "soldier", "elephant", "cross"),
        "history": ("history", "tradition", "origin", "development", "dynasty"),
        "current_topic": ("2026", "latest", "recent", "current", "news"),
    }
    result: dict[str, list[dict[str, str]]] = {}
    for topic in topics:
        terms = patterns.get(topic, ())
        matches: list[dict[str, str]] = []
        for source in sources:
            text = str(source.get("text_excerpt") or "").lower()
            matched = [term for term in terms if term in text]
            if matched:
                matches.append({"source_id": str(source.get("id")), "matched_terms": ",".join(matched), "url": str(source.get("url"))})
        result[topic] = matches
    return result


def _gemini_key() -> str | None:
    candidates = [os.getenv("GOOGLE_GROUNDING_API_KEY"), os.getenv("GEMINI_API_KEY"), os.getenv("GOOGLE_API_KEY")]
    for raw in (os.getenv("GEMINI_KEYS_JSON"), os.getenv("AI_ROUTER_GEMINI_KEYS_JSON")):
        if raw:
            try:
                values = json.loads(raw)
                if isinstance(values, list):
                    for value in values:
                        if isinstance(value, str):
                            candidates.append(value)
                        elif isinstance(value, dict) and value.get("key"):
                            candidates.append(str(value["key"]))
            except json.JSONDecodeError:
                pass
    return next((str(value).strip() for value in candidates if str(value or "").strip()), None)


def _native_google_grounding(puzzle: dict[str, Any], topics: list[str]) -> dict[str, Any] | None:
    enabled = _truthy(os.getenv("GOOGLE_GROUNDING_ENABLED"), False)
    required = _truthy(os.getenv("GOOGLE_GROUNDING_REQUIRED"), False)
    if not enabled:
        if required:
            raise ResearchGroundingError("GOOGLE_GROUNDING_REQUIRED=1 but GOOGLE_GROUNDING_ENABLED=0")
        return None
    key = _gemini_key()
    if not key:
        if required:
            raise ResearchGroundingError("Google Search grounding is required but no Gemini grounding key is configured")
        return None
    model = os.getenv("GOOGLE_GROUNDING_MODEL", "gemini-2.5-flash")
    prompt = (
        "Research the following Xiangqi lesson before script generation. Use Google Search grounding. "
        "Return a concise JSON object with source-backed facts and URLs. Do not invent rules. "
        f"Topics: {json.dumps(topics)}. Lesson: {json.dumps(puzzle, ensure_ascii=False)}"
    )
    payload = {
        "model": model,
        "input": prompt,
        "tools": [{"type": "google_search"}, {"type": "url_context"}],
    }
    try:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json=payload,
            timeout=max(30, int(os.getenv("GOOGLE_GROUNDING_TIMEOUT_SECONDS", "90"))),
        )
        response.raise_for_status()
        body = response.json()
        return {
            "provider": "gemini_google_search",
            "model": model,
            "status": "retrieved",
            "response": body,
            "response_sha256": hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
        }
    except Exception as exc:
        if required:
            raise ResearchGroundingError(f"Google Search grounding failed: {exc}") from exc
        return {"provider": "gemini_google_search", "status": "failed", "error": str(exc)[:500]}


def build_research_bundle(puzzle: dict[str, Any]) -> dict[str, Any]:
    existing = puzzle.get("researchBundle")
    if isinstance(existing, dict) and existing.get("status") == "grounded" and existing.get("sourceHash"):
        return existing
    topics = _required_topics(puzzle)
    timeout = max(5, int(os.getenv("RESEARCH_SOURCE_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))))
    sources = [_fetch_source(spec, timeout) for spec in _source_specs(puzzle)]
    retrieved = [source for source in sources if source.get("status") == "retrieved"]
    cached = _load_cached_sources() if _truthy(os.getenv("RESEARCH_ALLOW_CACHE"), True) else []
    cached_by_id = {str(source.get("id")): source for source in cached}
    for index, source in enumerate(sources):
        if source.get("status") == "failed" and str(source.get("id")) in cached_by_id:
            sources[index] = {**cached_by_id[str(source.get("id"))], "liveFetchError": source.get("error")}
    evidence_sources = [source for source in sources if source.get("status") in {"retrieved", "cached"}]
    evidence = _topic_evidence(evidence_sources, topics)
    missing_topics = [topic for topic in topics if not evidence.get(topic)]
    google_grounding = _native_google_grounding(puzzle, topics)
    if google_grounding and google_grounding.get("status") == "retrieved":
        google_text = json.dumps(google_grounding.get("response"), ensure_ascii=False).lower()
        for topic in list(missing_topics):
            if topic.replace("_", " ") in google_text or topic.split("_")[0] in google_text:
                missing_topics.remove(topic)
    if research_required() and (len(evidence_sources) < 2 or missing_topics):
        failed = [f"{item.get('id')}: {item.get('error')}" for item in sources if item.get("status") == "failed"]
        raise ResearchGroundingError(
            "Grounding evidence is insufficient; missing topics=" + ",".join(missing_topics) + "; failed_sources=" + ",".join(failed[:4])
        )
    bundle_core = {
        "contract": RESEARCH_CONTRACT,
        "status": "grounded" if evidence_sources else "ungrounded",
        "retrievedAt": datetime.now(timezone.utc).isoformat(),
        "requiredTopics": topics,
        "evidence": evidence,
        "sources": sources,
        "googleGrounding": google_grounding,
    }
    source_hash = hashlib.sha256(json.dumps(bundle_core, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    bundle = {**bundle_core, "sourceHash": source_hash}
    return bundle


def attach_research_bundle(puzzle: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(puzzle)
    enriched["researchBundle"] = build_research_bundle(enriched)
    enriched["groundingStatus"] = enriched["researchBundle"].get("status")
    enriched["groundingContract"] = RESEARCH_CONTRACT
    return enriched
