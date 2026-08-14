# Multilingual YouTube publishing contract

## Default language and order

Every job remains **English-first**. The English script, English Edge-TTS voice (`en-US-GuyNeural`), English on-screen captions, English YouTube metadata, and English default thumbnail are created and published first. No Arabic text, audio, caption, or translation is permitted.

After the English video is uploaded and associated with its playlist, the post-publish localization phase runs automatically. It uses the same AI Router chain for an exact segment-preserving Simplified Chinese translation and uses `zh-CN-YunjianNeural` for the Chinese narration artifact.

## Automated YouTube operations

The pipeline creates English and Simplified Chinese SRT/VTT files from the actual narration timing, then uploads the English caption track (`en`) and Chinese caption track (`zh-Hans`) through the YouTube Data API. It updates the video's localized title and description under `localizations.zh-Hans` while retaining English as the default language.

The pipeline generates a 1280×720 JPEG thumbnail below 2MB, uploads the English-primary thumbnail through the YouTube Data API, and stores a Chinese thumbnail variant for localized-thumbnail upload.

## Audio-track boundary

YouTube's official Help documentation describes multi-language audio upload through YouTube Studio's Languages area and notes that availability is limited to eligible creators. The official Data API reference used by this project documents captions, localized metadata, and thumbnail upload, but not an alternate-audio upload endpoint. Therefore the pipeline generates the Chinese audio file and records `audio_track_status=generated_studio_upload_required`; it must not report the Chinese audio as attached to the English video unless a verified Studio automation integration confirms that action.

If the channel is not eligible for multi-language audio, the Chinese MP3 remains in the GitHub Actions artifact and can be published as the existing separate Chinese video path without pretending that it is an attached alternate track.

## Idempotency and failure handling

Caption upload uses the same language/name pair and updates an existing track when one is found, preventing `captionExists` on retries. Localization failure does not delete or privatize the already published English video; it is recorded as `failed_pending_retry` in publication metadata and the generated artifacts remain available for the next retry. A failed translation must never alter the English title, English description, English audio, or public privacy status.

## Required workflow controls

`YOUTUBE_LOCALIZATION_ENABLED` defaults to `1` and is exposed as a GitHub Actions variable. Localization assets are uploaded as artifacts under `output/jobs/**/localization/**`. `YOUTUBE_PUBLISH_MODE` remains `public` by default, and the Xiangqi legal-move gate runs before this entire post-publish phase.
