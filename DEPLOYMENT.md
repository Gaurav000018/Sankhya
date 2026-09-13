# Deploying SANKHYA

The application is host-agnostic: the API is a container, the frontend is a
folder of static files, and everything that differs between environments comes
from environment variables. Nothing below is specific to one provider.

---

## What the platform needs

| Component | Requirement | Why |
|---|---|---|
| **Postgres** | 16+ with `pgvector` | Course and material embeddings are stored as vectors |
| **Redis** | 7+ | Sign-in codes, rate-limit counters, the speech worker queue |
| **Resend** | An account with a verified sending domain | Sign-in codes, confirmation links, password resets |
| **API** | 1 vCPU / 1 GB per instance | Stateless; scale horizontally |
| **Frontend** | Any static host or CDN | Built output is HTML, CSS and JS |
| **Ollama + GPU** | *Optional* | Only the AI interview and question generation need it |

The platform runs without Ollama. Those two features return a clear error; the
Skill Twin, adaptive assessment, recommendations, promotion forecasting and all
analytics work normally.

---

## 1. Configure

```bash
cp .env.production.example .env
```

Fill in every value marked REQUIRED. **The API refuses to start with
`APP_ENV=production` if any of them is missing or still a development
placeholder** — a crash loop is visible, whereas signing tokens with a public
secret is silent and every session issued that way is forgeable.

Generate the signing key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Three settings are easy to get subtly wrong:

- **`CORS_ORIGINS`** — the browser origin, comma-separated, scheme included, no
  trailing slash. Never `*`: these endpoints carry credentials.
- **`PUBLIC_APP_URL`** — the *browser-facing* origin, not the API's. Links in
  emails are built from it, and a confirmation link pointing at the API host
  lands the officer on raw JSON.
- **`EMAIL_FROM`** — the domain must be verified in Resend (SPF + DKIM records
  in DNS), or every send returns 403.

---

## 2. Database

Schema is owned by Alembic in production. The container's entrypoint runs
`alembic upgrade head` before starting the server and exits non-zero if it
fails, so a bad migration stops the deploy instead of leaving an API running
against a schema it does not match.

To seed the demo corpus (204 officers, ~3,700 evidence records) — do this only
on a demo deployment, since it **drops every table first**:

```bash
docker run --rm --env-file .env sankhya-api:prod python -m app.seed.seed
```

A real deployment starts with an empty database, an administrator created by
hand, and officers registering themselves.

### Creating the first administrator

Registration only ever produces a learner. Promote the first account once it
has confirmed its address:

```bash
docker run --rm --env-file .env sankhya-api:prod python -c "
from sqlalchemy import select
from app.db import SessionLocal
from app.models import User, UserRole
db = SessionLocal()
u = db.scalar(select(User).where(User.email == 'admin@yourdomain.gov.in'))
u.role = UserRole.ADMIN
db.commit()
print('promoted', u.email)
"
```

---

## 3. Build and run the API

```bash
docker build -f backend/Dockerfile.prod -t sankhya-api:prod backend
```

```bash
docker run -d --env-file .env -p 8000:8000 --name sankhya-api sankhya-api:prod
```

The production image differs from the development one deliberately: two stages
so the C toolchain does not ship in the running image, a non-root user, four
uvicorn workers instead of `--reload`, and migrations on boot.

### Health endpoints

- **`/health`** — liveness. Does not touch the database, so a brief Postgres
  problem does not get every container killed mid-incident. Point the
  orchestrator's liveness probe here.
- **`/health/ready`** — readiness. Checks Postgres and Redis and returns 503 if
  Postgres is unreachable. Point the load balancer here.

Redis being down reports `degraded`, not failure: the rate limiter fails open
and email OTP is one of four sign-in methods, so the instance can still serve
everything else.

---

## 4. Build and serve the frontend

```bash
cd frontend && npm ci && npm run build
```

Output lands in `frontend/dist`. Two things the host must do:

1. **Serve `index.html` for any unmatched path.** This is a single-page app:
   `/verify?token=…` arrives as a cold page load from an email client, and a
   host that 404s it breaks every confirmation link.
2. **Route `/api/*` to the API.** In development Vite proxies it; in production
   the CDN, reverse proxy or rewrite rule must. Same-origin means no CORS
   preflight on every request and no third-party cookie problems.

If the API is on its own domain instead, set `CORS_ORIGINS` to the frontend
origin and point the frontend at the API with an absolute base URL.

<details>
<summary>Caddy example</summary>

```
sankhya.example.gov.in {
    handle /api/* {
        uri strip_prefix /api
        reverse_proxy sankhya-api:8000
    }
    handle {
        root * /srv/sankhya
        try_files {path} /index.html
        file_server
    }
}
```
</details>

---

## 5. Verify the deployment

```bash
curl -fsS https://sankhya.example.gov.in/api/health/ready
```

Expect `{"status":"ready","database":"ok","redis":"ok","email":"resend"}`.
`"email":"disabled"` means `EMAIL_ENABLED` is false and nobody can complete
registration.

Then walk the real path once: register a gov address, confirm the link from the
inbox, sign in. If the email does not arrive, check the Resend dashboard's
delivery log before anything else — an unverified sending domain is the usual
cause and it is invisible from the application side.

---

## Security posture

What is already handled:

- **Argon2** password hashing; secrets are never logged.
- **Rate limiting** on sign-in, registration, resend and reset — counted per
  email *and* per client IP, since either alone is trivially evaded.
- **Neutral responses** on registration and password reset, so neither can be
  used to discover which officers hold accounts.
- **Single-use tokens**, stored only as a keyed hash. Issuing a new one
  invalidates the last, so an old link in an inbox stops working.
- **Domain-restricted registration**, suffix-matched so `gov.in` admits
  `mospi.gov.in` but not `gov.in.example.com`.
- **A password-change notification**, which is how someone learns their account
  was taken over by an attacker holding the link but not the mailbox.
- **An audit trail** for every authentication event.

What a real government deployment still needs, and this prototype does not have:

- **Parichay SSO.** The adapter is a documented stub that returns 501. Officers
  should not be holding a separate password for this platform at all.
- **httpOnly cookie sessions.** The access token is in `localStorage`, so a
  single XSS becomes a stolen session. The seam is one file
  (`frontend/src/api.ts`) and the change is `Set-Cookie` on the API side.
- **Token revocation.** JWTs are valid until they expire; there is no
  server-side session list, so "sign out everywhere" is not possible. Rotating
  `JWT_SECRET` invalidates every session at once, which is the blunt version.
- **A security review and a pen test** before it holds real officer records.

---

## Operations

**Backups.** The evidence table is the platform — competency levels are derived
from it and nothing else. Point-in-time recovery on Postgres, tested by actually
restoring, not just configured.

**Rotating the signing key.** Change `JWT_SECRET` and redeploy. Every existing
session is invalidated immediately, which is the correct response to a suspected
leak.

**Expired tokens.** `app.core.tokens.purge_expired` deletes rows older than 30
days. Harmless to leave — they are unusable once expired — but worth running
monthly on a long-lived deployment.

**Logs.** The API logs to stdout. Sign-in failures, registrations, verifications
and password changes are also written to the audit table, which survives log
rotation and is what an investigation actually reads.
