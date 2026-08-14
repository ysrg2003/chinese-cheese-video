# YouTube Shorts thumbnail behavior research

## Finding

The channel screenshots show two different surfaces. The Data API custom-thumbnail upload succeeded for the video, but the Shorts channel grid and Studio preview display a vertical frame selected from the Short rather than the uploaded 16:9 image. This is expected platform behavior for Shorts, not evidence that `thumbnails.set` failed.

## Official YouTube Help

The official YouTube Help page [Create YouTube Shorts](https://support.google.com/youtube/answer/10343433?hl=en-GB) states under **Select a thumbnail** that a creator can choose a frame from the Short before or after uploading it, and that thumbnail editing is available from the YouTube app, not Studio. The documented flow is to open the final upload screen, tap Edit on the thumbnail, select a frame, and tap Done. After upload, the documented edit flow is through the channel page and the YouTube app.

## Official YouTube Data API

The official [Thumbnails: set](https://developers.google.com/youtube/v3/docs/thumbnails/set) reference states that `thumbnails.set` uploads a custom video thumbnail, accepts JPEG/PNG media up to 2 MB, and requires one of several OAuth scopes including `youtube.upload` or `youtube.force-ssl`. It does not promise that every Shorts surface will display that uploaded image as the vertical Shorts cover.

## Consequence for Xiangqi Lab

The existing 16:9 `thumbnail_en.jpg` upload should remain enabled for watch-page, search, desktop, and non-Short surfaces. For Shorts channel cards and app surfaces, the autonomous system must instead make an attractive English cover frame part of the vertical MP4 itself, ideally in the first 0.5–1.0 seconds, and keep that frame visually clean enough to be selected by the YouTube app when a manual selection is possible. A 16:9 upload alone cannot guarantee the desired image in the Shorts grid.

## References

1. [YouTube Help — Create YouTube Shorts](https://support.google.com/youtube/answer/10343433?hl=en-GB)
2. [YouTube Data API — Thumbnails: set](https://developers.google.com/youtube/v3/docs/thumbnails/set)
