# Public YouTube Thumbnail Audit — 2026-08-15

## Audited videos

| Lesson | Video ID | Public endpoint inspected | Result |
|---|---|---|---|
| en-001 — What Is Xiangqi? | `GCgUvitq9lA` | `maxresdefault.jpg` | A custom-looking generated collage is publicly served |
| en-003 — A Short History of Xiangqi | `_cw1jqzX6Pc` | `maxresdefault.jpg` | A custom-looking generated history/board collage is publicly served |
| en-005 — The 9×10 Point Board | `qxbAHPFXeyE` | `maxresdefault.jpg` | The custom thumbnail is publicly served |
| en-006 — The River and the Two Palaces | `OGbYcaIJ00E` | `maxresdefault.jpg` | A public image is served; requires separate source comparison |

## en-005 source comparison

The exact custom source thumbnail recovered from the publication commit is 1280×720 JPEG. YouTube’s public en-005 `maxresdefault.jpg` is also 1280×720 JPEG. A deterministic pixel comparison found a mean absolute RGB difference of only **0.61 intensity levels**, which is consistent with YouTube recompression and strongly indicates that the custom thumbnail was uploaded and is the image currently served publicly. The public image visibly contains `XIANGQI LAB`, `THE 9×10 POINT BOARD`, `CHINESE CHESS`, and the Xiangqi board preview.

## Studio screenshot interpretation

The supplied Studio screenshot shows a gray placeholder in the thumbnail panel. That panel appears not to have loaded or refreshed the thumbnail in the current Studio page view. It conflicts with the public image endpoint, which is serving the custom en-005 thumbnail. The screenshot therefore does not prove that the thumbnail is absent from YouTube’s public video record; the public CDN image is stronger evidence of the actual serving state.

The public endpoint should still be verified through YouTube Studio after a hard refresh or by reopening the video details page. If Studio continues to show the placeholder while the public CDN continues to serve the custom image, the issue is a Studio UI/cache/display problem rather than an upload failure.

## Older videos

The public en-001 and en-003 endpoints also serve non-placeholder generated images, although their designs are visually different from the en-005 thumbnail. This indicates that the channel is not globally missing thumbnails. The remaining audit question is whether en-006’s image matches its intended uploaded thumbnail and whether YouTube Studio is displaying cached placeholders for some videos.

## en-006 source comparison

The exact en-006 thumbnail source from the GitHub artifact is 1280×720 JPEG. YouTube’s public en-006 `maxresdefault.jpg` is also 1280×720 JPEG, but the mean absolute RGB difference is **87.615**, unlike en-005’s 0.61. The public en-006 image therefore does not match the intended generated thumbnail source and likely fell back to a video-frame/default thumbnail or was replaced by a different image. This is a real publication inconsistency and requires a thumbnail re-upload plus post-upload verification for en-006.
