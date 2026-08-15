from __future__ import annotations

import json
from pathlib import Path

from visual_director import add_visual_storyboard, validate_visual_storyboard


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "new-sentence-experiment-output"


def main() -> None:
    narration = "The river separates the territories, and the palaces restrict the Generals to a narrow central zone."
    job = {
        "id": "new-sentence-river-palace-experiment",
        "title": "A New Xiangqi Rule Idea",
        "language": "en",
        "visual_mode": "storyboard",
        "content_type": "definition",
        "narration": narration,
        "narrationSegments": [{"kind": "intro", "text": narration, "captionPosition": "bottom"}],
        "moves": [],
        "captions": [],
        "publicationEnabled": False,
        "publish": False,
    }
    puzzle = {
        "id": job["id"],
        "language": "en",
        "content_type": "definition",
        "visual_mode": "storyboard",
        "curriculum_lesson_key": "isolated-new-sentence-river-palaces",
        "moves": [],
        "visualStoryboard": [],
    }
    result = add_visual_storyboard(job, puzzle)
    errors = validate_visual_storyboard(result)
    if errors:
        raise SystemExit("visual storyboard validation failed: " + "; ".join(errors))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    output_job = OUTPUT / "new-sentence-job.json"
    output_job.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "output": str(output_job),
        "publicationEnabled": bool(result.get("publicationEnabled")),
        "sentenceVisualIntents": result.get("sentenceVisualIntents", []),
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
        "durationInSeconds": result.get("durationInSeconds"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
