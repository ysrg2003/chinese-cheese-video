# Audio/Captions and YouTube Catalog Completion Report

## Executive result

The audio/caption mismatch was traced to two independent causes. The live GitHub Actions workflow explicitly set `USE_WORD_CAPTIONS: "0"`, and the director data model allowed captions to be authored as paraphrased summaries that were independent from `narration`. The video renderer displayed `job.captions`, while Edge-TTS spoke `job.narration`, so the two could disagree.

The production path is now corrected. Edge-TTS `WordBoundary` events are grouped into readable display captions without changing their text. The audio, the generated `voice_words.json`, the generated `voice.vtt`, and the Remotion `job.captions` now originate from the same spoken units. English joins units with spaces; Chinese joins units without inserted spaces. The live workflow is set to `USE_WORD_CAPTIONS: "1"`, and the runtime always uses the word-boundary caption builder whenever Edge-TTS returns cues.

## Database result

The SQLite catalog remains `data/chinese_cheese_video.db` and is still the durable GitHub Actions state. It now includes the existing operational tables plus a normalized YouTube catalog:

| Table | Stored information |
| --- | --- |
| `youtube_channels` | Channel ID, handle, title, public URL, and configuration state. |
| `youtube_playlists` | All 22 configured English/Chinese playlist definitions, content type, title, description, privacy, resolved YouTube playlist ID, URL, state, and errors. |
| `youtube_videos` | Stable job ID, candidate, language, content type, title, source, duration, YouTube video ID/URL, privacy, playlist key, local media paths, caption source, narration SHA-256, captions SHA-256, status, timestamps, and errors. |
| `youtube_video_playlists` | Video-to-playlist association, YouTube playlist ID, playlist item ID, state, and errors. |
| `youtube_publications` | Existing upload/retry state that preserves a video ID after partial upload and prevents duplicate uploads. |

The initializer seeds the channel and all 22 playlist definitions idempotently. Existing publication records are backfilled into the normalized catalog automatically. Every render/publication updates the catalog, and `youtube-catalog.json` is exported and uploaded as a GitHub Actions artifact after each run.

## Tests

The local regression suite passed 9 tests. It covers English and Chinese word-boundary captions, preservation of spoken units, rejection of invented Chinese summary text, metadata-to-playlist mapping, SQLite publication idempotency, normalized catalog records, upload/playlist association, retry reuse of an existing video ID, and stale/deleted playlist recovery. Python compilation and workflow validation also passed.

## Live validation

GitHub Actions run `31655711769` completed successfully from commit `1b6e092`. The run reported `selected: 1`, `completed: 1`, and `failed: 0`. It executed the autonomous production step with `USE_WORD_CAPTIONS=1`, published both language variants publicly, exported the normalized catalog, uploaded artifacts, and committed the SQLite state.

| Language | Public video | Playlist | Duration observed |
| --- | --- | --- | --- |
| English | [M7mQrRxIg-M](https://www.youtube.com/watch?v=M7mQrRxIg-M) | [EN — Trending Xiangqi](https://www.youtube.com/playlist?list=PLeAPpNpQbt4w) | 0:18 |
| Chinese | [na82AsZBxKU](https://www.youtube.com/watch?v=na82AsZBxKU) | [中文 — 象棋热点](https://www.youtube.com/playlist?list=PLVqPL589s1NI) | 0:17 |

Both public watch pages loaded successfully. The exported catalog reported `captions_source=edge_tts_word_boundaries`, `status=published`, the corresponding video IDs, and the corresponding playlist IDs for both new records. The new associations also include playlist item IDs.

## Repository changes

The implementation was pushed to `ysrg2003/chinese-cheese-video` on `master`. The main changes are in `python/tts.py`, `python/run_pipeline.py`, `python/local_store.py`, `.github/workflows/render-video.yml`, `python/export_youtube_catalog.py`, `python/test_tts_captions.py`, and `docs/youtube_catalog.md`.

## Operational note

The two newly validated Chinese/English videos use the source trend title supplied by the RSS candidate. Their narration and captions follow the correct language-specific voice and transcript path; title localization is a separate editorial enhancement and does not affect audio/caption synchronization or database integrity.
