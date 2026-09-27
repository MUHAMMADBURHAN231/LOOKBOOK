# Security controls

Each control lists where it is implemented and how it is verified. Tests live in
`backend/tests/test_security.py`, `test_features.py` and `test_s3_storage.py`.

## Checklist

| Control | Status | Implementation | Verified by |
|---|---|---|---|
| HTTPS is forced | Yes | API: `HttpsAndHeadersMiddleware` redirects http to https (308) and sends HSTS when `FORCE_HTTPS` (default on in production). Web: `src/proxy.ts` sends HSTS and `upgrade-insecure-requests`. Production config refuses non-https URLs. | `test_production_refuses_unsafe_config` |
| Passwords are hashed | Yes | Argon2id (m=19 MiB, t=2, p=1, OWASP parameters), rehash on login when parameters change. Plain passwords are never stored or logged. | `test_signup_sets_hardened_session_cookie_and_hashes_password` |
| Bot protection on sign-up and public forms | Yes (needs keys) | Cloudflare Turnstile on sign-up, sign-in and forgot-password, verified server side. Production refuses to start without `TURNSTILE_SECRET_KEY`. Plus per-IP and per-email rate limits. | `test_login_rate_limited` |
| Sessions expire | Yes | Server-side sessions: 24 h idle timeout (sliding), 7 day absolute limit, revocable per device, all revoked on password reset. Cookie holds a random token; the database stores only its SHA-256. New session on every login (no fixation). | `test_sessions_expire`, `test_login_rotates_session_and_logout_revokes` |
| CSRF protection | Yes | Double-submit token (`X-CSRF-Token` must match the `lb_csrf` cookie) plus an Origin allowlist on every state-changing request, and `SameSite=Lax` cookies. WebSockets check Origin too. | `test_csrf_required_for_state_changes`, `test_cross_origin_state_change_blocked`, `test_websocket_rejects_foreign_origin` |
| Reset links expire and work once | Yes | 32-byte random token, stored hashed, 30 minute expiry, claimed atomically (`UPDATE ... WHERE used_at IS NULL RETURNING`), older links invalidated when a new one is requested. The token travels in the URL fragment so it never reaches server logs. Forgot-password answers identically for unknown emails. | `test_password_reset_is_single_use_and_revokes_sessions`, `test_password_reset_link_expires`, `test_only_latest_reset_link_works` |
| Database key is limited | Yes | The API and workers connect as `lookbook_app`, which can only SELECT/INSERT/UPDATE/DELETE. Migrations run as `lookbook_owner`. Production refuses an owner URL in `DATABASE_URL`. | `test_app_role_cannot_run_ddl` |
| Logs don't contain secrets | Yes | `RedactingFilter` scrubs passwords, tokens, API keys (Google, Replicate, Decart and others), cookies, bearer credentials, JWTs, Luhn-valid card numbers and email local parts. Access logs omit query strings (signed URLs). Validation errors never echo submitted values. | `test_log_redaction` (6 cases) |
| Billing alerts | Yes | Daily cap on paid AI calls (`DAILY_PAID_CALL_BUDGET`) and per-user try-on cap. Webhook alerts (Slack or Discord) at 80% and 100%. New jobs are refused once the cap is hit. Also set billing alerts in each provider dashboard (see operations.md). | `app/core/spend.py` |
| Automated backups | Yes | `backup` service in docker-compose: nightly `pg_dump`, keeping 7 daily, 4 weekly and 6 monthly dumps. Restore steps in operations.md. On managed Postgres, enable point-in-time recovery as well. | `docker-compose.yml` |

## Further controls

- **Biometric consent (BIPA / GDPR Art. 9):** uploads and try-ons return 403 until consent is recorded
  with a timestamp. Withdrawing consent deletes every portrait and result immediately.
- **Upload safety:** file type is checked from magic bytes (not the client's MIME type), images are
  structurally verified, capped at 50 megapixels (decompression bombs), re-encoded, and stripped of
  metadata including GPS. Portraits that are explicit or appear to show a minor are refused.
- **Encryption at rest:** S3/R2/MinIO objects use SSE-AES256, enforced in the presigned POST policy.
  The local development backend encrypts files with AES-256-GCM.
- **Retention:** raw portraits after 14 days, results after 90 days, temporary files after 1 day,
  via bucket lifecycle rules and a nightly purge job.
- **Access control:** every query is scoped to the signed-in user. Cross-user access returns 404.
- **Content Security Policy:** per-request nonce with `strict-dynamic`, `object-src 'none'`,
  `frame-ancestors 'none'` except `/embed`, which only the merchant's registered origins may frame.
- **Store widget keys:** publishable keys are bound to an origin allowlist, per-IP rate limits and a
  daily session cap. Decart tokens are scoped to one model, our origin, a 5 minute session and a
  10 minute lifetime.
- **Rate limits:** Redis token buckets executed as a single Lua script (no race under load), with
  `Retry-After` headers.
- **Open redirects:** the post-sign-in `next` parameter only accepts same-site paths.
- **Security headers:** `nosniff`, `X-Frame-Options: DENY`, strict referrer policy, restrictive
  permissions policy, `Cache-Control: no-store` on API responses.
