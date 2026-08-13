# Chinese Cheese Video — Audio Captions and YouTube Catalog

## Caption contract

Every rendered video now uses the text emitted by Edge-TTS `WordBoundary` events as its on-screen caption source. The pipeline groups adjacent word-boundary units only for readability; it does not paraphrase, summarize, translate, or invent a second caption script. English units are joined with spaces, while Chinese units are joined without inserted spaces. The generated audio, `voice_words.json`, `voice.vtt`, and `job.captions` therefore share the same spoken source and timing.

The two configured male voices remain unchanged: `en-US-GuyNeural` for English and `zh-CN-YunjianNeural` for Simplified Chinese. Arabic is rejected by the director sanitization rules and is not introduced by the caption builder.

## SQLite catalog

The local database at `data/chinese_cheese_video.db` remains the durable source of truth used by GitHub Actions. In addition to the existing discovery, jobs, AI telemetry, and `youtube_publications` retry table, the following normalized YouTube tables are maintained:

| Table | Purpose |
| --- | --- |
| `youtube_channels` | Stores the configured channel ID, handle, title, public URL, and configuration status. |
| `youtube_playlists` | Stores every configured English and Chinese playlist key, language, content type, title, description, privacy status, resolved YouTube playlist ID, URL, and state. All 22 configured playlists are seeded idempotently. |
| `youtube_videos` | Stores each stable job ID, candidate and language, content type, source, title, duration, YouTube video ID and URL, privacy status, selected playlist key, local media paths, caption source, narration hash, caption hash, publication state, timestamps, and errors. |
| `youtube_video_playlists` | Stores the many-to-many association between a job/video and a playlist, including the YouTube playlist ID, playlist-item ID when available, state, and error. |
| `youtube_publications` | Retains the operational upload/retry state, including the rule that a successful upload is reused when playlist association needs another attempt. |

The catalog is populated in two ways. First, the schema initializer seeds the channel and all playlist definitions from `config/youtube_playlists.json`. Second, every render or publication calls `upsert_youtube_catalog`, which updates the normalized video and association records. Existing publication rows are backfilled automatically, so adding the catalog does not re-upload old videos.

## States and duplicate prevention

A video keeps the stable job ID derived from candidate ID and language. The SHA-256 fingerprint of the narration and the SHA-256 fingerprint of the final captions are stored in `youtube_videos`, allowing later audits to distinguish a changed script from a retry. The publication table continues to preserve `video_id` after a partial failure. A retry therefore attempts playlist association with the existing YouTube video instead of creating another upload.

The normalized catalog is exported after every GitHub Actions run to `youtube-catalog.json` and uploaded with the SQLite snapshot and generated artifacts. The export contains channel, playlist, video, and association records without OAuth tokens or API secrets.

## Verification expectations

A healthy published record has `youtube_videos.status = 'published'`, a non-empty `video_id`, a non-empty `playlist_key`, a matching row in `youtube_video_playlists` with `status = 'published'`, and a playlist row with the resolved `youtube_playlist_id`. A failed playlist operation must retain the video ID and be retried with the same job ID.
