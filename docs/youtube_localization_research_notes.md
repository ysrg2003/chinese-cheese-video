
## YouTube localization research

Official YouTube Data API documentation confirms that `captions.insert` uploads a caption track for a video using `snippet.videoId`, `snippet.language`, and `snippet.name`, with OAuth scope `youtube.force-ssl`; the method supports media upload and has a 400-unit quota cost. Source: https://developers.google.com/youtube/v3/docs/captions/insert.

Official `videos.update` documentation confirms that localized title and description can be written through the `localizations.(key)` properties, provided the video's default language is set. Source: https://developers.google.com/youtube/v3/docs/videos/update.

Official YouTube Help says multi-language audio allows a creator to upload a self-produced dubbed audio file to an existing long-form video through YouTube Studio's Languages area, but the feature is available only to a subset of creators as access expands. The Help article also says localized thumbnails are managed through YouTube Studio's Languages flow. Source: https://support.google.com/youtube/answer/13338784.

The reviewed official Data API reference lists captions and thumbnail set operations but does not document an endpoint for uploading alternate audio tracks. Therefore the autonomous pipeline should generate the Chinese MP3 and preserve it as an artifact, upload the Chinese caption track and localized metadata through the Data API, and attempt alternate-audio upload only through a separately verified Studio automation path when the channel is eligible. It must never claim that a Data API call successfully attached a secondary audio track unless the operation is explicitly confirmed.

The official help page states that multi-language audio is not automatic dubbing: the creator must supply the dubbed audio file, and it should be approximately the same length as the video. Source: https://support.google.com/youtube/answer/13338784.

## Thumbnail research

Official YouTube Help confirms that custom thumbnails may be uploaded for verified accounts and can be changed from YouTube Studio. Source: https://support.google.com/youtube/answer/72431.

Official YouTube Data API `thumbnails.set` supports uploading a custom thumbnail for a video with OAuth; accepted MIME types include JPEG and PNG, and the maximum file size is 2MB. Source: https://developers.google.com/youtube/v3/docs/thumbnails/set.

Official YouTube A/B testing guidance says eligible creators can test up to three title/thumbnail variants in YouTube Studio, and recommends high-resolution thumbnails; thumbnails below 1280×720 are downscaled in experiments. The feature is desktop-only and does not currently cover Shorts. Source: https://support.google.com/youtube/answer/13861714.

The pipeline's default thumbnail design will therefore use a 16:9 1280×720 JPEG under 2MB, with one clear Xiangqi focal position, high contrast, a short English-primary headline, consistent Xiangqi Lab branding, and no claim that an A/B test was run unless Studio confirms it.
