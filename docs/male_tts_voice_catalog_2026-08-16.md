# Male TTS Voice Catalog — 2026-08-16

Google's official Gemini API documentation lists the following Gemini-TTS voices as male:

| Voice | Gender | Official characteristic context |
|---|---|---|
| Achird | Male | Voice option; use preview audio for final choice |
| Algenib | Male | Voice option; use preview audio for final choice |
| Algieba | Male | Voice option; use preview audio for final choice |
| Alnilam | Male | Voice option; use preview audio for final choice |
| Charon | Male | Current production choice; informative |
| Enceladus | Male | Breathiness is noted in the Google prompting guide |
| Fenrir | Male | Voice option; use preview audio for final choice |
| Iapetus | Male | Voice option; use preview audio for final choice |
| Orus | Male | Voice option; use preview audio for final choice |
| Puck | Male | Upbeat; Google suggests it for excited delivery |
| Rasalgethi | Male | Voice option; use preview audio for final choice |
| Sadachbia | Male | Voice option; use preview audio for final choice |
| Sadaltager | Male | Voice option; use preview audio for final choice |
| Schedar | Male | Voice option; use preview audio for final choice |
| Umbriel | Male | Voice option; use preview audio for final choice |
| Zubenelgenubi | Male | Voice option; use preview audio for final choice |

The official page lists 30 total Gemini-TTS voices: 16 male and 14 female. This project must test only the 16 male voices. `Charon` remains the current default until the user selects another voice.

## Sources

1. Google Gemini API — Text-to-speech generation: https://ai.google.dev/gemini-api/docs/speech-generation
2. Google Cloud — Gemini-TTS: https://docs.cloud.google.com/text-to-speech/docs/gemini-tts

## Fallback policy to implement

The production order must be: every configured AI Provider Router audio route and every configured key, according to the router's own ordered chain; then the router's complete provider fallback behavior; and only after the router raises a terminal failure, explicit Edge TTS fallback. Edge TTS must never be tried before the AI Router chain is exhausted, and its use must be recorded in the audio manifest and logs as `edge_tts_last_resort`.
