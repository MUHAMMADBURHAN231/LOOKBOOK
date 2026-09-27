# Operations

## Production checklist

1. **HTTPS everywhere.** Put the web app and API behind a TLS-terminating proxy or platform
   (Cloudflare, a load balancer, Vercel for the web app). Set `APP_URL` and `API_URL` to `https://`
   URLs. The API runs uvicorn with `--proxy-headers` so it sees the original scheme.
2. **Same-site cookies.** Serve the app and API from subdomains of one domain (for example
   `app.example.com` and `api.example.com`) and set `COOKIE_DOMAIN=.example.com`.
3. **Secrets.** Generate `SECRET_KEY` and database/Redis passwords with
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Keep them in your platform's
   secret store, never in the repository. The API refuses to start in production with a weak
   `SECRET_KEY`, without Turnstile, without SMTP, or with the owner role in `DATABASE_URL`.
4. **AI provider plans.** Use paid tiers whose terms exclude training on API inputs. Some free tiers
   (including Google AI Studio's) may use inputs to improve their products, which would break the
   privacy promise.
5. **Turnstile.** Create a widget, set `TURNSTILE_SECRET_KEY` (API) and
   `NEXT_PUBLIC_TURNSTILE_SITE_KEY` (web build).
6. **Storage.** Run `python -m scripts.init_storage` once against the production bucket. It blocks
   public access, applies lifecycle retention rules and sets CORS for your app origin.
7. **Merchants.** Insert store rows into `merchants` with a `pk_live_...` key and their exact
   origins, for example `https://shop.example.com`.

## Scaling

- The API is stateless (sessions in Postgres, rate limits and pub/sub in Redis), so run as many
  replicas as needed behind a load balancer. WebSocket connections can land on any replica, since
  progress events fan out through Redis.
- Scale `worker` replicas for try-on throughput. Jobs are acknowledged only after completion, so a
  crashed worker's job is redelivered. Paid calls are capped per day.
- Uploads and downloads go directly between browsers and object storage, so large files never pass
  through the API.
- Put a CDN in front of the web app's static assets.

## Billing alerts

The app enforces its own daily cap (`DAILY_PAID_CALL_BUDGET`) and posts to `ALERT_WEBHOOK_URL` at 80%
and 100%. Also set spending alerts in each provider:

- Google Cloud Billing: budgets and alerts on the Gemini project
- Replicate: spend limit in account settings
- Decart: usage limits in the platform dashboard
- Your cloud host: a billing budget with email alerts

## Backups and restore

The `backup` service writes compressed dumps to `./backups` nightly (7 daily, 4 weekly, 6 monthly).
Copy that folder off the machine (for example with an object-storage sync), since a backup on the same
disk isn't a backup.

Restore into a fresh database:

```bash
ls backups/daily/                     # pick a dump, e.g. lookbook-<date>.sql.gz
gunzip -c backups/daily/<dump>.sql.gz | docker compose exec -T postgres psql -U postgres -d lookbook
```

Test a restore at least once a quarter. On managed Postgres (Neon, Supabase, RDS), also enable
point-in-time recovery.

## Key rotation

- **AI provider keys:** create the new key, update the secret, restart `api` and `worker`, then
  revoke the old key.
- **SECRET_KEY:** rotating invalidates local-storage signed URLs and requires re-encrypting local
  storage files. S3 deployments are unaffected apart from in-flight signed URLs.
- **Database passwords:** `ALTER ROLE lookbook_app PASSWORD '...'`, update `DATABASE_URL`, restart.

## Monitoring

- `GET /healthz`: liveness. `GET /readyz`: database, Redis and storage checks (503 when degraded).
- Logs are JSON in production with request IDs (`X-Request-ID` is echoed to clients for support).
- Alerts for spend thresholds go to `ALERT_WEBHOOK_URL`.
