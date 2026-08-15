from __future__ import annotations

import json
from pathlib import Path

from timing import finalize_timing
from visual_director import add_visual_storyboard, validate_visual_storyboard

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "experiment-output" / "new-concept-job.json"
FEN = "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR r"


def main() -> int:
    narration = (
        "The tempo window is a teaching lens for noticing how initiative shifts after an exchange. "
        "It isolates the idea before we study a concrete position."
    )
    job = {
        "id": "sentence-supervision-new-concept-experiment",
        "title": "A New Concept: The Tempo Window",
        "language": "en",
        "content_type": "definition",
        "visual_mode": "storyboard",
        "fen": FEN,
        "moves": [],
        "narration": narration,
        "narrationSegments": [{
            "kind": "intro",
            "text": narration,
            "captionPosition": "bottom",
        }],
        "captions": [],
        "experimentOnly": True,
        "publicationEnabled": False,
    }
    puzzle = {
        "id": job["id"],
        "title": job["title"],
        "language": "en",
        "content_type": "definition",
        "visual_mode": "storyboard",
        "fen": FEN,
        "moves": [],
        "visualStoryboard": [],
    }
    job = add_visual_storyboard(job, puzzle)
    job = finalize_timing(job)
    errors = validate_visual_storyboard(job, audio_duration=float(job["durationInSeconds"]))
    if errors:
        raise SystemExit("; ".join(errors))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "publicationEnabled": job["publicationEnabled"],
        "supervision": job["sentenceVisualSupervision"],
        "intents": job["sentenceVisualIntents"],
        "segments": [
            {
                "sentenceId": item.get("sentenceId"),
                "text": item.get("text"),
                "visualKind": item.get("visualKind"),
                "visualPlan": item.get("visualPlan"),
            }
            for item in job["narrationSegments"]
        ],
        "storyboardSource": job["visualStoryboardSource"],
        "storyboardCount": len(job["visualStoryboard"]),
        "durationInSeconds": job["durationInSeconds"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
