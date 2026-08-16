# Male Voice Comparison — GitHub Actions Run 31930903399

The comparison workflow completed successfully. It generated one identical English Xiangqi sentence with every official male Gemini-TTS voice, plus one clearly labeled Edge TTS reference sample. No video was rendered or published, and no YouTube state was changed.

Sample sentence: “The advisor moves one point diagonally and remains inside the palace.”

| # | Provider | Voice | Result | Duration (s) | MP3 bytes |
|---:|---|---|---|---:|---:|
| 1 | Gemini-TTS | Achird | Success | 5.664 | 48,981 |
| 2 | Gemini-TTS | Algenib | Success | 5.856 | 52,149 |
| 3 | Gemini-TTS | Algieba | Success | 6.048 | 56,589 |
| 4 | Gemini-TTS | Alnilam | Success | 6.024 | 55,581 |
| 5 | Gemini-TTS | Charon | Success | 6.048 | 52,917 |
| 6 | Gemini-TTS | Enceladus | Success | 5.976 | 55,293 |
| 7 | Gemini-TTS | Fenrir | Success | 5.664 | 52,509 |
| 8 | Gemini-TTS | Iapetus | Success | 6.048 | 56,925 |
| 9 | Gemini-TTS | Orus | Success | 5.808 | 49,917 |
| 10 | Gemini-TTS | Puck | Success | 5.544 | 52,485 |
| 11 | Gemini-TTS | Rasalgethi | Success | 6.168 | 54,165 |
| 12 | Gemini-TTS | Sadachbia | Success | 5.736 | 52,749 |
| 13 | Gemini-TTS | Sadaltager | Success | 6.048 | 55,845 |
| 14 | Gemini-TTS | Schedar | Success | 5.928 | 54,813 |
| 15 | Gemini-TTS | Umbriel | Success | 6.144 | 55,125 |
| 16 | Gemini-TTS | Zubenelgenubi | Success | 6.504 | 55,989 |
| 17 | Edge TTS last-resort reference | en-US-GuyNeural | Success | 4.776 | 28,656 |

All 16 official male Gemini-TTS voices succeeded. Edge TTS is now a production **last-resort fallback**, not a peer provider: the complete AI Provider Router chain and its configured keys/models are attempted first; Edge TTS runs only after the router reports a terminal failure and `TTS_EDGE_FALLBACK_ENABLED` is enabled.

## How to listen

The complete MP3 collection is attached to the GitHub Actions run as the artifact named `chinese-cheese-video-31930903399`. Open the [workflow run](https://github.com/ysrg2003/chinese-cheese-video/actions/runs/31930903399), open the artifact section, download it, and listen to the files under `tts-voice-comparison/`. Each directory name contains the provider family and voice name. The Edge file is intentionally labeled `edge_tts_last_resort_reference__en-us-guyneural`.

## Selection

After the user selects a voice, set `TTS_VOICE_EN` and `TTS_VOICE_ZH` to that Gemini voice in `.github/workflows/render-video.yml`. The selected voice remains subject to the same male-voice constraint. If the selected Gemini voice fails at runtime, the router continues through its full chain and only then uses the Edge TTS last-resort fallback.

## Official references

1. [Google Gemini API — Text-to-speech generation](https://ai.google.dev/gemini-api/docs/speech-generation)
2. [Google Cloud — Gemini-TTS](https://docs.cloud.google.com/text-to-speech/docs/gemini-tts)
