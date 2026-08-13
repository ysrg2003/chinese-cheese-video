from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    router_path = os.getenv("AI_ROUTER_PATH", "").strip()
    if router_path:
        source_path = Path(router_path).expanduser().resolve() / "src"
        sys.path.insert(0, str(source_path))
    from ai_router import AIRouter

    router = AIRouter(
        config_dir=os.getenv("AI_ROUTER_CONFIG_DIR"),
        state_db=os.getenv("AI_ROUTER_STATE_DB", "data/ai_router.db"),
    )
    try:
        counts = {provider_id: len(router.config.keys_for(provider_id)) for provider_id in router.config.providers}
        chain = [
            {"provider": spec.provider_id, "model": spec.model}
            for spec in router.config.model_chain(os.getenv("AI_ROUTER_CHAIN", "default"))
        ]
        print(json.dumps({"key_counts": counts, "model_chain": chain}, ensure_ascii=False))
        if os.getenv("AI_ROUTER_REQUIRE_KEYS", "1").lower() in {"1", "true", "yes"}:
            required = {"google_gemini", "huggingface"}
            missing = sorted(provider for provider in required if counts.get(provider, 0) == 0)
            if missing:
                raise RuntimeError("AI Router key pools are empty for: " + ", ".join(missing))
        return 0
    finally:
        router.close()


if __name__ == "__main__":
    raise SystemExit(main())
