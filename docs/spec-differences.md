# Differences from the technical specification

Where the implementation deliberately differs from the LOOKBOOK technical specification, and why.
Update the specification (or the code) so the two stay in step.

| Spec | Implementation | Reason |
|---|---|---|
| Next.js 15 | Next.js 16 | Current major release at build time. Middleware is called `proxy.ts` in 16. |
| NextAuth route (`api/auth/[...nextauth]`) | Server-side sessions issued by the FastAPI API (HttpOnly cookie + CSRF token) | One source of truth for auth, with sessions, reset tokens and revocation in the same database the API already guards. |
| `ivfflat` index with `lists = 100` | `hnsw` index (`vector_cosine_ops`) | IVFFlat needs thousands of rows to train lists. HNSW gives good recall on a small, growing catalogue. |
| Presigned `PUT` upload | Presigned `POST` with a policy | A POST policy lets S3 enforce content type, a size range and SSE-AES256 itself. `PUT` can't enforce size. |
| DWPose and SCHP as separate worker groups | Separate stages only in the self-hosted GPU adapter. With hosted IDM-VTON, pose and parsing run inside the model, and the UI reports the stages that actually happen. | Hosted IDM-VTON performs its own DensePose + human parsing. Reporting stages we don't run would be misleading. |
| Four separate worker groups | One Celery `tryon` queue whose adapter runs the stages, plus a `default` queue | Simpler to operate at this scale. Queues can be split per stage later without API changes. |
| `/dev/shm` for intermediate masks | Masks never leave the model provider or GPU worker. A `tmp/` storage prefix with 1-day expiry exists for future use. | Nothing intermediate is produced on our side with the current adapters. |
| Raw uploads kept 14 days unless "Retain in Private Vault" | 14 days, no vault option yet. Results kept 90 days. | Vault opt-in is a product decision still to make. |
| `libmagic` byte inspection | Magic-number check in Python plus Pillow structural verification and re-encoding | Same protection without a native dependency. |
| Google SafeSearch / NSFW check | Gemini vision classifier (explicit, violent, apparent minor) before generation, when a Gemini key is set | Uses a provider the app already has. Skipped in development without a key. |
| CLIP ViT-L/14 embeddings | CLIP ViT-L/14 via Replicate when configured, otherwise Gemini embeddings at 768 dims, otherwise an offline hashing embedding | Works with whichever keys exist. Vectors record their model and can be rebuilt with `--reembed`. |
| Gemini 2.5 Pro stylist brain | Configurable (`GEMINI_STYLIST_MODEL`), default `gemini-2.5-pro` | Newer models can be swapped in by configuration. |
| Cloudflare WAF / DDoS layer | Not in the repository | Configured at deploy time in Cloudflare, not in code. |
| Quantitative targets (FID, SSIM, latency, CLIP score) | No evaluation harness yet | Needs a labelled evaluation set and GPU time. Latency per job is recorded (`execution_time_ms`). |
| Try-on execute accepts `garment_id` | Accepts `garment_id` or a free-text `prompt` (parsed by the outfit interpreter) | Matches the natural-language design feature. |
| Not in spec | Live camera try-on (Decart), store widget with merchant keys, spend caps and alerts | Added features. |
