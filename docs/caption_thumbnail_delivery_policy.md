# Caption and Thumbnail Delivery Policy

**Effective policy for Xiangqi Lab**

The channel is English-primary. English narration is already audible, while the Remotion scene provides synchronized headlines, move cards, board highlights, and fast legal move animation. Showing a second English text layer inside the video repeats the same message and can cover the move labels. Therefore, English burned-in captions are disabled by default, and the English caption track is not uploaded by default.

Chinese localization remains active. The pipeline translates the English narration into Simplified Chinese, generates the male Chinese voice `zh-CN-YunjianNeural`, creates Chinese SRT/VTT captions from the same translated narration units, and uploads the `zh-Hans` caption track through the YouTube Data API. The Chinese audio file is retained as a durable artifact for YouTube Studio alternate-audio attachment when the channel is eligible for that feature.

The setting is centralized in `config/youtube_metadata_policy.json`:

| Setting | Default | Meaning |
|---|---:|---|
| `delivery.english_in_video_captions` | `false` | Do not render English captions inside the MP4. |
| `delivery.english_youtube_caption_track` | `false` | Do not upload a redundant English YouTube caption track. |
| `delivery.thumbnail_languages` | `["en"]` | Generate and validate only the English thumbnail. |

A deliberate test or accessibility deployment can opt into English captions by setting `YOUTUBE_ENGLISH_CAPTIONS_IN_VIDEO=1`. This override is intentionally explicit; the normal GitHub Actions workflow does not set it.

## Thumbnail automation

The pipeline renders a clean board frame, builds `thumbnail_en.jpg` at 1280×720, validates JPEG format, dimensions, readability, and the 2 MB limit, then calls the YouTube `thumbnails.set` endpoint automatically after the video upload and playlist association. YouTube's official API documentation defines `thumbnails.set` as the method that uploads and sets a custom video thumbnail, with a 2 MB maximum file size.[1]

No Chinese thumbnail is generated, validated, stored, or uploaded. The English thumbnail is the sole thumbnail policy for this channel. This avoids an unnecessary Studio-only localization step and keeps every future production run fully unattended.

## Why the automation is split this way

YouTube's official Data API exposes `captions.insert` for uploading caption tracks and `videos.update` for localized title and description data.[2] [3] It also exposes `thumbnails.set` for the default custom thumbnail.[1] The current API reference does not provide a normal `videos` or `audioTracks` endpoint for attaching an alternate spoken-audio file to an existing video, so Chinese audio remains generated and durable but is marked `generated_studio_upload_required` rather than being falsely reported as attached. The same distinction is used for any future platform-only feature.

## Acceptance contract

Before `upload_video()` is called, the workflow must have a valid Chinese audio file, Chinese SRT/VTT files, valid Chinese metadata, and one valid English thumbnail. If any required artifact fails, upload is blocked. After upload, the workflow uploads the Chinese caption track, updates English and Chinese localized metadata, sets the English thumbnail automatically, associates the public video with its playlist, and persists all statuses in SQLite.

## References

[1]: https://developers.google.com/youtube/v3/docs/thumbnails/set "YouTube Data API — Thumbnails: set"
[2]: https://developers.google.com/youtube/v3/docs/captions/insert "YouTube Data API — Captions: insert"
[3]: https://developers.google.com/youtube/v3/docs/videos/update "YouTube Data API — Videos: update"

## Verification of the change

Commit `620ad32` passed local Python tests (61 tests), Python compilation, and TypeScript checking. GitHub Actions quality-gate run [31773582539](https://github.com/ysrg2003/chinese-cheese-video/actions/runs/31773582539) also completed successfully. Its artifact contains `thumbnail_en.jpg` and no `thumbnail_zh.jpg`; `thumbnail-smoke.json` reports `width=1280`, `height=720`, `default_language=en`, and `localized_thumbnail_status=disabled_by_policy`. The smoke explicitly performs no production upload or YouTube mutation.
