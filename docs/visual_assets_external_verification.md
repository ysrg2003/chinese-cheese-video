# Visual Assets — External Verification Record

## Service and deployment

The visual-assets service is deployed at `https://yousefsg-chatgpt-api.hf.space` and exposes these authenticated endpoints after the deployment commit `e6f5e20`:

- `POST /v1/visual-assets/jobs`
- `GET /v1/visual-assets/jobs/{job_id}`
- `GET /v1/visual-assets/jobs/{job_id}/download`

The service was extended from a text-only browser proxy. It uses a single queued worker, waits for a sufficiently large new image on the ChatGPT page, downloads an HTTP/data image source when available, and otherwise takes an element screenshot for a browser-local blob URL. The extractor scans both assistant message media and page-level media because ChatGPT image cards are not guaranteed to be nested in the text bubble.

## Security configuration

The public Space source no longer contains the browser cookie export. The session is provided only as the write-only Hugging Face Space Secret `CHATGPT_COOKIES_NETSCAPE`; the service reads it from the environment at startup. The service API is protected by an `API_KEY` Space Secret, and GitHub Actions receives the corresponding value only through repository secret `CHATGPT_VISUAL_API_KEY`.

A Hugging Face configuration collision was resolved by deleting the old public `API_KEY` variable that conflicted with the new secret. The Space runtime subsequently reached `RUNNING` on commit `e6f5e20`.

## Live smoke test

A non-published smoke test completed successfully through the service. The generated PNG was 941×1672 pixels and approximately 2.2 MB. It depicted a portrait historical Chinese military-strategy scroll with warm antique-gold and lacquer-red palette, no Xiangqi board grid, no Western chessboard, and no readable text. A Remotion composite confirmed that the asset sits below the title, caption, and storyboard overlays, then clears quickly before the deterministic Xiangqi board explanation.

## Reference documentation

- OpenAI image-generation guide: https://developers.openai.com/api/docs/guides/image-generation
- OpenAI images and vision guide: https://developers.openai.com/api/docs/guides/images
- Hugging Face HfApi reference (`add_space_secret`): https://huggingface.co/docs/huggingface_hub/en/package_reference/hf_api
- Hugging Face Space management guide: https://huggingface.co/docs/huggingface_hub/en/guides/manage-spaces
- Hugging Face Spaces overview: https://huggingface.co/docs/hub/en/spaces-overview

## Published workflow verification

GitHub Actions run `31678909084` completed successfully and published **The River and the Two Palaces** to the public channel and to `EN — Board, Setup, and Notation`. The produced job used the AI Router storyboard and selected two contextual asset plans. The first completed successfully and was attached to scene 1 as `editorial_backdrop`; the second failed during a transient 30-second browser navigation timeout, was recorded in `visualAssets.failures`, and did not block rendering or publication. The service was subsequently updated to set Playwright's navigation timeout to 10 minutes.

A contact sheet verified the deterministic river, palace, rule-focus, board-overview, and learning-roadmap scenes across the lesson. A frame at 0.75 seconds verified the live generated opening image: a portrait heritage landscape with a river separating black and red palace regions, overlaid with exact explanatory markers and the synchronized caption. This confirms that generated assets are rendered in the published MP4, rather than only recorded in job metadata.
