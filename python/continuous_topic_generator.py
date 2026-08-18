from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

from content_discovery import discover_all
from local_store import LocalStore, normalize_topic_key
from systems.durable_content_state import DurableStateStore, candidate_fingerprint


def _write(output_path: str | Path, payload: dict[str, Any]) -> str:
    destination = Path(output_path)
    if not destination.is_absolute():
        destination = ROOT / destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(destination)


def _candidate_key(candidate: dict[str, Any]) -> str:
    payload = candidate.get("payload") or {}
    return normalize_topic_key(payload.get("topic_key") or candidate.get("topic_key") or candidate.get("title"))


def _fresh_candidate(store: LocalStore, language: str) -> dict[str, Any] | None:
    published_topics = store.get_published_topic_keys(language)
    published_moves = store.get_published_move_signatures(language)
    candidates = []
    for candidate in store.list_candidates(status="discovered", limit=500):
        if candidate.get("language") != language:
            continue
        if _candidate_key(candidate) in published_topics:
            continue
        payload = candidate.get("payload") or {}
        signature = json.dumps({"fen": payload.get("fen"), "moves": payload.get("moves") or []}, ensure_ascii=False, sort_keys=True)
        if signature in published_moves:
            continue
        candidates.append(candidate)
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-float(item.get("priority_score") or 0), str(item.get("id") or "")))
    return candidates[0]


def generate_next(*, db_path: str | Path, output_path: str | Path, domain: str = "xiangqi", language: str = "en", allow_discovery: bool = True, reason: str = "post-curriculum Xiangqi topic generation") -> dict[str, Any]:
    if domain != "xiangqi":
        raise ValueError(f"continuous_topic_generator only accepts domain=xiangqi, got {domain!r}")
    store = LocalStore(db_path)
    gate = store.curriculum_gate(language)
    state = DurableStateStore(db_path)
    state_key = f"{domain}:continuous_generation"
    if not gate.get("complete"):
        result = {
            "status": "no_candidate",
            "domain": domain,
            "reason": "curriculum_incomplete",
            "curriculum": gate,
        }
        state.set_generation_state(state_key=state_key, domain_id=domain, value={"last_status": result["status"], "reason": result["reason"], "curriculum_published": gate.get("published", 0)})
        return result
    candidate = _fresh_candidate(store, language)
    discovery_metrics = None
    discovery_allowed = allow_discovery and os.getenv("CONFIGURED_AUTOMATION_DISCOVERY_ENABLED", "1").lower() in {"1", "true", "yes"}
    if candidate is None and discovery_allowed:
        discovery_metrics = discover_all(store, 20)
        candidate = _fresh_candidate(store, language)
    if candidate is None:
        result = {"status": "no_candidate", "domain": domain, "reason": "discovery_exhausted", "discovery": discovery_metrics}
        state.set_generation_state(state_key=state_key, domain_id=domain, value={"last_status": result["status"], "reason": result["reason"], "discovery": discovery_metrics})
        return result
    payload = dict(candidate.get("payload") or {})
    payload.update(
        {
            "id": candidate["id"],
            "title": candidate.get("title") or payload.get("title"),
            "language": language,
            "content_type": candidate.get("content_type") or payload.get("content_type"),
            "topic_key": _candidate_key(candidate),
            "source_kind": candidate.get("source_kind"),
            "source_url": candidate.get("source_url"),
            "generation_reason": reason,
        }
    )
    destination = _write(output_path, payload)
    fingerprint = str(candidate.get("fingerprint") or candidate_fingerprint({"domainId": domain, "contentType": payload.get("content_type"), "language": language, "title": payload.get("title"), "topic": payload.get("topic_key"), "sourceUrl": payload.get("source_url")}))
    state.record_variant(fingerprint=fingerprint, domain_id=domain, variant_kind="post_curriculum_topic", job_id=str(candidate["id"]), signature={"topic_key": payload.get("topic_key"), "source_kind": payload.get("source_kind"), "content_type": payload.get("content_type")}, status="selected")
    result = {"status": "selected", "domain": domain, "source": "post_curriculum_topic", "candidate_id": str(candidate["id"]), "job_id": str(candidate["id"]), "topic_key": payload.get("topic_key"), "content_type": payload.get("content_type"), "input": destination, "discovery": discovery_metrics}
    state.set_generation_state(state_key=state_key, domain_id=domain, value={"last_status": result["status"], "last_candidate_id": candidate["id"], "last_topic_key": payload.get("topic_key"), "fingerprint": fingerprint})
    return result


__all__ = ["generate_next"]
