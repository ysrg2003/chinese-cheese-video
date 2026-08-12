from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


def load_router() -> Any | None:
    external_path = os.getenv("AI_ROUTER_PATH", "").strip()
    if external_path:
        source_path = Path(external_path).expanduser().resolve() / "src"
        if str(source_path) not in sys.path:
            sys.path.insert(0, str(source_path))
    try:
        from ai_router import AIRouter
    except ImportError:
        return None
    config_dir = os.getenv("AI_ROUTER_CONFIG_DIR")
    state_db = os.getenv("AI_ROUTER_STATE_DB", "data/ai_router.db")
    return AIRouter(config_dir=config_dir, state_db=state_db)
