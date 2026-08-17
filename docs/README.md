# Documentation Index

The documentation is organized as a beginner path followed by operational references. All canonical project documentation is English-only; identifiers, commands, model names, and provider fields remain exactly as implemented.

| Document | Start here when you need to… |
| --- | --- |
| [`../README.md`](../README.md) | Install the project, understand the architecture, run a first safe check, or learn the production contracts |
| [`configuration.md`](configuration.md) | Configure GitHub Secrets and Variables, local `.env`, API keys, OAuth, provider chains, and rotation |
| [`operations.md`](operations.md) | Run scheduled or manual workflows, inspect artifacts, back up SQLite, recover pending publication, or prepare a release |
| [`integrations.md`](integrations.md) | Understand GitHub Actions, AI Router, Gemini grounding, visual assets, YouTube, Hugging Face, and Supabase |
| [`troubleshooting.md`](troubleshooting.md) | Diagnose failed preflight, claims, visual QA, TTS, thumbnails, uploads, ordering, or secrets |
| [`independent_automation.md`](independent_automation.md) | Understand the autonomous architecture, provider order, selection, deduplication, and persistence |
| [`release-v1.3.0-production-ready.md`](release-v1.3.0-production-ready.md) | Review the final production-ready baseline and its verification evidence |

## Historical and contract references

The repository also contains focused research notes, quality reports, visual specifications, curriculum notes, localization policies, and historical incident reports. They explain why individual safeguards exist. For current operational behavior, prefer the documents above and the source files they reference. A historical report must not override the current workflow or code contract.

## Documentation maintenance rule

When production behavior changes, update the relevant canonical document in the same pull request. Every new secret requires a credential card in `configuration.md`; every new workflow input requires an operations entry; every new provider requires an integration and troubleshooting entry; and every new release must record its verification evidence without including credentials.

## References

[1]: https://docs.github.com/actions/security-guides/using-secrets-in-github-actions "Using secrets in GitHub Actions"
[2]: https://developers.google.com/youtube/v3/guides/authentication "YouTube Data API OAuth 2.0"
[3]: https://github.com/ysrg2003/ai-provider-router "Reusable AI Provider Router"
