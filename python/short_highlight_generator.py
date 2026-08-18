from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

from systems.derivative_lineage import build_lineage_metadata, parent_fingerprint, window_fingerprint
from systems.durable_content_state import DurableStateStore


def _read(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _windows(parent: dict[str, Any], *, max_seconds: float = 58.0, limit: int = 3) -> list[dict[str, Any]]:
    moves = parent.get("moves") or []
    candidates: list[dict[str, Any]] = []
    for index, move in enumerate(moves):
        if not isinstance(move, dict):
            continue
        start = float(move.get("startSec") or max(0.0, (index * 2.0)))
        end = float(move.get("endSec") or (start + 2.0))
        if end <= start:
            continue
        pad = 1.5
        window_start = max(0.0, start - pad)
        window_end = min(float(parent.get("durationSeconds") or parent.get("duration") or end + pad), end + pad)
        if window_end <= window_start:
            continue
        reason = "capture" if move.get("captured") else "decision"
        if move.get("piece") in {"cannon", "rook", "knight"}:
            reason = "tactical decision" if not move.get("captured") else "tactical capture"
        candidates.append(
            {
                "start_sec": window_start,
                "end_sec": min(window_end, window_start + max_seconds),
                "highlight_reason": reason,
                "move_index": index,
                "move": move,
                "score": (10 if move.get("captured") else 0) + (3 if move.get("piece") in {"cannon", "rook", "knight"} else 0) + max(0.0, 1.0 - index / max(1, len(moves))),
            }
        )
    candidates.sort(key=lambda item: (-float(item["score"]), int(item["move_index"])))
    return candidates[: max(1, int(limit))]


def extract_highlights(*, parent_job_path: str | Path, db_path: str | Path, output_dir: str | Path, limit: int = 3, max_seconds: float = 58.0, reason: str = "Xiangqi highlight extraction") -> dict[str, Any]:
    parent = _read(parent_job_path)
    parent_id = str(parent.get("id") or Path(parent_job_path).stem)
    parent_fp = parent_fingerprint(parent)
    windows = _windows(parent, max_seconds=max_seconds, limit=limit)
    if not windows:
        return {"status": "no_candidate", "domain": "xiangqi", "reason": "parent has no timed move windows", "parent_job_id": parent_id}
    destination_root = Path(output_dir)
    if not destination_root.is_absolute():
        destination_root = ROOT / destination_root
    destination_root.mkdir(parents=True, exist_ok=True)
    store = DurableStateStore(db_path)
    existing = store.list_lineage(parent_id, limit=1000)
    results: list[dict[str, Any]] = []
    for window in windows:
        child_fp = window_fingerprint(parent=parent, start_sec=window["start_sec"], end_sec=window["end_sec"], reason=window["highlight_reason"], extra={"move_index": window["move_index"]})
        if any(str(item.get("short_fingerprint")) == child_fp for item in existing):
            continue
        child_id = f"{parent_id}-short-{child_fp[:12]}"
        child = dict(parent)
        child["id"] = child_id
        child["title"] = f"{parent.get('title') or 'Xiangqi highlight'} — {window['highlight_reason'].title()}"
        child["content_type"] = "short"
        child["format"] = "short"
        child["source_kind"] = "highlight_short"
        child["parent_job_id"] = parent_id
        child["parent_fingerprint"] = parent_fp
        child["source_window"] = {"start_sec": window["start_sec"], "end_sec": window["end_sec"], "reason": window["highlight_reason"], "move_index": window["move_index"]}
        child["lineage"] = build_lineage_metadata(parent=parent, start_sec=window["start_sec"], end_sec=window["end_sec"], reason=window["highlight_reason"], child_id=child_id, child_fingerprint=child_fp, extra={"source_path": str(parent_job_path), "extraction_reason": reason})
        child_path = destination_root / f"{child_id}.json"
        child_path.write_text(json.dumps(child, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        store.record_lineage(short_id=child_id, short_fingerprint=child_fp, parent_job_id=parent_id, parent_fingerprint=parent_fp, source_kind="highlight_short", source_start_sec=window["start_sec"], source_end_sec=window["end_sec"], highlight_reason=window["highlight_reason"], metadata=child["lineage"], status="generated")
        store.record_variant(fingerprint=child_fp, domain_id="xiangqi", variant_kind="short_highlight", job_id=child_id, signature={"parent_job_id": parent_id, "source_window": child["source_window"]}, status="generated")
        results.append({"status": "generated", "job_id": child_id, "path": str(child_path), "source_window": child["source_window"], "fingerprint": child_fp})
    return {"status": "selected" if results else "no_candidate", "domain": "xiangqi", "parent_job_id": parent_id, "parent_fingerprint": parent_fp, "shorts": results}


__all__ = ["extract_highlights"]
