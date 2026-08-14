# Autonomous Production Proof — Run 31769865009

**Date:** 2026-08-14  
**Repository:** `ysrg2003/chinese-cheese-video`  
**Commit used by the production run:** `c4b40d4`  
**Production run:** [31769865009](https://github.com/ysrg2003/chinese-cheese-video/actions/runs/31769865009)  
**Post-production quality gate:** [31771609657](https://github.com/ysrg2003/chinese-cheese-video/actions/runs/31771609657)

## Result

The autonomous production run completed successfully. It passed the autonomous preflight contracts, reconciled the YouTube catalog, discovered and selected curriculum lesson `en-001-what-is-xiangqi`, rendered the video, generated and validated localization artifacts and thumbnails before upload, published the video publicly, associated it with the public `Start Here` playlist, exported the catalog, and committed the SQLite state back to `master`.

The public video is [What Is Xiangqi?](https://www.youtube.com/watch?v=D-o77HngwOU). The SQLite record confirms `status=published`, `privacy_status=public`, `playlist_key=en-start-here`, and the playlist association is `status=published`. The curriculum episode plan is also `status=published`.

## Acceptance checks

| Check | Result | Evidence |
|---|---|---|
| Legal Xiangqi input | Passed | `job.json` contains the verified standard initial FEN; the lesson intentionally has no move sequence because it introduces the board before moves. The deterministic legal-move gate passed in production preflight. |
| English-primary content | Passed | Title, narration, metadata, default language, and public watch page are English-primary. |
| Arabic exclusion | Passed | The generated English job and Chinese localization contain English and Simplified Chinese only; no Arabic artifact was produced. |
| Male voices | Passed | CI environment uses `en-US-GuyNeural` and `zh-CN-YunjianNeural`; no female voice is configured. |
| Captions | Passed | English and Chinese SRT/VTT artifacts were generated; the production log contains two successful YouTube caption API responses. |
| Localized title/description | Passed | The production metadata update contains English and `zh-Hans` localization records. |
| English thumbnail | Passed | `thumbnail_en.jpg` was validated at 1280×720 and below 2 MB, then uploaded as the default YouTube thumbnail. |
| Chinese thumbnail artifact | Generated and validated | `thumbnail_zh.jpg` was generated and retained. YouTube's localized-thumbnail control is marked `studio_upload_required`; the Data API does not expose a general unattended per-language thumbnail upload. |
| Chinese audio | Generated | `zh/voice.mp3` and Chinese captions were generated. The record is `generated_studio_upload_required` because alternate-audio attachment requires eligible YouTube Studio multi-language-audio access; the standard Data API cannot attach this track as a normal caption or video upload. |
| Correct board geometry | Passed | The 1080×1920 clean-board artifact visibly uses intersection placement, a real river gap, and central palace X diagonals. |
| Duplicate protection | Passed | The new ID is `D-o77HngwOU`; it is not one of the previously deleted publication IDs. The catalog guard remains active. |
| Autonomous schedule | Passed | `render-video.yml` remains scheduled at `08:15`, `14:15`, and `20:15` UTC, which is `11:15`, `17:15`, and `23:15` in UTC+3. |
| Regression smoke | Passed | Run 31771609657 completed successfully with the full deterministic/publication contract suite, corrected-board render, thumbnail checks, and fail-closed verification. It performs no YouTube mutation. |

## Visual-asset behavior in this proof

The optional ChatGPT reference-edit service timed out for two requested concept insets after 600 seconds. The production job recorded these failures durably instead of pretending that the images were included. Because the lesson has deterministic board visuals, production continued with the verified Remotion board scenes and still passed the asset/scene/timing contract. No ephemeral ChatGPT history URL was treated as a publishable asset.

This is intentional fail-soft behavior for optional generated imagery: the channel can continue autonomously with correct, deterministic Xiangqi visuals when the external image service is unavailable. A future image is considered part of a video only when it has a durable path, SHA-256 hash, scene mapping, and a visible timing window.

## Local artifact paths

The downloaded proof artifact contains `output/jobs/curriculum-en-001-what-is-xiangqi-en/job.json`, `localization/localization.json`, `localization/en/captions.srt`, `localization/zh/captions.srt`, `localization/zh/voice.mp3`, `prepublish_thumbnails/thumbnail_en.jpg`, `prepublish_thumbnails/thumbnail_zh.jpg`, and `prepublish_thumbnails/clean_board.png`.

## Final repository state

The production-generated SQLite state was rebased locally, the proof documentation was committed as `fa1293c`, pushed to `master`, and the local branch is clean and synchronized with `origin/master`.

## Subsequent delivery-policy refinement

After the proof run, the channel policy was refined so concise English teaching cues remain enabled in the MP4, while the redundant English YouTube caption track is not uploaded by default. Chinese audio and Chinese captions remain active. The thumbnail policy is now English-only: `thumbnail_en.jpg` is generated, validated, and uploaded automatically; `thumbnail_zh.jpg` is no longer generated or required. See `docs/caption_thumbnail_delivery_policy.md` for the contract and official API references.

The delivery-policy commit `620ad32` was subsequently verified by quality-gate run [31773582539](https://github.com/ysrg2003/chinese-cheese-video/actions/runs/31773582539). The GitHub artifact contains only `thumbnail_en.jpg`; the English YouTube caption-track disable policy, English-only thumbnail contract, corrected board render, and fail-closed production checks all passed.
