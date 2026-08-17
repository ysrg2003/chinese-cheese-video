# Thumbnail Delivery Policy

## Purpose

The channel publishes educational videos and explicit Shorts. `lesson` and `game` jobs must render in landscape at 1920×1080; only an explicit `short` job may render in portrait at 1080×1920. The publisher also checks the actual remote dimensions during reconciliation/backfill. The system must preserve creator-selected thumbnails and must never claim that a thumbnail is visible merely because the YouTube Data API returned a successful `thumbnails.set` response.

## Policy by video shape

| Render shape | Thumbnail action | Completion state |
|---|---|---|
| Standard video (landscape) | Generate the controlled English thumbnail, validate JPEG format, 1280×720 dimensions, and 2 MB limit, call `thumbnails.set` with the exact YouTube `videoId`, then read the same video with `videos.list(part=snippet,id=...)`. The returned `snippet.thumbnails.maxres` URL and dimensions must match the upload response. | Record `api_readback_confirmed` only after both upload and read-back succeed. |
| Portrait / Short | Do not call the YouTube Data API thumbnail setter as an authoritative Shorts workflow. The creator selects or uploads a 9:16 thumbnail in YouTube Studio on a computer. Existing portrait uploads are detected from their real remote dimensions during backfill. | Record `manual_studio_required`; never convert this to `completed` automatically. |

## Why Shorts are different

YouTube’s official help page says that custom Shorts thumbnails are added in YouTube Studio on a computer and recommends a 9:16 uploaded image. The generic Data API documentation describes `thumbnails.set` for video IDs, but the system does not treat that generic response as authoritative for a portrait Short. For standard videos, the API response is followed by a low-quota `videos.list(part=snippet,id=...)` read-back so the selected `maxres` resource is independently verified.

References:

1. [YouTube Help — Add custom thumbnails on YouTube](https://support.google.com/youtube/answer/72431?hl=en&co=GENIE.Platform%3DDesktop)
2. [YouTube Blog — Making thumbnails easier on YouTube](https://blog.youtube/news-and-events/youtube-studio-custom-thumbnail-updates/)
3. [YouTube Data API — Thumbnails: set](https://developers.google.com/youtube/v3/docs/thumbnails/set)
4. [Google Issue Tracker — YouTube v3 API Thumbnail Set on Shorts Not Working](https://issuetracker.google.com/issues/381127084)

## Operational rule

For a portrait video, the publication record must contain the following information:

```json
{
  "thumbnail_policy": "manual_studio_required",
  "thumbnail_upload_status": "manual_studio_required",
  "thumbnail_source": "user_studio_upload"
}
```

This state is not an error. It is an explicit platform boundary. The video can be uploaded and localized automatically, while the thumbnail remains creator-managed. Existing thumbnails manually uploaded by the channel owner must not be replaced by a generated asset or by an API retry. A legacy portrait upload must first be classified from its remote dimensions; it must not be treated as a standard video merely because its curriculum label is `lesson`.
