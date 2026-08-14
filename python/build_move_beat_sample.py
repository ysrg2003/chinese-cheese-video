"""Build a deterministic move-beat proof job for CI without external AI or TTS."""

from __future__ import annotations

import json
from pathlib import Path

from director import build_narration_segments
from timing import finalize_timing
from visual_director import add_visual_storyboard, validate_visual_storyboard


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "python" / "move_beat_sample_job.json"
FEN = "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR r"


def main() -> int:
    job = {
        "id": "move-beat-sample",
        "title": "How An Elephant Changes The Position",
        "language": "en",
        "fen": FEN,
        "visual_mode": "storyboard",
        "content_type": "rules",
        "moves": [{
            "ply": 1,
            "from": [2, 9],
            "to": [4, 7],
            "piece": "bishop",
            "side": "red",
            "label": "Guard the diagonal",
            "purpose": "guard the central diagonal",
            "opponentReply": "block the elephant eye",
            "effect": "the bishop becomes restricted",
        }],
        "narration": "This lesson explains the elephant's route, the opponent's reply, and the restriction that changes the position.",
        "analysis_focus": "the elephant eye and the river limit",
        "narrationSegments": [],
        "captions": [],
    }
    narration, segments = build_narration_segments(job["narration"], job["moves"], "en", "rules", job["analysis_focus"])
    job["narration"] = narration
    job["narrationSegments"] = segments
    job = add_visual_storyboard(job, {"language": "en", "visual_mode": "storyboard", "content_type": "rules"})
    job = finalize_timing(job)
    errors = validate_visual_storyboard(job, audio_duration=float(job["durationInSeconds"]))
    if errors:
        raise SystemExit("; ".join(errors))
    OUTPUT.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "durationInSeconds": job["durationInSeconds"],
        "segments": [{"kind": item.get("kind"), "movePhase": item.get("movePhase"), "visualKind": item.get("visualKind")} for item in job["narrationSegments"]],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
