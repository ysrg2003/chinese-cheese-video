from __future__ import annotations

import json
import os

from research_grounding import attach_research_bundle


if __name__ == "__main__":
    os.environ.setdefault("XIANGQI_RESEARCH_REQUIRED", "1")
    os.environ.setdefault("GOOGLE_GROUNDING_ENABLED", "0")
    os.environ.setdefault("GOOGLE_GROUNDING_REQUIRED", "0")
    puzzle = {
        "title": "Horse Leg and Elephant Eye",
        "objective": "Explain the Horse Leg and Elephant Eye blockers accurately before script generation.",
        "content_type": "rules",
        "research_question": "What blocks a Xiangqi Horse and Elephant?",
    }
    bundle = attach_research_bundle(puzzle)["researchBundle"]
    print(json.dumps({
        "status": bundle.get("status"),
        "sourceHash": bundle.get("sourceHash"),
        "retrievedSources": [item.get("id") for item in bundle.get("sources", []) if item.get("status") == "retrieved"],
        "requiredTopics": bundle.get("requiredTopics"),
        "evidenceTopics": {key: len(value) for key, value in bundle.get("evidence", {}).items()},
    }, ensure_ascii=False, indent=2))
