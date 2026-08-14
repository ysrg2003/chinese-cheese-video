import json
from pathlib import Path

from visual_director import add_visual_storyboard, validate_visual_storyboard

job = {
    "id": "semantic-visual-proof",
    "title": "How Xiangqi Routes Work",
    "language": "en",
    "visual_mode": "storyboard",
    "content_type": "definition",
    "fen": "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR w",
    "moves": [],
    "captions": [],
    "narrationSegments": [
        {"kind": "intro", "text": "A Xiangqi board has nine vertical files and ten horizontal ranks, creating ninety intersections.", "startSec": 0.0, "endSec": 3.4},
        {"kind": "intro", "text": "The pieces stand on those intersections, and a move travels along the lines between them.", "startSec": 3.4, "endSec": 6.8},
        {"kind": "intro", "text": "The horizontal river divides the two sides, while the central files connect the battlefield from one palace to the other.", "startSec": 6.8, "endSec": 10.2},
        {"kind": "intro", "text": "A chariot values an open file, a cannon values a line with the right screen, and a horse needs an unobstructed leg.", "startSec": 10.2, "endSec": 14.5},
    ],
    "durationInSeconds": 14.5,
    "audioSrc": "",
    "theme": "wood",
}
puzzle = {"curriculum_lesson_key": "en-005-the-9x10-point-board", "language": "en", "visual_mode": "storyboard"}
result = add_visual_storyboard(dict(job), puzzle)
errors = validate_visual_storyboard(result)
if errors:
    raise SystemExit("; ".join(errors))
Path("python/semantic_visual_sample_job.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"scenes": [{"index": scene["index"], "visualKind": scene["visualKind"], "semanticTags": scene["semanticTags"], "visualPlan": scene["visualPlan"]} for scene in result["visualStoryboard"]]}, ensure_ascii=False, indent=2))
