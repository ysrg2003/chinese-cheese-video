# AI Router TTS Research — 2026-08-16

Google's official Gemini-TTS documentation identifies `gemini-3.1-flash-tts-preview` and related Gemini TTS models as audio-output models. It documents linear PCM output at 24 kHz in the Interactions API examples and lists the prebuilt voices with gender. `Charon` is explicitly listed as **Male**, while `Kore` is listed as Female.

Sources:

- https://docs.cloud.google.com/text-to-speech/docs/gemini-tts — Gemini-TTS models, output formats, and voice options.
- https://ai.google.dev/gemini-api/docs/speech-generation — Gemini TTS Interactions API examples and PCM/WAV handling.

The updated `ysrg2003/ai-provider-router` repository at the inspected revision exposes `AIRouter.complete_auto(..., output_type="audio", voice=...)`. Its Gemini adapter returns `output_type=audio`, `mime_type`, base64 audio data, and `sample_rate_hz=24000`; its configured audio route begins with `gemini-3.1-flash-tts-preview` and then `gemini-2.5-flash-preview-tts`.
