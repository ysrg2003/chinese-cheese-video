# Caption and Thumbnail Delivery Policy

**Effective policy for Xiangqi Lab**

The channel is English-primary. English narration is already audible, while the Remotion scene provides concise synchronized teaching cues: scene headlines, MoveCards, board highlights, fast legal move animation, and spoken-sentence cues. These in-video teaching cues remain enabled because they tell the viewer what to watch. The separate English caption track on YouTube is disabled by default because it duplicates the same narration.

Chinese localization remains active. The pipeline translates the English narration into Simplified Chinese, generates the male Chinese voice `Schedar` through AI Provider Router Gemini-TTS, creates Chinese SRT/VTT captions from the same translated narration units, and uploads the `zh-Hans` caption track through the YouTube Data API. The Chinese audio file is retained as a durable artifact for YouTube Studio alternate-audio attachment when the channel is eligible for that feature.

The setting is centralized in `config/youtube_metadata_policy.json`:

| Setting | Default | Meaning |
|---|---:|---|
| `delivery.english_in_video_captions` | `true` | Keep concise English teaching cues inside the MP4. |
| `delivery.english_youtube_caption_track` | `false` | Do not upload a redundant English YouTube caption track. |
| `delivery.thumbnail_languages` | `["en"]` | Generate and validate only the English thumbnail. |

A deliberate visual simplification can disable the English teaching-cue layer by setting `YOUTUBE_ENGLISH_CAPTIONS_IN_VIDEO=0`. This override is intentionally explicit; the normal GitHub Actions workflow does not set it. It does not control the separate YouTube caption-track policy.

## Thumbnail automation

The pipeline renders a clean board frame, builds `thumbnail_en.jpg` at 1280×720, validates JPEG format, dimensions, readability, and the 2 MB limit, then calls the YouTube `thumbnails.set` endpoint automatically after the video upload and playlist association. The publisher explicitly requests both `https://www.googleapis.com/auth/youtube.upload` and `https://www.googleapis.com/auth/youtube.force-ssl` in `python/youtube_publisher.py`; the latter is covered by a unit test and a production preflight grep gate. YouTube's official API documentation defines `thumbnails.set` as the method that uploads and sets a custom video thumbnail, with a 2 MB maximum file size.[1]

No Chinese thumbnail is generated, validated, stored, or uploaded. The English thumbnail is the sole thumbnail policy for this channel. This avoids an unnecessary Studio-only localization step and keeps every future production run fully unattended.

## Shorts cover strategy

The channel publishes vertical videos that YouTube classifies as Shorts. The uploaded 16:9 `thumbnail_en.jpg` remains useful for watch-page, search, desktop, and other non-Short surfaces, but YouTube Help documents that Shorts thumbnails are selected from a frame through the YouTube app rather than edited in Studio.[4] A temporary vertical opening-cover experiment was tested in production and retired because the Shorts surface selected frames non-deterministically. New MP4 files no longer contain a dedicated `VerticalShortCover` state; the system does not claim control over a Shorts grid cover that the Data API cannot deterministically set.

## Audio provider policy

Production narration uses `TTS_PROVIDER=ai_router` and the male `Schedar` Gemini-TTS voice for both English and Simplified Chinese. The router returns audio data, normally linear PCM at 24 kHz; `python/tts.py` converts it to MP3 with `loudnorm` plus `dynaudnorm` so quiet later speech does not become unintelligible, then measures the real duration with FFprobe. Word-boundary cues are not claimed when the provider does not return them, so segment captions are aligned proportionally to the measured audio duration. Edge TTS remains available only as the final last-resort fallback after the complete AI Router chain fails.

## Narration-to-visual direction

The production director now treats every narration segment as a visual contract rather than a title request. It reads the segment text, assigns semantic tags, chooses a renderer-supported visual plan, and validates that the scene has actionable primitives. Board geometry remains deterministic: files, ranks, intersections, river band, palace X diagonals, central files, legal destinations, piece paths, cannon screens, and horse-leg constraints are drawn from the actual board state. The external reference-edit service is reserved for non-geometric concepts such as a localized historical or cultural inset. It receives the exact Remotion reference image and a bounded transparent mask, and is not permitted to redraw the board, pieces, moves, or coordinates.

## Why the automation is split this way

YouTube's official Data API exposes `captions.insert` for uploading caption tracks and `videos.update` for localized title and description data.[2] [3] It also exposes `thumbnails.set` for the default custom thumbnail.[1] The current API reference does not provide a normal `videos` or `audioTracks` endpoint for attaching an alternate spoken-audio file to an existing video, so Chinese audio remains generated and durable but is marked `generated_studio_upload_required` rather than being falsely reported as attached. The same distinction is used for any future platform-only feature.

## Acceptance contract

Before `upload_video()` is called, the workflow must have valid English teaching cues in the job/render contract, a valid Chinese audio file, Chinese SRT/VTT files, valid Chinese metadata, and one valid English thumbnail. If any required artifact fails, upload is blocked. After upload, the workflow uploads the Chinese caption track but not the redundant English YouTube caption track, updates English and Chinese localized metadata, sets the English thumbnail automatically, associates the public video with its playlist, and persists all statuses in SQLite. For piece lessons and move explanations, legal destination dots are computed from the actual board position and filtered through Xiangqi legality before they are drawn.

## References

[1]: https://developers.google.com/youtube/v3/docs/thumbnails/set "YouTube Data API — Thumbnails: set"
[2]: https://developers.google.com/youtube/v3/docs/captions/insert "YouTube Data API — Captions: insert"
[3]: https://developers.google.com/youtube/v3/docs/videos/update "YouTube Data API — Videos: update"
[4]: https://support.google.com/youtube/answer/10343433?hl=en-GB "YouTube Help — Create YouTube Shorts"

## Verification of the change

Commit `620ad32` passed local Python tests (61 tests), Python compilation, and TypeScript checking. The later legal-destination implementation, Shorts-cover retirement, and semantic visual contract are tracked on the current `master`; the final GitHub quality-gate run will be recorded after this revision.

The live production proof for video `NYhJlCD49hw` recorded a successful `youtube#thumbnailSetResponse`, including the returned `maxresdefault.jpg` URL. Therefore the scope was not merely documented: it was effective during the actual upload.
 Its artifact contains `thumbnail_en.jpg` and no `thumbnail_zh.jpg`; `thumbnail-smoke.json` reports `width=1280`, `height=720`, `default_language=en`, and `localized_thumbnail_status=disabled_by_policy`. The smoke explicitly performs no production upload or YouTube mutation.

## Legacy video cleanup proof

The one-time cleanup workflow [31773822614](https://github.com/ysrg2003/chinese-cheese-video/actions/runs/31773822614) found the legacy manual track `English transcript` on video `D-o77HngwOU` and deleted only that track ID. The follow-up idempotent run [31773940298](https://github.com/ysrg2003/chinese-cheese-video/actions/runs/31773940298) returned `matched=[]` in the initial dry-run, completed with no deletion, and passed the post-delete `assert-absent` verification. Automatic ASR captions and the Chinese caption track were not selected or deleted.
