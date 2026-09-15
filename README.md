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

```bash
cd frontend && npm install && npm run dev
```

The interface is at <http://localhost:3000>, API docs at
<http://localhost:8000/docs>, health at `/health` and `/health/ready`.

Sign in with any seeded account (password `Sankhya@2026`), or register a new one
at `/register` — self-registration is limited to `gov.in` and `nic.in`
addresses. With `EMAIL_ENABLED=false` the API hands the confirmation link back
in the response and the page shows it, so a demo never waits on an email.

### Accounts and email

Officers register themselves, confirm the address, and an administrator then
assigns their division and FRAC role — a new account is always a learner with
no role, because every competency figure is measured against a role and that
must not be self-declared.

Delivery is [Resend](https://resend.com). For real sending, set `EMAIL_ENABLED=true`,
`RESEND_API_KEY`, and an `EMAIL_FROM` on a domain verified in the Resend
dashboard. See [DEPLOYMENT.md](DEPLOYMENT.md).

### Verifying it works

```bash
python scripts/smoke.py
```

129 checks against the running stack — walks the whole demo narrative: sign in
four ways, read the Skill Twin, rank gaps, run promotion readiness against a
target role, catch the inflated self-rating, append evidence and watch a derived
level move without losing history, sit a whole adaptive assessment and confirm
the interval narrows, generate a cited question and approve it, build a
prerequisite-ordered learning path, open an officer's record as an
administrator, produce the ACBP draft, and confirm RBAC blocks what it should.

It reseeds and flushes Redis first, so it is safe to run repeatedly. Pass
`--no-reset` to test against data you have already changed.

Unit tests need no database or containers:

```bash
cd backend && python -m pytest
```

291 cases covering the IRT engine and its ability recovery, the reliability
model, auth primitives, delivery scoring, judge output handling, citation
verification, the ranking signals and the promotion simulator.

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

```bash
python scripts/check_adaptive_gain.py
```

Simulates officers of known ability through the real adaptive loop and checks
two things: that the estimate recovers the ability it was given, and that
choosing items beats asking more of them. Needs no database and no model — it is
pure arithmetic over `app/ml/irt.py`, and it is what makes the comparison table
in [The adaptive assessment](#the-adaptive-assessment) a measurement rather than
a claim.

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

With `EMAIL_ENABLED=false` every code and link is logged and returned in the API
response instead of being sent. A live demo must never depend on an email
arriving over venue wifi — and a production deployment refuses to start in that
state, because nobody could complete registration.

### Account lifecycle

| Step | Endpoint | Notes |
|---|---|---|
| Register | `POST /auth/register` | Restricted to `gov.in` / `nic.in`, suffix-matched so `gov.in.example.com` is refused. Always creates a **learner with no role**. |
| Confirm | `POST /auth/verify` | Single-use, 24h. Consuming it activates the account and signs the officer in — they have just proved control of the mailbox. |
| Forgot | `POST /auth/forgot-password` | 2h link. Issuing one invalidates the last. |
| Reset | `POST /auth/reset-password` | Burns the token, then emails the officer that their password moved — which is how someone learns an attacker reached the link but not the inbox. |
| Change | `POST /auth/change-password` | Requires the current password even though the session is authenticated. |

Registration and password reset answer **identically** whether or not the
address is known. Anything else turns either endpoint into a way to enumerate
which officers hold accounts.

Division and FRAC role are assigned by an administrator, never by the applicant:
every competency figure is measured against a role, and the platform's whole
premise is that competency is not self-declared. A new officer sees a
getting-started page saying exactly that, rather than a dashboard of zeros.

Tokens live in Postgres rather than Redis, stored only as a keyed hash. A
sign-in code is worthless ten minutes later; a confirmation link is the only
route into an account and a reset is a security event that has to stay
auditable.

Sign-in, registration, resend and reset are all rate limited — counted per email
*and* per client IP, since either alone is trivially evaded. Redis being down
fails **open**: the limiter is a brake on abuse, not an authorisation decision,
and the password check behind it is what protects the account.

Delivery is [Resend](https://resend.com), not SMTP: no connection held open
inside a request handler, no app password to rotate, and failures come back as a
status code rather than an exception from deep inside `smtplib`. Sending never
fails a request — if Resend is down, an officer requesting a code gets the same
neutral response they always do.

---

## Taking it to production

[DEPLOYMENT.md](DEPLOYMENT.md) covers the whole path: configuration, Alembic
migrations on boot, the hardened image, health probes, and an honest list of
what a government deployment still needs that this prototype does not have
(Parichay SSO, cookie sessions, token revocation).

The short version: copy `.env.production.example`, fill in everything marked
REQUIRED, and set `APP_ENV=production`. The API **refuses to start** if the JWT
secret is still the development placeholder, if `CORS_ORIGINS` is empty, or if
email sending is off — a crash loop is visible, whereas signing tokens with a
public secret is silent and every session issued that way is forgeable.

---

## The adaptive assessment

A fixed paper asks everybody the same questions, which means most of them are
wrong for most people. An item far below someone's ability is answered correctly
and teaches us nothing; one far above is missed and teaches us nothing either.
Both still cost the officer two minutes.

Item response theory fixes that by putting **items and people on one scale**. An
item has a difficulty `b` — the ability at which someone has an even chance on
it. A person has an ability `theta`. The distance between them predicts the
answer, so the most informative question is always the one nearest the current
estimate.

```
prior N(0, 1.2²)  ──>  pick the item with most Fisher information at θ̂
                            │
                       answer scored
                            │
                  posterior updated on a 161-point grid
                            │
        SE ≤ 0.50?  ──yes──>  stop, write evidence weighted by reliability
             │no
             └──> next item
```

`app/ml/irt.py` holds the mathematics and has no database in it;
`app/services/adaptive_quiz.py` is the part that has to be careful about state.

### The model is 3PL, and that is not a detail

These are four-option items, so somebody who knows nothing still scores 25%. A
two-parameter model has no way to express that, reads guessing as ability, and
biases every low estimate upward — exactly the officers whose gaps matter most.
So the lower asymptote is modelled, fixed at `1/options` rather than estimated:
estimating it well needs thousands of responses per item, and a badly estimated
one is worse than a principled constant.

The cost is information. A 4-option item peaks at 0.155 of Fisher information at
ordinary discrimination, against 0.25 for the same item with no guessing. That
single number sets everything else.

### What twelve questions can actually tell you

Since SE = 1/√(total information), an SE of 0.32 — the figure that sounds
respectable, and the one we reached for first — needs roughly **sixty**
well-targeted items. The stopping threshold is therefore 0.50, which is what
twelve can deliver, and corresponds to a 95% interval of about ±0.65 of a FRAC
level.

The interval is reported everywhere the level is. An assessment claiming ±0.2
from twelve multiple-choice questions would be lying, and the lie would be
invisible.

Adaptation is what makes twelve enough to be worth doing. Against a fixed paper
drawn from the same bank and scored by the same model:

```bash
python scripts/check_adaptive_gain.py
```

| True ability | Adaptive, 12 items | Fixed, 12 items | Fixed, 24 items |
|---|---|---|---|
| L1.67 | **0.73** | 0.84 | 0.66 |
| L2.33 | **0.57** | 0.63 | 0.53 |
| L3.00 | **0.50** | 0.57 | 0.45 |
| L3.67 | **0.57** | 0.65 | 0.49 |
| L4.33 | **0.65** | 0.77 | 0.57 |

RMSE in theta, 400 simulated officers per row; lower is better. Choosing twelve
items well recovers about **two-thirds of what doubling the paper would buy**,
for half the questions — and the margin is widest at the extremes, where the
officers a capacity-building programme most needs to identify actually sit.

The same script checks the prior question, which matters more: that an officer
who truly sits at L4 is reported near L4. It fails loudly if the estimate stops
recovering a known ability, which is what would happen after a sign error in the
posterior update — a bug that otherwise produces plausible numbers and no
symptom at all.

### Where the difficulties come from

Every item ships with the difficulty its author intended. That is a necessary
starting point — an uncalibrated bank cannot adapt at all — but it is a guess,
and authors are reliably wrong in one direction: an expert who knows the answer
cannot see what is hard about the question.

`POST /item-bank/calibrate` re-fits `b` and `a` from real responses once 25
people have answered an item, shrinking towards the authored value rather than
replacing it. The authored figure is kept beside the calibrated one, and the
distance between them is the most useful review signal the bank produces: an
item two theta harder than intended is usually miskeyed.

### Knowing when the bank cannot measure someone

`GET /item-bank/health` reports test information across the whole L1–L5 range
per competency, not just an item count. Twenty items all pitched at L3 measure
L3 precisely and everything else not at all, and a count of twenty hides that.

This is not decoration — it found a real hole. The first run of the expanded
bank reported information of 0.03 at L1 for Team Leadership, whose easiest item
sat at L2.4; an officer below that was answering questions pitched entirely
above them. The `FOUNDATION` band in `app/seed/mcqs_extended.py` exists because
of that report.

The related failure the engine now refuses: when the most informative remaining
item carries less than 0.02, the test **stops and says so** rather than serving
questions that cannot move the estimate. Before that check existed, an officer
at the bottom of the scale was asked three questions carrying 0.004, 0.001 and
0.001 — each unanswerable, each costing them time, each reported as a real
assessment item.

### The item bank

274 hand-written items across 12 competencies, 22–24 each, spanning L1.2 to
L4.9. Every item carries a worked explanation and a rationale for each
distractor, and is seeded APPROVED because an author writing them deliberately
*is* the review a generated item needs.

Options are shuffled at seed time, deterministically from a hash of the stem.
That is a correctness fix, not cosmetics: as authored, 98% of one batch had its
key at position B, because an author writing a plausible distractor first and
the right answer second follows the shape of the explanation in their head. A
candidate who noticed would have outscored one who knew the material.

---

## Officer records

`/officers` is the one screen in the platform that shows a named person rather
than an aggregate, which is why three things about it are deliberate.

**Nothing on it can be edited.** There is no override and no "set level". Every
level is derived from evidence, and the only way to affect one is to append more
through `POST /evidence`, which is audited and attributed. An administrator who
could type a number would make the audit trail a fiction.

**The evidence travels with the level.** Each competency row shows the level,
what the role requires, how many observations sit behind it, and what the
strongest of those was — including the rows that have *no* evidence and are
counted at the floor. A readiness figure with no trail is an assertion, and an
officer being discussed by a promotion board deserves better than one.

**Every drill-down is audited.** Reading a named officer's assessment history is
a privileged act against someone who cannot see that it happened.

Scope is enforced server-side: an administrator sees everyone, a supervisor sees
their own division whatever `division_id` they pass, and an unknown officer id
returns 404 rather than 403 so a supervisor cannot probe for who exists
elsewhere.

One number is shared rather than recomputed. Readiness on the roster is
calculated in SQL for speed and on the detail page by `competency.role_readiness`
in Python; a test asserts they agree, because the first version of the roster
used a different definition and reported 10% for an officer the detail page put
at 76%. Both were right. Having two of them under one word was the bug.

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
  detection, prosody, and a rubric judge on five independent axes. Verified
  against real audio by `scripts/check_speech_pipeline.py`.
* **Question generation** — upload a document or a recording, generate MCQs with
  page-anchored citations, discard anything whose quote is not in the passage,
  and hold the rest for SME approval.
* **Adaptive assessment** — a 3PL item-response model that puts questions and
  officers on one ability scale and picks each question from the answer before
  it, with the estimate and its interval shown live. 274 curated items across 12
  competencies, calibrated from real responses once enough people have answered.
  Classical item statistics kept alongside.
* **Officer records** — a scoped roster and a full per-officer record for
  administrators and supervisors, read-only and audited.
* **Recommendation and planning** — ranked courses with the signals shown,
  prerequisite-ordered paths, the promotion simulator and the readiness
  forecast.
* **Access and audit** — four sign-in methods, RBAC, audit logging.

Not built, and deliberately named rather than implied: the simulation task
(doing the work on real data, the strongest evidence source in the model),
anti-cheat, a RAG-grounded judge, and question generation in languages other
than English.

The assessment's known ceiling is stated rather than hidden: a twelve-item
four-option test resolves ability to about ±0.65 of a FRAC level at 95%, because
guessing costs most of the information an item would otherwise carry. The
interval is reported everywhere the level is, and `/item-bank/health` says which
part of the scale each bank can and cannot measure.

Nothing here has touched real officer data, and no interview audio is retained
beyond the seconds it takes to analyse it.
