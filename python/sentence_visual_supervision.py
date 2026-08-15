from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

SENTENCE_RE = re.compile(r"(?<=[.!?。！？])\s+|(?<=[。！？])")
ARABIC_RE = re.compile(r"[\u0600-\u06ff]")

KNOWN_TREATMENTS: list[tuple[tuple[str, ...], str, str, list[str], str]] = [
    (("river", "palace", "territor", "河界", "九宫"), "region_split", "river_palaces", ["river_band", "territory_split", "palace_x"], "board_state"),
    (("intersection", "point", "file", "rank", "coordinate", "交叉点", "坐标"), "coordinate_map", "coordinate_map", ["files", "ranks", "coordinate_endpoints"], "board_state"),
    (("horse leg", "horse's leg", "马腿"), "horse_leg", "rule_focus", ["piece_anchor", "horse_leg", "legal_destinations"], "claim_proof"),
    (("elephant eye", "象眼"), "elephant_eye", "rule_focus", ["piece_anchor", "elephant_eye", "river_limit"], "claim_proof"),
    (("cannon screen", "one screen", "screen", "炮架"), "cannon_screen", "cannon_screen", ["piece_anchor", "cannon_screen", "cannon_target"], "claim_proof"),
    (("checkmate", "general", "将军", "将死"), "goal_focus", "generals_goal", ["palace_piece_anchor", "pressure_marker"], "board_state"),
    (("piece", "pawn", "horse", "chariot", "rook", "cannon", "elephant", "advisor", "soldier", "棋子"), "piece_spotlight", "piece_spotlight", ["piece_anchor", "legal_destinations"], "board_state"),
    (("history", "origin", "dynasty", "tradition", "heritage", "历史", "文化"), "history_context", "history_timeline", ["board_overview"], "research_bundle"),
    (("compare", "different", "unlike", "versus", "comparison", "比较"), "comparison", "comparison_split", ["before_after"], "editorial_bridge"),
    (("question", "pause", "choose", "your move", "问题"), "question_reveal", "question_reveal", ["legal_destinations"], "board_state"),
]


def split_sentences(text: str) -> list[str]:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if not clean:
        return []
    parts = [part.strip() for part in SENTENCE_RE.split(clean) if part.strip()]
    return parts or [clean]


def _role(text: str, segment: dict[str, Any]) -> str:
    value = text.lower()
    if segment.get("movePhase"):
        return f"move_{segment['movePhase']}"
    if any(token in value for token in ("must", "cannot", "legal", "rule", "only", "must remain", "不能", "规则")):
        return "rule_explanation"
    if any(token in value for token in ("because", "so ", "therefore", "this changes", "as a result", "因此")):
        return "causal_effect"
    if any(token in value for token in ("next", "later", "first", "then", "接下来", "之后")):
        return "learning_bridge"
    return "concept_explanation"


def _intent_for(text: str, segment: dict[str, Any]) -> dict[str, Any]:
    lowered = text.lower()
    for markers, treatment, visual_kind, primitives, evidence in KNOWN_TREATMENTS:
        if any(marker in lowered for marker in markers):
            return {
                "concept": treatment,
                "semanticRole": _role(text, segment),
                "visualTreatment": treatment,
                "evidenceMode": evidence,
                "coverage": "covered",
                "confidence": "verified" if evidence in {"claim_proof", "board_state"} else "inferred",
                "visualKind": visual_kind,
                "primitives": primitives,
            }
    # Flexible path for new concepts: preserve the idea, use a safe generic
    # renderer treatment, and let the AI visual director refine it if possible.
    return {
        "concept": re.sub(r"[^A-Za-z0-9 _-]", "", text).strip()[:80] or "new concept",
        "semanticRole": _role(text, segment),
        "visualTreatment": "concept_focus",
        "evidenceMode": "editorial_bridge" if _role(text, segment) == "learning_bridge" else "board_state",
        "coverage": "covered",
        "confidence": "inferred",
        "visualKind": "board_overview",
        "primitives": ["concept_focus"],
    }


def expand_narration_segments(job: dict[str, Any]) -> dict[str, Any]:
    """Split meaningful narration into sentence segments before visual planning.

    The operation is idempotent: already expanded jobs are returned unchanged.
    Timings are proportional estimates and are replaced by TTS alignment later.
    """
    if job.get("sentenceVisualSupervision"):
        return job
    source = job.get("narrationSegments") if isinstance(job.get("narrationSegments"), list) else []
    if not source:
        source = [{"kind": "intro", "text": str(job.get("narration") or ""), "captionPosition": "bottom"}]
    expanded: list[dict[str, Any]] = []
    intents: list[dict[str, Any]] = []
    global_cursor = 0.0
    for segment_index, original in enumerate(source, start=1):
        if not isinstance(original, dict):
            continue
        sentences = split_sentences(str(original.get("text") or original.get("captionText") or ""))
        if not sentences:
            continue
        raw_start = float(original.get("startSec") or 0.0)
        raw_end = float(original.get("endSec") or 0.0)
        if raw_end <= raw_start:
            raw_start = max(global_cursor, raw_start)
        weights = [max(1, len(sentence.split())) for sentence in sentences]
        total = float(sum(weights)) or 1.0
        cursor = raw_start
        for sentence_index, (sentence, weight) in enumerate(zip(sentences, weights), start=1):
            if raw_end > raw_start:
                end = raw_end if sentence_index == len(sentences) else cursor + (raw_end - raw_start) * weight / total
            else:
                end = cursor + max(0.35, weight * 0.16)
            intent = _intent_for(sentence, original)
            sentence_id = f"seg-{segment_index:03d}-sent-{sentence_index:02d}"
            child = deepcopy(original)
            child.update({
                "text": sentence,
                "captionText": sentence,
                "startSec": round(cursor, 3),
                "endSec": round(max(cursor + 0.08, end), 3),
                "sentenceId": sentence_id,
                "visualIntent": {key: value for key, value in intent.items() if key not in {"visualKind", "primitives"}},
            })
            # Keep move beat identity while allowing the visual director to
            # assign a distinct treatment to each sentence.
            expanded.append(child)
            intents.append({
                "sentenceId": sentence_id,
                "segmentIndex": segment_index,
                "sentenceIndex": sentence_index,
                "text": sentence,
                **intent,
                "startSec": child["startSec"],
                "endSec": child["endSec"],
            })
            cursor = end
        global_cursor = max(global_cursor, cursor)
    job["narrationSegments"] = expanded
    job["sentenceVisualIntents"] = intents
    job["sentenceVisualSupervision"] = {
        "version": "sentence_visual_supervision_v1",
        "status": "planned",
        "sourceSegmentCount": len(source),
        "sentenceCount": len(expanded),
        "unresolvedCount": sum(1 for item in intents if item.get("confidence") == "unresolved"),
    }
    return job


def validate_sentence_visual_coverage(job: dict[str, Any]) -> list[str]:
    intents = job.get("sentenceVisualIntents")
    segments = job.get("narrationSegments")
    if not isinstance(intents, list) or not intents:
        return ["sentence visual intents are missing"]
    if not isinstance(segments, list) or len(intents) != len(segments):
        return [f"sentence intent count does not match narration segments: {len(intents)} != {len(segments or [])}"]
    errors: list[str] = []
    for index, intent in enumerate(intents, start=1):
        if not isinstance(intent, dict):
            errors.append(f"sentence_intent_{index} is not an object")
            continue
        if not str(intent.get("sentenceId") or "").strip():
            errors.append(f"sentence_intent_{index} has no sentenceId")
        if not str(intent.get("visualTreatment") or "").strip():
            errors.append(f"sentence_intent_{index} has no visualTreatment")
        if intent.get("confidence") == "unresolved":
            errors.append(f"sentence_intent_{index} is unresolved")
        if str(intent.get("coverage") or "") not in {"covered", "bridge_only"}:
            errors.append(f"sentence_intent_{index} has invalid coverage")
    return errors
