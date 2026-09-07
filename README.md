# SANKHYA

Workforce intelligence for India's Official Statistical System — an intelligence
layer over iGOT Karmayogi that measures competency by **demonstration**, not
declaration.

Built for **SIH26101** (MoSPI, Data Informatics & Innovation Division).

---

## The one idea

Competency there is self-declared and progress is measured by course completion,
which records attendance rather than capability. SANKHYA replaces that with a
**Digital Skill Twin**: an append-only evidence record per officer.

```
diagnostic ┐
quiz       ├──> proficiency_evidence ──> competency_profile ──> gaps ──> iGOT path
interview  │      (append-only)            (derived)                        │
simulation │                                                                │
supervisor ┘                       new evidence <───── learning completed <─┘
```

Nothing writes a competency score directly. Every level the platform reports is
derived from evidence and traces back to the artifact that produced it. This is
what gives us trend over time, a full audit trail, and multi-signal blending
without building any of them as separate features.

---

## Running it

Requires Docker Desktop. Ollama runs **natively on the host** (not in Compose) so
it can reach the GPU.

```bash
cp .env.example .env
```

```bash
docker compose up -d --build
```

```bash
docker compose exec api python -m app.seed.seed
```

API docs at <http://localhost:8000/docs>. Health check at `/health`.

### Verifying it works

```bash
python scripts/smoke.py
```

99 checks against the running stack — walks the whole demo narrative: sign in
four ways, read the Skill Twin, rank gaps, run promotion readiness against a
target role, catch the inflated self-rating, append evidence and watch a derived
level move without losing history, generate a cited question and approve it,
build a prerequisite-ordered learning path, produce the ACBP draft, and confirm
RBAC blocks what it should.

It reseeds and flushes Redis first, so it is safe to run repeatedly. Pass
`--no-reset` to test against data you have already changed.

Unit tests need no database or containers:

```bash
cd backend && python -m pytest
```

191 cases covering the reliability model, auth primitives, delivery scoring,
judge output handling, citation verification, the ranking signals and the
promotion simulator.

### The models, and what breaks them

Three checks, each one because the thing it checks failed silently once:

```bash
python scripts/check_judge.py
```

Proves the rubric judge can score an answer, and says which layer broke when it
cannot: Ollama unreachable, the model not pulled, or output the schema rejects.
The judge degrades rather than crashing — right for an officer mid-interview,
useless for whoever is running the machine — so this is the thing that says out
loud whether it works.

```bash
python scripts/check_speech_pipeline.py
```

Synthesises a spoken answer with the Windows speech engine, encodes it as WebM,
and runs the real path: ffmpeg, Whisper, the Vosk disfluency pass, Silero pause
detection, Praat prosody, and the judge. A synthetic voice is not a human one —
this proves the stages connect, not how the numbers behave on real speech.

```bash
python scripts/check_relevance_floor.py
```

Measures how far apart related and unrelated course/competency pairs actually
sit, and fails if the recommender's floor has stopped discriminating between
them.

#### The NVIDIA driver

Ollama's CUDA runners are built against a recent toolkit. On an older driver the
model loads onto the GPU and then the runner dies:

```
CUDA error: device kernel image is invalid
```

Every call then returns HTTP 500 and every interview scores as degraded, which
looks like a bad model rather than a broken runtime. Check the driver with
`nvidia-smi --query-gpu=driver_version --format=csv`; a driver reporting CUDA
12.3 cannot load a runner built for 12.8.

Two ways out. Update the driver, which restores GPU speed. Or run the judge on
the CPU, which works on any driver:

```bash
setx OLLAMA_LLM_LIBRARY cpu
```

Restart Ollama afterwards. A 3B model scores an answer in roughly 15-40 seconds
on CPU, which is fine for an answer that has already been recorded and too slow
to do live. Whisper is unaffected either way — it ships its own CUDA libraries
and keeps the GPU.

Ollama's Vulkan runner is not a third option here: it does not enumerate NVIDIA
devices, so forcing it falls back to CPU anyway.

### The dashboards

```bash
cd frontend && npm install && npm run dev
```

Opens on <http://localhost:3000> and proxies `/api` to the backend, so the
browser stays on one origin and there is no CORS preflight in development.

| Screen | Who sees it | What it shows |
|---|---|---|
| Dashboard | Everyone | Skill Twin radar, gaps, promotion readiness, evidence timeline |
| Team | Supervisor, Admin | Officers by readiness, division × competency heatmap |
| Review queue | SME, Admin | Generated questions, cited passage, approve / reject |
| Workforce | Admin | National priorities, evidence mix, division standing |
| Learning | Everyone | Ranked recommendations with their reasoning, prerequisite-ordered paths |
| Capacity plan | Admin | ACBP draft and course efficacy |
| Interview | Everyone | Calibration, recording, transcript correction, four-axis report |

The interview needs the speech worker running on the host (`cd backend && python
-m app.worker`). To exercise scoring and the report without a microphone or any
models installed:

```bash
python scripts/simulate_interview.py
```

It feeds synthetic measurements through the real scoring service and asserts
what matters: four axes populated, no composite field, and fluency separating a
fluent answer from a hesitant one **on the same baseline** (4.9 vs 1.07).

### Demo accounts

Password for all: `Sankhya@2026`

| Role | Email |
|---|---|
| Learner | `venkatesan@sankhya.gov.in` |
| Supervisor | `director.esd@sankhya.gov.in` |
| SME | `sme@sankhya.gov.in` |
| Admin | `admin@sankhya.gov.in` |

The learner account is the officer from the demo narrative: a Deputy Director in
the Economic Statistics Division with a critical GIS gap and an inflated
self-rating on that same competency.

### Ports

Postgres is on **5433** and Redis on **6380** so they do not collide with local
installs.

---

## Layout

```
backend/app/
  models.py               schema — the evidence spine lives here
  config.py               settings, all overridable by .env
  db.py                   engine, session, init_db
  schemas.py              request/response contracts
  core/
    security.py           argon2, JWT, TOTP
    otp.py                email OTP in Redis, with reuse + rate limits
    mailer.py             SMTP, or dev-mode logging
    deps.py               current user, RBAC gates, audit helper
  services/
    competency.py         derivation, gap analysis, divergence detection
  api/
    auth.py               password / email OTP / TOTP / Parichay stub
    competency.py         Skill Twin, gaps, evidence intake
  seed/seed.py            200 synthetic officers, 12 months of evidence
```

---

## Two design decisions worth knowing before you edit anything

### 1. Evidence is append-only

There is no update path and no delete path for `proficiency_evidence`, and this
is deliberate. To correct a mistake, append a new observation. To retract one,
append with `confidence = 0` and a note. `competency_profile` is a derived cache
— safe to truncate and rebuild at any time, and never written to by feature code.

Reliability is expressed in exactly one place, `SOURCE_WEIGHTS` in
`services/competency.py`:

| Source | Weight | |
|---|---|---|
| Simulation | 1.00 | did the thing, on real data |
| Quiz | 0.85 | |
| Diagnostic | 0.80 | |
| Interview | 0.70 | Knowledge axis only |
| Certification | 0.60 | |
| Supervisor | 0.55 | |
| Learning activity | 0.40 | completion is weak evidence of skill |
| Historical | 0.35 | |
| Self | 0.20 | |

Each observation is additionally scaled by its own confidence and by recency
decay (365-day half-life), so old evidence cannot outvote new evidence forever.

### 2. The AI interview's Fluency and Confidence axes write no evidence

Only the **Knowledge** axis produces competency evidence — see
`record_interview_evidence`.

Hesitation tracks cognitive load and utterance planning, not knowledge; an expert
explaining a hard idea often produces *more* disfluency than someone reciting a
memorised answer. Scoring delivery as competency would also contradict the
platform's own confidence-competence divergence check, and would route
speech-delivery signal into promotion readiness.

Fluency is still measured and shown to the officer as coaching feedback — as a
**deviation from their own read-aloud baseline**, never against a population
mean, so accent and regional speech patterns are not penalised. Officers with a
speech disability can switch fluency scoring off entirely
(`users.fluency_scoring_enabled`) with no effect on the Knowledge axis.

---

## Authentication

Four methods, one interface, all issuing the same JWT:

| Method | Notes |
|---|---|
| Email + password | Argon2id |
| Email OTP | Redis TTL. An unexpired code is **reused** on resend — that single rule keeps sending far below any free-tier cap. Rate limited per address and per hour. |
| TOTP | No delivery, no quota, works with the network off. **This is the one to demo on stage.** |
| Parichay SSO | Adapter stub. Real integration needs ministry onboarding. |

With `EMAIL_ENABLED=false` the OTP is logged and returned in the API response.
A live demo must never depend on an email arriving over venue wifi.

To send real mail, set `EMAIL_ENABLED=true` and use a Gmail **App Password** —
which requires 2-Step Verification to be enabled on that account first, or the
option does not appear in Google account settings.

---

## The recommendation engine

Four signals, combined and kept separate so the explanation can name them:

| Signal | Weight | What it asks |
|---|---|---|
| relevance | 0.40 | Does this address the competency that is short? |
| level fit | 0.25 | Does its band cover the officer's level *and* reach the requirement? |
| urgency | 0.20 | How wide is the gap, and how critical to the role? |
| peers | 0.15 | How many officers in the same role completed it? |

A course with no level overlap is **dropped, not ranked low**. Relevance alone
was once enough to recommend a course the officer had already outgrown, which is
how a recommender stops being believed.

A course may be recommended against a competency it does not itself belong to,
when its content is close enough. The threshold for that is a property of the
**embedder**, not a constant in the recommender: a lexical embedder scores
unrelated text near zero, while a trained one puts everything in a high, narrow
band. Carrying one number across a change of embedder meant every unrelated pair
cleared the bar, and a QGIS course was offered against a team-leadership gap.
`scripts/check_relevance_floor.py` measures both distributions and fails when
the floor stops separating them.

Where a course *is* a substitution, the interface says so, because the
simulator credits the course's own competency and not the gap it was suggested
against.

Every recommendation stores the gap *as it stood when produced*, so its reason
still makes sense once the officer's level moves:

> Closes GIS & Spatial Analysis, where you are assessed at L2.15 and Deputy
> Director requires L4.0. It covers L2.5 to L3.8, which is the band your gap
> sits in. This competency is marked critical for your role. Your level here
> rests on 5 evidence records, strongest from simulation.

Learning paths resolve prerequisites from the course graph and keep going until
the sequence reaches the required level — and when the catalogue cannot get
there, the path says so rather than implying the gap is closed.

## Accessibility

GIGW 3.0 requires WCAG 2.1 AA for Indian government sites, so it is checked
rather than claimed:

```bash
python scripts/check_contrast.py
```

Reads the colour tokens out of `index.css` and computes 22 foreground/background
ratios against the AA thresholds — 4.5:1 for text, 3:1 for UI component
boundaries under 1.4.11. It found six genuine failures on the first run,
including `ink-3` at 3.18:1 on inset panels and input borders at 1.73:1.

```bash
python scripts/check_a11y.py
```

Static checks over the JSX: table headers scoped, every form control
programmatically named, labels pointing at real elements, data tables
captioned, every page setting a document title, and the skip link / main
landmark / named navigation present.

Beyond those: focus moves to the page heading on every route change (a
client-side navigation is otherwise silent to a screen reader), loading states
are `role="status"`, errors are `role="alert"`, and every chart or bar that
carries meaning also prints its value — colour is never the only channel.

## Languages

English and Hindi, switchable from the header and remembered per browser.

```bash
python scripts/check_i18n.py
```

Reports coverage and fails on a broken key — one used in a component but absent
from the catalogue, or defined in Hindi but not English. Currently 79 keys at
100% Hindi coverage.

Three things the implementation does that a naive `t()` does not: missing keys
fall back to **English, never the key itself** (a user shown `nav.dashboard`
learns nothing); `<html lang>` follows the choice, so a screen reader switches
pronunciation instead of reading Devanagari as mispronounced English; and
document titles are translated too, or a Hindi reader gets a Hindi page sitting
in an English tab.

Devanagari uses IBM Plex Sans Devanagari, the metric companion to the Latin
face, so mixed English/Hindi lines keep one baseline.

**The Hindi still needs review by a Hindi-speaking officer before deployment.**
It is hand-written using the vocabulary the statistical system actually uses
(सांख्यिकी, अभिलेख, दक्षता) rather than machine-translated, but a government
interface that reads as translated is worse than one that stays in English.

## The two things no LMS produces

**Course efficacy** (`/analytics/course-efficacy`) — mean assessed level in the
120 days after completing a course, minus the mean in the 120 days before.
Course-completion and self-assessment records are excluded from both windows so
a course cannot supply its own evidence of working.

Reported honestly: samples under five are labelled **provisional**, courses with
no evidence either side are **not measurable** rather than scored zero, and the
payload states that observed lift is *correlational, not causal* — officers who
choose a course are not a random sample.

**ACBP draft** (`/analytics/acbp`) — Mission Karmayogi requires each ministry to
publish an Annual Capacity Building Plan. This computes one from the evidence
base: priority areas ranked by the share of officers short of the role they
actually hold, the divisions worst affected, the intervention that closes it,
and the cost in officer-hours. It is labelled a draft, and the caveat travels
in the payload rather than sitting in a footnote.

## Status

Working end to end, on synthetic data only:

* **Evidence spine** — FRAC model, append-only evidence, derivation with decay,
  gap analysis, divergence detection, historical reconstruction.
* **AI interview** — record, transcode, transcribe, disfluency and pause
  detection, prosody, and a rubric judge on four independent axes. Verified
  against real audio by `scripts/check_speech_pipeline.py`.
* **Question generation** — upload a document or a recording, generate MCQs with
  page-anchored citations, discard anything whose quote is not in the passage,
  and hold the rest for SME approval.
* **Assessment** — difficulty-adjusted scoring that writes evidence, plus
  classical item statistics.
* **Recommendation and planning** — ranked courses with the signals shown,
  prerequisite-ordered paths, the promotion simulator and the readiness
  forecast.
* **Access and audit** — four sign-in methods, RBAC, audit logging.

Not built, and deliberately named rather than implied: the simulation task
(doing the work on real data, the strongest evidence source in the model), the
adaptive follow-up probe, anti-cheat, a RAG-grounded judge, and question
generation in languages other than English.

Nothing here has touched real officer data, and no interview audio is retained
beyond the seconds it takes to analyse it.
