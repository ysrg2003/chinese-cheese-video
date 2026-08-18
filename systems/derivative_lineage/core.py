from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Iterable


def parent_fingerprint(parent: dict[str, Any]) -> str:
    metadata = parent.get("metadata") or {}
    recorded = str(
        metadata.get("content_fingerprint")
        or metadata.get("fingerprint")
        or parent.get("fingerprint")
        or ""
    ).strip()
    if recorded:
        return recorded
    stable = {
        "id": parent.get("id"),
        "title": parent.get("title"),
        "sourceUrl": parent.get("sourceUrl") or parent.get("source_url"),
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def window_fingerprint(*, parent: dict[str, Any], start_sec: float, end_sec: float, reason: str, extra: dict[str, Any] | None = None) -> str:
    if float(end_sec) <= float(start_sec):
        raise ValueError("source window end must be greater than start")
    signature = {
        "parent": parent_fingerprint(parent),
        "start": round(float(start_sec), 3),
        "end": round(float(end_sec), 3),
        "reason": str(reason),
        "extra": extra or {},
    }
    return hashlib.sha256(json.dumps(signature, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def build_lineage_metadata(*, parent: dict[str, Any], start_sec: float, end_sec: float, reason: str, child_id: str, child_fingerprint: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    if float(end_sec) <= float(start_sec):
        raise ValueError("source window end must be greater than start")
    metadata = deepcopy(parent.get("metadata") or {})
    metadata["parent_job_id"] = str(parent.get("id") or "")
    metadata["parent_fingerprint"] = parent_fingerprint(parent)
    metadata["source_start_sec"] = float(start_sec)
    metadata["source_end_sec"] = float(end_sec)
    metadata["lineage_reason"] = str(reason)
    metadata["child_id"] = str(child_id)
    metadata["child_fingerprint"] = str(child_fingerprint)
    if extra:
        metadata["lineage_extra"] = deepcopy(extra)
    return metadata


def unused_windows(*, candidates: Iterable[dict[str, Any]], existing: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    used = {
        (round(float(item.get("source_start_sec") or 0.0), 3), round(float(item.get("source_end_sec") or 0.0), 3), str(item.get("highlight_reason") or item.get("reason") or ""))
        for item in existing
    }
    result = []
    for candidate in candidates:
        key = (
            round(float(candidate.get("start_sec") or candidate.get("start") or 0.0), 3),
            round(float(candidate.get("end_sec") or candidate.get("end") or 0.0), 3),
            str(candidate.get("highlight_reason") or candidate.get("reason") or ""),
        )
        if key not in used:
            result.append(dict(candidate))
    return result


__all__ = ["build_lineage_metadata", "parent_fingerprint", "unused_windows", "window_fingerprint"]
