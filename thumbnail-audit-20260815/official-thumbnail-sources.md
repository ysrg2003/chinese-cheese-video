# Official Thumbnail Sources and Findings

## YouTube Help — Add custom thumbnails on YouTube

URL: https://support.google.com/youtube/answer/72431?hl=en&co=GENIE.Platform%3DDesktop

Retrieved 2026-08-15. The official help page states that custom thumbnails are available for videos and Shorts when the account is verified. For Shorts, it specifically instructs creators to use YouTube Studio on a computer, open Content > Shorts, choose the Short, click Upload file under Thumbnail, and click Save. It recommends a 9:16 aspect ratio for uploaded Shorts thumbnails and warns that thumbnail changes may take time to appear.

## YouTube official blog — Making thumbnails easier on YouTube

URL: https://blog.youtube/news-and-events/youtube-studio-custom-thumbnail-updates/

Published 2026-07-24. YouTube announced that fully custom Shorts thumbnails are being introduced for YouTube Partner Program creators and expanded to more creators over time. It also states that Shorts thumbnails can be selected from suggested frames on desktop or from any frame through the YouTube mobile app.

## YouTube Data API — Thumbnails: set

URL: https://developers.google.com/youtube/v3/docs/thumbnails/set

Retrieved 2026-08-15. The endpoint accepts JPEG or PNG images up to 2 MB and requires an authorized YouTube scope such as `youtube.force-ssl`. A successful response returns a thumbnail resource. The documentation describes the endpoint generically as setting a custom video thumbnail and does not guarantee that a vertical Short will display or retain the image in Studio.

## Public YouTube Issue Tracker — Shorts API thumbnail behavior

URL: https://issuetracker.google.com/issues/381127084

The public issue documents reports that the API can return HTTP 200 and a thumbnail resource for Shorts while Creator Studio does not apply the thumbnail. A Google response in the issue says custom thumbnails for Shorts were not fully supported, and the issue is marked Won't Fix/Infeasible. Later user reports in 2026 continue to describe the API thumbnail being overwritten or falling back to a random still.

## Project-specific public CDN audit

The project’s published videos are vertical Shorts. Direct public CDN images were fetched without mutation:

- en-001 `GCgUvitq9lA`: `https://i.ytimg.com/vi/GCgUvitq9lA/maxresdefault.jpg`
- en-003 `_cw1jqzX6Pc`: `https://i.ytimg.com/vi/_cw1jqzX6Pc/maxresdefault.jpg`
- en-005 `qxbAHPFXeyE`: `https://i.ytimg.com/vi/qxbAHPFXeyE/maxresdefault.jpg`
- en-006 `OGbYcaIJ00E`: `https://i.ytimg.com/vi/OGbYcaIJ00E/maxresdefault.jpg`

The public en-005 CDN image visually contains the custom `THE 9×10 POINT BOARD` thumbnail and is 1280×720. It closely matches the old system-generated source file with mean absolute RGB difference 0.61, but the user has clarified that they manually uploaded the thumbnails, so the old source comparison is not proof of ownership or intended image identity. The screenshot of Studio must be treated as the authoritative report of the user’s current Studio view; no thumbnail should be overwritten.

The correct system behavior is therefore preservation plus verification: do not call the API thumbnail setter for vertical Shorts as if it were authoritative, record `manual_studio_required`, and never claim thumbnail completion for a Short based only on an API response. User-uploaded Studio thumbnails must remain untouched.
