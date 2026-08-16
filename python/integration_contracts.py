from __future__ import annotations

from typing import Any

from xiangqi_rules import validate_move_sequence


class IntegrationContractError(ValueError):
    """A cross-layer payload is inconsistent or unsafe to continue."""


def validate_job_contract(
    job: dict[str, Any],
    *,
    stage: str,
    puzzle: dict[str, Any] | None = None,
    require_audio: bool = False,
) -> list[str]:
    """Validate the shared job contract at every pipeline boundary.

    This deliberately checks identity and semantic invariants together. A file can
    be individually valid while still belonging to a different lesson, language,
    board position, or publication job; those mismatches are the failures this
    contract prevents.
    """
    errors: list[str] = []
    required = ("id", "title", "language", "fen", "moves", "narration", "content_type")
    for field in required:
        if field not in job or job[field] in (None, ""):
            errors.append(f"missing required field: {field}")
    language = str(job.get("language") or "")
    if language not in {"en", "zh"}:
        errors.append(f"unsupported language: {language}")
    if language == "en" and any("\u0600" <= char <= "\u06ff" for char in str(job.get("narration") or "")):
        errors.append("English narration contains Arabic characters")
    if puzzle:
        for field in ("language", "fen", "curriculum_lesson_key", "content_type"):
            expected = puzzle.get(field)
            if expected not in (None, "") and str(job.get(field) or "") != str(expected):
                errors.append(f"identity mismatch for {field}: job={job.get(field)!r}, puzzle={expected!r}")
    move_result = validate_move_sequence(str(job.get("fen") or ""), job.get("moves") or [])
    if not move_result.get("ok"):
        errors.extend(f"illegal move trace: {item}" for item in move_result.get("errors") or [])
    proof = job.get("claimProof")
    if not isinstance(proof, dict) or proof.get("ok") is not True:
        errors.append("claimProof is not verified")
    if stage in {"storyboard", "tts", "render", "publish"}:
        if not isinstance(job.get("narrationSegments"), list) or not job.get("narrationSegments"):
            errors.append("narrationSegments missing at visual/audio boundary")
    if stage in {"tts", "render", "publish"} and require_audio:
        if not str(job.get("audioSrc") or "").strip():
            errors.append("audioSrc missing after TTS")
    if stage in {"storyboard", "render", "publish"}:
        if not isinstance(job.get("scenes"), list) or not job.get("scenes"):
            errors.append("scenes missing at render boundary")
    return errors


def validate_publication_contract(job: dict[str, Any], publication: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    status = str(publication.get("status") or "")
    allowed = {"published", "uploaded_playlist_pending", "published_localization_pending", "published_thumbnail_pending", "failed", "rendered"}
    if status not in allowed:
        errors.append(f"unknown publication status: {status}")
    if status == "published" and not str(publication.get("video_id") or "").strip():
        errors.append("published result has no video_id")
    if publication.get("video_id") and publication.get("video_url") and str(publication["video_id"]) not in str(publication["video_url"]):
        errors.append("video_id does not match video_url")
    metadata = publication.get("metadata") or {}
    if metadata.get("job_id") and str(metadata["job_id"]) != str(job.get("id")):
        errors.append("publication metadata job_id does not match job id")
    for field in ("language", "curriculum_lesson_key", "playlist_key"):
        expected = job.get(field)
        actual = metadata.get(field)
        if expected not in (None, "") and actual not in (None, "") and str(expected) != str(actual):
            errors.append(f"publication metadata mismatch for {field}")
    return errors


def assert_job_contract(job: dict[str, Any], **kwargs: Any) -> None:
    errors = validate_job_contract(job, **kwargs)
    if errors:
        raise IntegrationContractError("Integration contract failed: " + "; ".join(errors))


def assert_publication_contract(job: dict[str, Any], publication: dict[str, Any]) -> None:
    errors = validate_publication_contract(job, publication)
    if errors:
        raise IntegrationContractError("Publication contract failed: " + "; ".join(errors))
