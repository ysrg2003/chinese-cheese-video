#!/usr/bin/env python3
"""Validate reusable system capsule folders."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"ya29\.[0-9A-Za-z_-]{20,}"),
    re.compile(r"gh[pousr]_[0-9A-Za-z]{20,}"),
    re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
]


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("systems_root", type=Path)
    parser.add_argument("--forbid-import", action="append", default=[])
    args = parser.parse_args()
    root = args.systems_root.resolve()
    if not root.exists() or not root.is_dir():
        fail(f"missing systems root: {root}")
    capsules = [path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".") and path.name != "__pycache__"]
    if not capsules:
        fail("no system capsule directories found")
    checked = []
    for capsule in sorted(capsules):
        contract = capsule / "contract.json"
        core = capsule / "core.py"
        adapters = capsule / "adapters"
        tests = capsule / "tests"
        examples = capsule / "examples"
        for required in (contract, core, adapters, tests, examples):
            if not required.exists():
                fail(f"{capsule.name}: missing {required.relative_to(capsule)}")
        try:
            data = json.loads(contract.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(f"{capsule.name}: invalid contract JSON: {exc}")
        for key in ("name", "purpose", "inputs", "outputs", "statuses", "errors"):
            if key not in data:
                fail(f"{capsule.name}: contract missing {key}")
        texts = []
        for path in capsule.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".json", ".md", ".txt"}:
                text = path.read_text(encoding="utf-8")
                texts.append((path, text))
                for pattern in SECRET_PATTERNS:
                    if pattern.search(text):
                        fail(f"{capsule.name}: secret-like value in {path.relative_to(root)}")
        core_text = core.read_text(encoding="utf-8")
        for forbidden in args.forbid_import:
            if forbidden in core_text:
                fail(f"{capsule.name}: forbidden domain import {forbidden}")
        checked.append({"name": capsule.name, "contract": str(contract.relative_to(root))})
    print(json.dumps({"status": "ok", "capsules": checked}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
