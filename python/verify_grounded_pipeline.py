from __future__ import annotations

import faulthandler
import json
import os
import sys

from creative_critic import review_job
from director import generate_director_data, make_job
from research_grounding import attach_research_bundle
from visual_director import add_visual_storyboard, validate_visual_storyboard


if __name__ == "__main__":
    faulthandler.dump_traceback_later(20, repeat=True, file=sys.stderr)
    os.environ["XIANGQI_RESEARCH_REQUIRED"] = "1"
    os.environ["RESEARCH_SOURCE_TIMEOUT_SECONDS"] = "5"
    os.environ["GOOGLE_GROUNDING_ENABLED"] = "0"
    os.environ["GOOGLE_GROUNDING_REQUIRED"] = "0"
    os.environ["YOUTUBE_PUBLISH_ENABLED"] = "0"
    os.environ["AI_ROUTER_REQUIRE_KEYS"] = "0"
    os.environ["PREPUBLISH_CRITIC_REQUIRED"] = "0"
    for key in ("AI_ROUTER_PATH", "AI_ROUTER_GEMINI_KEYS_JSON", "AI_ROUTER_HF_KEYS_JSON", "GEMINI_KEYS_JSON", "GEMINI_API_KEYS", "GOOGLE_API_KEYS", "GOOGLE_API_KEY", "GEMINI_API_KEY", "OLLAMA_BASE_URL"):
        os.environ.pop(key, None)
    puzzle = {
        "id": "grounded-smoke",
        "title": "Horse Leg and Elephant Eye",
        "language": "en",
        "content_type": "rules",
        "objective": "Explain Horse Leg and Elephant Eye without inventing a blocker.",
        "research_question": "What blocks a Xiangqi Horse and Elephant?",
        "fen": "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR r",
        "moves": ["0,6-0,5"],
        "visual_mode": "storyboard",
    }
    print("grounding:start", flush=True)
    puzzle = attach_research_bundle(puzzle)
    print("grounding:done", flush=True)
    director_data = generate_director_data(puzzle, operation="grounded-smoke")
    print("director:done", flush=True)
    job = make_job("grounded-smoke", puzzle, director_data)
    print("job:done", flush=True)
    job = add_visual_storyboard(job, puzzle)
    print("storyboard:done", flush=True)
    storyboard_errors = validate_visual_storyboard(job)
    review = review_job(job, puzzle, require_ai=False)
    print(json.dumps({
        "groundingStatus": puzzle.get("groundingStatus"),
        "sourceHash": puzzle["researchBundle"].get("sourceHash"),
        "claimProof": job.get("claimProof", {}).get("ok"),
        "storyboardErrors": storyboard_errors,
        "criticDecision": review.get("decision"),
        "criticScore": review.get("score"),
        "criticErrors": review.get("errors", []),
    }, ensure_ascii=False, indent=2))
    if puzzle.get("groundingStatus") != "grounded" or not job.get("claimProof", {}).get("ok") or storyboard_errors or review.get("decision") != "approve":
        raise SystemExit(1)
