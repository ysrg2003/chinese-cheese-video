from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from systems.config_driven_automation.orchestrator import run_automation

__all__ = ["run_automation"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the configured Xiangqi automation adapter chain")
    parser.add_argument("--config", default="config/automation.json")
    parser.add_argument("--db-path", default="data/chinese_cheese_video.db")
    parser.add_argument("--output", default="output/configured-selection.json")
    parser.add_argument("--reason", default="configured Xiangqi automation")
    args = parser.parse_args()
    result = run_automation(config_path=args.config, db_path=args.db_path, output_path=args.output, reason=args.reason)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"selected", "no_valid_candidate"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
