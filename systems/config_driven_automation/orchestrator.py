from __future__ import annotations

import argparse
import importlib
import inspect
import json
from pathlib import Path
from typing import Any

from .core import load_automation_config


def _invoke_stage(stage: dict[str, Any], *, db_path: str | Path, output_path: str | Path, reason: str) -> dict[str, Any]:
    module = importlib.import_module(str(stage["module"]))
    entrypoint = getattr(module, str(stage.get("entrypoint") or "generate_next"), None)
    if not callable(entrypoint):
        raise RuntimeError(f"automation stage {stage['id']!r} entrypoint is not callable: {stage['module']}.{stage.get('entrypoint')}")
    kwargs = dict(stage.get("kwargs") or {})
    parameters = inspect.signature(entrypoint).parameters
    accepts_var_kwargs = any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())
    for key, value in (("db_path", db_path), ("output_path", output_path), ("reason", reason)):
        if accepts_var_kwargs or key in parameters:
            kwargs.setdefault(key, value)
    result = entrypoint(**kwargs)
    if not isinstance(result, dict):
        raise RuntimeError(f"automation stage {stage['id']!r} returned a non-object result")
    return result


def run_automation(*, config_path: str | Path, db_path: str | Path, output_path: str | Path, reason: str = "configured automation stage chain") -> dict[str, Any]:
    config = load_automation_config(config_path)
    attempts: list[dict[str, Any]] = []
    for stage in config["stages"]:
        if not stage.get("enabled", True):
            attempts.append({"stage": stage["id"], "status": "disabled"})
            continue
        try:
            result = _invoke_stage(stage, db_path=db_path, output_path=output_path, reason=reason)
        except Exception as exc:
            if str(stage.get("on_error") or "fail") != "skip":
                raise
            record = {"stage": stage["id"], "status": "stage_error_skipped", "error_type": type(exc).__name__, "error": str(exc)[:500]}
            attempts.append(record)
            continue
        record = {"stage": stage["id"], **result}
        attempts.append(record)
        status = str(result.get("status") or "").lower()
        if status == "selected":
            return {"status": "selected", "domain": config["domain_id"], "stage": stage["id"], "selection": result, "attempts": attempts, "config_path": config["config_path"]}
        if status in {"no_candidate", "no_valid_candidate", "skipped", "disabled"}:
            continue
        raise RuntimeError(f"automation stage {stage['id']!r} returned unsupported status: {status!r}")
    return {"status": "no_valid_candidate", "domain": config["domain_id"], "attempts": attempts, "config_path": config["config_path"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a configured generic content-selection and fallback chain")
    parser.add_argument("--config", default="config/automation.json")
    parser.add_argument("--db-path", default="data/framework.db")
    parser.add_argument("--output", default="output/scheduled-job.json")
    parser.add_argument("--reason", default="configured automation stage chain")
    args = parser.parse_args()
    result = run_automation(config_path=args.config, db_path=args.db_path, output_path=args.output, reason=args.reason)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"selected", "no_valid_candidate"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
