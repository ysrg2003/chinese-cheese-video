from __future__ import annotations

import argparse
import json
from pathlib import Path

from visual_director import add_visual_storyboard, validate_visual_storyboard


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one isolated Xiangqi sentence through storyboard supervision without publication.")
    parser.add_argument("--sentence", required=True)
    parser.add_argument("--output-dir", default="single-sentence-experiment-output")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    job = {
        "id": "single-sentence-parity-experiment",
        "title": "Single Sentence Parity Experiment",
        "language": "en",
        "visual_mode": "storyboard",
        "content_type": "rules",
        "narrationSegments": [{"kind": "intro", "text": args.sentence, "captionPosition": "bottom"}],
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
        "curriculum_lesson_key": "isolated-single-sentence",
        "moves": [],
        "visualStoryboard": [],
    }
    result = add_visual_storyboard(job, puzzle)
    errors = validate_visual_storyboard(result)
    if errors:
        raise SystemExit("visual storyboard validation failed: " + "; ".join(errors))
    output_job = output_dir / "job.json"
    output_job.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "sentence": args.sentence,
        "publicationEnabled": bool(result.get("publicationEnabled")),
        "visualStoryboardSource": result.get("visualStoryboardSource"),
        "sentenceVisualIntents": result.get("sentenceVisualIntents", []),
        "segments": [
            {
                "sentenceId": segment.get("sentenceId"),
                "visualKind": segment.get("visualKind"),
                "visualPlan": segment.get("visualPlan"),
            }
            for segment in result.get("narrationSegments", [])
        ],
        "jobPath": str(output_job),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
