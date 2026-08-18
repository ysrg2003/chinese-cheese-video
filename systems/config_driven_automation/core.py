from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

PATH_KEYS = {
    "path",
    "file",
    "queue_path",
    "facts_path",
    "sample_path",
    "profiles_path",
    "matches_path",
    "evidence_root",
    "output_path",
    "config_path",
}


class AutomationConfigError(ValueError):
    """Raised when a domain automation configuration violates the generic contract."""


def _resolve_path(value: Any) -> Any:
    if not isinstance(value, str) or not value.strip():
        return value
    path = Path(value).expanduser()
    return str(path if path.is_absolute() else ROOT / path)


def _normalize_kwargs(kwargs: Any) -> dict[str, Any]:
    if kwargs is None:
        return {}
    if not isinstance(kwargs, dict):
        raise AutomationConfigError("automation stage kwargs must be an object")
    normalized: dict[str, Any] = {}
    for key, value in kwargs.items():
        normalized[str(key)] = _resolve_path(value) if str(key) in PATH_KEYS else value
    return normalized


def load_automation_config(path: str | Path | None = None, *, root: Path = ROOT) -> dict[str, Any]:
    raw_path = path or "config/automation.json"
    config_path = Path(raw_path).expanduser()
    if not config_path.is_absolute():
        config_path = root / config_path
    if not config_path.exists():
        raise AutomationConfigError(f"automation config not found: {config_path}")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AutomationConfigError(f"invalid automation config JSON: {config_path}: {exc}") from exc
    if not isinstance(config, dict):
        raise AutomationConfigError("automation config must be a JSON object")
    if int(config.get("schema_version") or 0) != 1:
        raise AutomationConfigError("automation config schema_version must be 1")
    domain_id = str(config.get("domain_id") or "").strip()
    if not domain_id:
        raise AutomationConfigError("automation config domain_id is required")
    stages = config.get("stages") or []
    if not isinstance(stages, list):
        raise AutomationConfigError("automation config stages must be an array")
    normalized_stages: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_stage in stages:
        if not isinstance(raw_stage, dict):
            raise AutomationConfigError("each automation stage must be an object")
        stage = dict(raw_stage)
        stage_id = str(stage.get("id") or "").strip()
        module = str(stage.get("module") or "").strip()
        entrypoint = str(stage.get("entrypoint") or "generate_next").strip()
        if not stage_id or stage_id in seen:
            raise AutomationConfigError(f"automation stage ids must be non-empty and unique: {stage_id!r}")
        if not module:
            raise AutomationConfigError(f"automation stage {stage_id!r} requires module")
        seen.add(stage_id)
        stage["id"] = stage_id
        stage["kind"] = str(stage.get("kind") or stage_id)
        stage["module"] = module
        stage["entrypoint"] = entrypoint
        stage["enabled"] = bool(stage.get("enabled", True))
        stage["on_error"] = str(stage.get("on_error") or "fail")
        if stage["on_error"] not in {"fail", "skip"}:
            raise AutomationConfigError(f"automation stage {stage_id!r} on_error must be fail or skip")
        stage["kwargs"] = _normalize_kwargs(stage.get("kwargs"))
        normalized_stages.append(stage)
    result = dict(config)
    result["schema_version"] = 1
    result["domain_id"] = domain_id
    result["stages"] = normalized_stages
    result["config_path"] = str(config_path)
    return result


def enabled_stage_ids(config: dict[str, Any]) -> list[str]:
    return [str(stage["id"]) for stage in config.get("stages", []) if stage.get("enabled", True)]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate and print a generic automation configuration")
    parser.add_argument("--config", default="config/automation.json")
    args = parser.parse_args()
    print(json.dumps(load_automation_config(args.config), ensure_ascii=False, indent=2))
