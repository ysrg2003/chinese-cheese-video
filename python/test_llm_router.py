from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from llm_router import ProviderFailure, ProviderRouter
from local_store import LocalStore


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "router.db"
        os.environ["LOCAL_DB_PATH"] = str(db_path)
        os.environ["GEMINI_KEYS_JSON"] = '[{"id":"key-1","key":"first","project":"p1"},{"id":"key-2","key":"second","project":"p2"}]'
        os.environ["GEMINI_PRIMARY_MODEL"] = "gemini-2.5-flash"
        os.environ["GEMINI_SECONDARY_MODEL"] = "gemini-2.5-flash-lite"
        os.environ.pop("HF_TOKEN", None)
        store = LocalStore(db_path)
        router = ProviderRouter(store)
        attempts: list[tuple[str, str]] = []

        def fake_gemini(slot, model, system_prompt, user_prompt):
            attempts.append((model, slot.slot_id))
            if (model, slot.slot_id) == ("gemini-2.5-flash", "key-1"):
                raise ProviderFailure("quota", retryable=True, cooldown_seconds=0, status_code=429)
            if (model, slot.slot_id) == ("gemini-2.5-flash", "key-2"):
                raise ProviderFailure("temporary", retryable=True, cooldown_seconds=0, status_code=503)
            return {"title": "fallback success"}, {"totalTokenCount": 12}

        with patch("llm_router.time.sleep"), patch.object(router, "_call_gemini", side_effect=fake_gemini):
            result = router.generate_json(system_prompt="system", user_prompt="user", operation="test")

        assert result["title"] == "fallback success"
        assert attempts == [
            ("gemini-2.5-flash", "key-1"),
            ("gemini-2.5-flash", "key-2"),
            ("gemini-2.5-flash-lite", "key-1"),
        ], attempts
        state = store.get_provider_state("gemini", "gemini-2.5-flash", "key-1")
        assert state and state["consecutive_failures"] == 1 and state["total_calls"] == 1
        assert store.health()["ai_provider_calls"] == 3
        print("provider rotation test passed")


if __name__ == "__main__":
    main()
