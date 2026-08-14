# Production run 31759446451 findings

The controlled production run used commit `afa1ce6`, selected `en-010-the-general`, completed one English job, and the workflow ended successfully with `completed=1` and `failed=0`. The English video remained public at `https://www.youtube.com/watch?v=QEdAG1azW2U` and was associated with playlist `PLQRZVvYZCWYc`.

The new Xiangqi legal-move gate did not block the job, so the regenerated line passed deterministic validation. The post-publish localization hook did run but recorded `localization.status=failed_pending_retry` with the error `expected str, bytes or os.PathLike object, not NoneType`. No Chinese captions, localized metadata, Chinese audio attachment, or thumbnail completion should be claimed until this error is fixed and a retry confirms the artifacts.

The workflow's overall success is therefore only an English-publication success, not a complete multilingual-publication success. The production catalog preserved the localization error in metadata for retry.
