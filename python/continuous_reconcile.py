"""Retry resumable YouTube publication work without rendering or uploading again."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Continuously reconcile public YouTube publications")
    parser.add_argument("--max-attempts", type=int, default=int(os.getenv("RECONCILIATION_MAX_ATTEMPTS", "8")))
    parser.add_argument("--initial-delay-seconds", type=int, default=int(os.getenv("RECONCILIATION_INITIAL_DELAY_SECONDS", "60")))
    parser.add_argument("--max-delay-seconds", type=int, default=int(os.getenv("RECONCILIATION_MAX_DELAY_SECONDS", "1800")))
    parser.add_argument("--max-runtime-minutes", type=int, default=int(os.getenv("RECONCILIATION_MAX_RUNTIME_MINUTES", "330")))
    parser.add_argument("--output", dest="output_path", default=os.getenv("RECONCILIATION_OUTPUT", "continuous-reconcile.json"))
    return parser.parse_args()


def _extract_json(stdout: str) -> dict[str, Any]:
    text = str(stdout or "").strip()
    if not text:
        return {}
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(text[start : end + 1])
                return value if isinstance(value, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}


def _is_complete(report: dict[str, Any]) -> bool:
    selected = int(report.get("selected") or 0)
    failed = int(report.get("failed") or 0)
    published = int(report.get("published") or 0)
    return selected == 0 or (failed == 0 and published >= selected)


def _report_errors(report: dict[str, Any]) -> list[str]:
    items = report.get("items") or []
    errors = [str((item or {}).get("error") or "").lower() for item in items]
    if not errors:
        errors = [str(report.get("error") or report.get("stderr") or "").lower()]
    return [error for error in errors if error]


def _is_daily_quota_exhausted(report: dict[str, Any]) -> bool:
    return any("quotaexceeded" in error or "domain': 'youtube.quota" in error or 'domain": "youtube.quota' in error for error in _report_errors(report))


def _is_retryable(report: dict[str, Any]) -> bool:
    """Allow continuation only for errors likely to clear without configuration changes."""
    if _is_daily_quota_exhausted(report):
        return False
    retry_markers = (
        "429",
        "500",
        "502",
        "503",
        "504",
        "rate limit",
        "ratelimit",
        "try the request again",
        "temporarily",
        "timeout",
        "timed out",
        "connection reset",
        "backenderror",
        "internalerror",
    )
    errors = _report_errors(report)
    return bool(errors) and all(any(marker in error for marker in retry_markers) for error in errors)


def reconcile_until_complete(
    *,
    max_attempts: int,
    initial_delay_seconds: int,
    max_delay_seconds: int,
    max_runtime_minutes: int,
    output_path: str | Path,
    runner: Any = None,
    sleeper: Any = time.sleep,
    clock: Any = time.monotonic,
) -> int:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if initial_delay_seconds < 0 or max_delay_seconds < 0 or max_runtime_minutes <= 0:
        raise ValueError("retry delays must be non-negative and runtime must be positive")

    execute = runner or _run_reconcile_process
    started = clock()
    delay = initial_delay_seconds
    attempts: list[dict[str, Any]] = []
    final_report: dict[str, Any] = {}
    exit_code = 1

    for attempt in range(1, max_attempts + 1):
        elapsed = clock() - started
        if elapsed >= max_runtime_minutes * 60:
            break
        try:
            report = execute()
            if not isinstance(report, dict):
                report = {"enabled": True, "selected": 0, "published": 0, "failed": 1, "error": "invalid reconciliation report"}
        except Exception as exc:  # pragma: no cover - guarded by deterministic tests through runner return values
            report = {"enabled": True, "selected": 1, "published": 0, "failed": 1, "error": str(exc)}
        final_report = report
        attempts.append({"attempt": attempt, "elapsed_seconds": round(clock() - started, 3), "report": report})
        if _is_complete(report):
            exit_code = 0
            break
        if not _is_retryable(report):
            final_report = dict(report)
            final_report["retryable"] = False
            if _is_daily_quota_exhausted(report):
                final_report["cooldown_reason"] = "youtube_daily_quota_exhausted"
            break
        if attempt < max_attempts:
            remaining = max_runtime_minutes * 60 - (clock() - started)
            wait_seconds = min(delay, max_delay_seconds, max(0, int(remaining)))
            if wait_seconds > 0:
                sleeper(wait_seconds)
            delay = min(max_delay_seconds, max(delay * 2, 1))

    result = {
        "status": "complete" if exit_code == 0 else ("quota_cooldown" if final_report.get("cooldown_reason") else ("non_retryable_failure" if final_report.get("retryable") is False else "retry_window_exhausted")),
        "attempts": attempts,
        "attempt_count": len(attempts),
        "final_report": final_report,
        "max_attempts": max_attempts,
        "max_runtime_minutes": max_runtime_minutes,
    }
    output = Path(output_path)
    if not output.is_absolute():
        output = ROOT / output
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


def _run_reconcile_process() -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "python" / "reconcile_youtube.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    report = _extract_json(completed.stdout)
    if completed.returncode != 0:
        report.setdefault("selected", 1)
        report.setdefault("published", 0)
        report.setdefault("failed", 1)
        report["process_returncode"] = completed.returncode
        if completed.stderr:
            report["stderr"] = completed.stderr[-2000:]
    return report


if __name__ == "__main__":
    raise SystemExit(reconcile_until_complete(**vars(parse_args())))
