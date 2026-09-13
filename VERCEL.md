# Deploying to Vercel

## Read this first

**Vercel can host the frontend. It cannot host this backend.** Not a
configuration problem — four things the platform does are incompatible with
serverless functions:

| What | Why it cannot run on Vercel |
|---|---|
| `app.worker` speech pipeline | A long-running process that polls a Redis queue. Serverless functions exist only for the duration of a request. |
| Ollama (interview scoring, question generation) | A multi-GB model server that needs a GPU. |
| Audio upload → analysis handover | Writes to a shared volume the worker reads. Function filesystems are ephemeral and not shared. |
| Whisper / Vosk / Praat | Hundreds of MB of native wheels, well past the function size limit. |

Even setting those aside, the API imports SQLAlchemy, argon2, reportlab, pypdf,
python-docx and python-pptx at startup — a cold start on every scale-from-zero,
on a service where a sign-in should feel instant.

**The API is already a container.** Run it where containers run.

---

## The shape that works

```
  Vercel            frontend/  (static, global CDN)
      │
      │  /api/*  →  rewrite
      ▼
  Railway/Render/Fly    backend/Dockerfile.prod
      ├── Neon          Postgres 16 + pgvector
      ├── Upstash       Redis
      └── Resend        email
```

Neon, Upstash and Resend are all on the Vercel Marketplace, so they can be
provisioned from the same dashboard and their connection strings land in your
environment automatically.

---

## 1. Deploy the API first

The frontend needs its URL, so this comes first. See
[DEPLOYMENT.md](DEPLOYMENT.md) for the full walkthrough — the short version:

- Build `backend/Dockerfile.prod`.
- Set everything marked REQUIRED in `.env.production.example`.
- `CORS_ORIGINS` — leave for now, you do not know the Vercel URL yet.
- `PUBLIC_APP_URL` — likewise.

Note the API's URL when it comes up, e.g. `https://sankhya-api.up.railway.app`.

---

## 2. Deploy the frontend

**Import the repo in Vercel, then set Root Directory to `frontend`.** Everything
else — framework, build command, output directory, the SPA rewrite — comes from
[frontend/vercel.json](frontend/vercel.json).

Then choose how the browser reaches the API.

### Option A — same-origin rewrite (recommended)

Leave `VITE_API_BASE_URL` unset. Add a rewrite to `frontend/vercel.json`, above
the SPA rule:

```json
"rewrites": [
  { "source": "/api/:path*", "destination": "https://YOUR-API-HOST/:path*" },
  { "source": "/((?!api/).*)", "destination": "/index.html" }
]
```

Order matters — Vercel takes the first match, and the SPA rule would otherwise
swallow `/api/*`.

The browser only ever talks to your Vercel origin, so there is **no CORS
preflight on any request**, and if sessions later move from `localStorage` to
cookies there is no third-party cookie problem to solve.

### Option B — call the API directly

Set an environment variable in the Vercel project:

```
VITE_API_BASE_URL = https://YOUR-API-HOST
```

It is read at **build time**, so changing it requires a redeploy, not just a
restart. Every request becomes cross-origin, so the API's `CORS_ORIGINS` must
list your Vercel origin exactly.

---

## 3. Close the loop

Once Vercel gives you a URL, set these on the **API** and restart it:

```
CORS_ORIGINS=https://your-project.vercel.app
PUBLIC_APP_URL=https://your-project.vercel.app
```

`PUBLIC_APP_URL` is what confirmation and password-reset links are built from.
Point it at the API by mistake and every link in every email lands the officer
on raw JSON.

### Preview deployments

Every branch gets its own URL, and none of them are in `CORS_ORIGINS`. Either
add them as you need them, or accept that previews can render the UI but not
sign in. Option A avoids this entirely — a preview's `/api/*` rewrite reaches
the same API from its own origin, and CORS never enters the picture.

---

## 4. Verify

```bash
curl -fsS https://your-project.vercel.app/api/health/ready
```

Expect `{"status":"ready","database":"ok","redis":"ok","email":"resend"}`.
If you chose Option B this will 404 — check the API's own URL instead.

Then the two things a static host most often gets wrong, both already handled by
`vercel.json` but worth confirming on the real deployment:

```bash
curl -o /dev/null -w '%{http_code}\n' https://your-project.vercel.app/verify?token=x
```

Must be **200**, not 404. Confirmation links arrive as cold page loads from an
email client, and a host that 404s deep links breaks every one of them.

Finally, register a real gov address and confirm the link arrives. If it does
not, check the Resend delivery log before anything else — an unverified sending
domain is the usual cause and it is invisible from the application side.

---

## What will not work, whatever you configure

The **AI interview** and **question generation** need Ollama and the speech
worker. Neither runs on Vercel, and neither runs on a small container host
without a GPU. Everything else — the Skill Twin, adaptive assessment,
recommendations, promotion forecasting, analytics, the ACBP draft — works fully.

For a demo, seed the database and sign in as `venkatesan@sankhya.gov.in`: the
interview report is already populated from seeded evidence, so the screen
demonstrates without needing to record anything live.
