from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


def build_report(db_path: str, job_id: str | None = None) -> dict[str, Any]:
    path = Path(db_path)
    if not path.exists():
        return {"database": str(path), "exists": False, "records": []}
    operation = f"director:{job_id}" if job_id else None
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        if operation:
            rows = connection.execute(
                "SELECT operation, provider, model, key_id, project, status, error_class, status_code, usage_json, created_at FROM provider_calls WHERE operation = ? ORDER BY id",
                (operation,),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT operation, provider, model, key_id, project, status, error_class, status_code, usage_json, created_at FROM provider_calls ORDER BY id"
            ).fetchall()
    records = [dict(row) for row in rows]
    statuses = Counter(record["status"] for record in records)
    models = Counter(record["model"] for record in records)
    keys = Counter(record["key_id"] for record in records)
    usage_totals: Counter[str] = Counter()
    for record in records:
        try:
            usage = json.loads(record.get("usage_json") or "{}")
        except json.JSONDecodeError:
            usage = {}
        for field in ("totalTokenCount", "promptTokenCount", "candidatesTokenCount", "total_tokens", "prompt_tokens", "completion_tokens"):
            if isinstance(usage.get(field), (int, float)):
                usage_totals[field] += usage[field]
    return {
        "database": str(path),
        "exists": True,
        "job_id": job_id,
        "attempts": len(records),
        "successes": statuses.get("success", 0),
        "failures": statuses.get("failed", 0),
        "models": dict(models),
        "key_ids": dict(keys),
        "usage_totals": dict(usage_totals),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Report AI Router consumption for Chinese Cheese Video jobs")
    parser.add_argument("--db", default="data/ai_router.db", help="AI Router SQLite database")
    parser.add_argument("--job-id", help="Filter to one video job; matches operation director:<job-id>")
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()
    report = build_report(args.db, args.job_id)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
