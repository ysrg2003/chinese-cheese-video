from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from content_discovery import discover_all
from local_store import LocalStore
from systems.durable_content_state import DurableStateStore

ROOT = Path(__file__).resolve().parents[1]


def _write_output(output_path: str | Path, payload: dict[str, Any]) -> str:
    destination = Path(output_path)
    if not destination.is_absolute():
        destination = ROOT / destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(destination)


def _candidate_payload(candidate: dict[str, Any], language: str) -> dict[str, Any]:
    payload = dict(candidate.get("payload") or {})
    payload.update(
        {
            "id": str(candidate.get("id") or payload.get("id") or "candidate"),
            "title": str(candidate.get("title") or payload.get("title") or "Untitled Xiangqi candidate"),
            "language": language,
            "content_type": str(candidate.get("content_type") or payload.get("content_type") or "definition"),
            "topic_key": candidate.get("topic_key") or payload.get("topic_key"),
            "source_url": candidate.get("source_url") or payload.get("source_url"),
            "source_kind": candidate.get("source_kind") or payload.get("source_kind") or "provided",
        }
    )
    return payload


def select_job(*, db_path: str | Path, output_path: str | Path, domain: str = "xiangqi", language: str = "en", discover_limit: int = 20, reason: str = "configured Xiangqi automation") -> dict[str, Any]:
    if domain != "xiangqi":
        raise ValueError(f"configured_automation_adapter only accepts domain=xiangqi, got {domain!r}")
    store = LocalStore(db_path)
    candidate = store.get_next_curriculum_candidate(language)
    source = "curriculum"
    if candidate is None:
        candidates = store.list_candidates(status="discovered", limit=max(1, int(discover_limit)))
        candidate = candidates[0] if candidates else None
        source = "configured_discovery"
    if candidate is None and os.getenv("CONFIGURED_AUTOMATION_DISCOVERY_ENABLED", "0").lower() in {"1", "true", "yes"}:
        discovery = discover_all(store, int(discover_limit))
        candidates = store.list_candidates(status="discovered", limit=max(1, int(discover_limit)))
        candidate = candidates[0] if candidates else None
        source = "configured_discovery"
    if candidate is None:
        result = {"status": "no_valid_candidate", "domain": domain, "reason": "no curriculum or discovered candidate", "run_reason": reason}
    else:
        job = _candidate_payload(candidate, language)
        result = {
            "status": "selected",
            "domain": domain,
            "source": source,
            "job_id": str(candidate.get("id") or job["id"]),
            "candidate_id": str(candidate.get("id") or job["id"]),
            "input": _write_output(output_path, job),
            "content_type": job.get("content_type"),
            "topic_key": job.get("topic_key"),
        }
        if source == "configured_discovery":
            result["discovery_enabled"] = os.getenv("CONFIGURED_AUTOMATION_DISCOVERY_ENABLED", "0")
    DurableStateStore(db_path).record_automation_run(
        run_id=f"configured-{result.get('candidate_id') or result['status']}",
        domain_id=domain,
        status=str(result["status"]),
        result=result,
    )
    return result


__all__ = ["select_job"]
