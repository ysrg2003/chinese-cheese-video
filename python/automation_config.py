from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from systems.config_driven_automation.core import AutomationConfigError, enabled_stage_ids, load_automation_config

__all__ = ["AutomationConfigError", "enabled_stage_ids", "load_automation_config"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate and print a configured Xiangqi automation chain")
    parser.add_argument("--config", default="config/automation.json")
    args = parser.parse_args()
    print(json.dumps(load_automation_config(args.config), ensure_ascii=False, indent=2))
