# Thumbnail Delivery Policy

## Purpose

The channel publishes portrait educational videos. A portrait render is treated as a YouTube Short for thumbnail delivery. The system must preserve creator-selected thumbnails and must never claim that a thumbnail is visible merely because the YouTube Data API returned a successful `thumbnails.set` response.

## Policy by video shape

| Render shape | Thumbnail action | Completion state |
|---|---|---|
| Landscape or square | Generate the controlled English thumbnail, validate JPEG format, 1280×720 dimensions, and 2 MB limit, then upload through the YouTube Data API. Record the API response as `api_response_confirmed`. | The system may report the API upload step as complete, while retaining the public URL for later audit. |
| Portrait / Short | Do not call the YouTube Data API thumbnail setter. Do not generate a replacement thumbnail for publication. The creator selects or uploads the thumbnail in YouTube Studio on a computer. | Record `manual_studio_required`; never convert this to `completed` automatically. |

## Why Shorts are different

YouTube’s official help page says that custom Shorts thumbnails are added in YouTube Studio on a computer and recommends a 9:16 uploaded image. YouTube’s official blog also describes Shorts thumbnail upload as a Studio feature being expanded to eligible creators. The generic Data API documentation describes `thumbnails.set`, but it does not guarantee that a portrait Short will retain the image in Studio. YouTube’s public issue tracker documents cases where the API returned success for Shorts while Studio did not apply or retain the custom thumbnail.

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

This state is not an error. It is an explicit platform boundary. The video can be uploaded and localized automatically, while the thumbnail remains creator-managed. Existing thumbnails manually uploaded by the channel owner must not be replaced by a generated asset or by an API retry.
