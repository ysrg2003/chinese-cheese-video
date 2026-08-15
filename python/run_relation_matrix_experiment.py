from __future__ import annotations

import json
from pathlib import Path

from visual_director import add_visual_storyboard, validate_visual_storyboard


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "relation-matrix-experiment-output"
SENTENCES = [
    "The river separates the territories, and the palaces restrict the Generals to a narrow central zone.",
    "The Horse's leg blocks a diagonal jump when the adjacent point is occupied.",
    "A Cannon needs one screen before it can capture a target.",
    "The board is a network of intersections, not a set of enclosed squares.",
]


def main() -> None:
    job = {
        "id": "relation-matrix-experiment",
        "title": "New Sentence Visual Contract Test",
        "language": "en",
        "visual_mode": "storyboard",
        "content_type": "rules",
        "narrationSegments": [{"kind": "intro", "text": sentence, "captionPosition": "bottom"} for sentence in SENTENCES],
        "moves": [],
        "captions": [],
        "publicationEnabled": False,
        "publish": False,
    }
    puzzle = {
        "id": job["id"],
        "language": "en",
        "content_type": "rules",
        "visual_mode": "storyboard",
        "curriculum_lesson_key": "isolated-relation-matrix",
        "moves": [],
        "visualStoryboard": [],
    }
    result = add_visual_storyboard(job, puzzle)
    errors = validate_visual_storyboard(result)
    if errors:
        raise SystemExit("visual storyboard validation failed: " + "; ".join(errors))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    output_job = OUTPUT / "relation-matrix-job.json"
    output_job.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "output": str(output_job),
        "publicationEnabled": bool(result.get("publicationEnabled")),
        "sentenceCount": len(result.get("sentenceVisualIntents", [])),
        "intents": result.get("sentenceVisualIntents", []),
        "segments": [
            {
                "sentenceId": segment.get("sentenceId"),
                "text": segment.get("text"),
                "visualKind": segment.get("visualKind"),
                "visualPlan": segment.get("visualPlan"),
            }
            for segment in result.get("narrationSegments", [])
        ],
        "storyboardSource": result.get("visualStoryboardSource"),
        "storyboardCount": len(result.get("visualStoryboard", [])),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
