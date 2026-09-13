import { useEffect, useRef, useState } from "react";
import type { MouseEvent } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth";
import { Faq } from "../components/landing/Faq";
import { IrtDemo } from "../components/landing/IrtDemo";
import {
  EvidenceLoop,
  EvidenceTicker,
  ProductPreview,
} from "../components/landing/ProductPreview";
import {
  Eyebrow,
  Glow,
  Marquee,
  Metric,
  Pill,
  Reveal,
  SectionHeading,
  SplitWords,
  trackSpotlight,
} from "../components/landing/Primitives";
import { useInView, useRevealOnScroll } from "../hooks/useReveal";
import { usePageTitle } from "../hooks/usePageTitle";

/**
 * The public face of the platform.
 *
 * Deliberately a different surface from the product: dark, wide, typographic,
 * and paced for a first read rather than a working session. Everything it
 * claims is something the running system does — the figures come from the
 * seeded corpus and the capability list maps one-to-one onto shipped routes.
 *
 * A signed-in officer can land here too (the mark in the app nav points at
 * it); the calls to action then point at their dashboard rather than at
 * sign-in.
 */

function MarkGlyph({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M4 20V13" />
      <path d="M9.3 20V8" />
      <path d="M14.7 20V15" />
      <path d="M20 20V4" />
    </svg>
  );
}

/** Inline glyph for "evidence" — a record with a verified mark. */
function EvidenceGlyph() {
  return (
    <span className="relative mx-[0.12em] inline-flex h-[0.62em] w-[0.62em] -translate-y-[0.14em] items-center justify-center rounded-[0.14em] border border-accent/45 bg-tint-accent align-baseline">
      <svg viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" className="h-[58%] w-[58%]" aria-hidden="true">
        <path d="M20 6 L9 17 L4 12" />
      </svg>
    </span>
  );
}

/** Inline glyph for "AI" — a four-point spark. */
function SparkGlyph() {
  return (
    <span className="relative mx-1 inline-block h-[0.8em] w-[0.8em] -translate-y-[0.04em] align-middle">
      <svg viewBox="0 0 24 24" fill="var(--color-good)" className="h-full w-full animate-glow" aria-hidden="true">
        <path d="M12 0 L14.6 9.4 L24 12 L14.6 14.6 L12 24 L9.4 14.6 L0 12 L9.4 9.4 Z" />
      </svg>
    </span>
  );
}

const CAPABILITIES = [
  {
    title: "Digital Skill Twin",
    body: "A living competency profile per officer, derived from every signal the platform collects. Twelve competencies across four domains, each on the FRAC L1–L5 scale, each traceable to the records that produced it.",
    route: "Dashboard",
  },
  {
    title: "Adaptive assessment",
    body: "Item Response Theory over a calibrated item bank. Difficulty adapts to the estimated ability after every answer, so eight well-chosen questions locate a level more tightly than fifty fixed ones.",
    route: "Assessment",
  },
  {
    title: "AI interview",
    body: "A spoken interview that generates its own follow-ups from what was actually said. Scored on knowledge, structure, communication and fluency — with the transcript and the rubric shown next to the score.",
    route: "Interview",
  },
  {
    title: "Grounded question generation",
    body: "Upload a circular, a manual or a past paper. Questions are generated against retrieved passages, carry a citation back to the source page, and wait in a review queue until an SME approves them.",
    route: "Review queue",
  },
  {
    title: "Explained recommendations",
    body: "A contextual bandit ranks candidate courses from the iGOT catalogue against the officer's gap vector — and states in plain language why each one was chosen, including the peer signal behind it.",
    route: "Learning",
  },
  {
    title: "Promotion readiness",
    body: "Readiness against any target role, the competencies still short, the service-years requirement, and a forecast built from the officer's own rate of movement rather than an assumed one.",
    route: "Promotion",
  },
  {
    title: "Workforce analytics",
    body: "Division-by-competency heatmaps, course efficacy measured as realised competency gain, and the evidence mix — how much of what the organisation believes rests on demonstration rather than attendance.",
    route: "Workforce",
  },
  {
    title: "Draft capacity plans",
    body: "An Annual Capacity Building Plan assembled from measured organisational gaps, with the cohort size, the competency it targets and the evidence behind each line item.",
    route: "Capacity plan",
  },
];

const PILLARS = [
  {
    k: "01",
    title: "Evidence is append-only",
    body: "A correction is a new record, never an edit. That is what makes a trend real and an audit possible — and it is why a level can be defended six months later.",
  },
  {
    k: "02",
    title: "Signals are weighted, not equal",
    body: "Demonstrated work outranks a course completion, and self-assessment counts for least. When self-rating and evidence disagree, the platform says so rather than averaging the disagreement away.",
  },
  {
    k: "03",
    title: "Every number is explainable",
    body: "No score appears without the records it came from. A recommendation states its reason; a generated question carries its citation; a forecast shows the rate it extrapolated.",
  },
];

const METHOD = [
  {
    tone: "border-accent",
    title: "Item Response Theory for the level",
    body: "Each competency is a latent trait. Every item carries a difficulty and a discrimination parameter; the officer carries an ability estimate per domain. The gap is the role's required θ minus the current estimate — a quantity with a confidence interval, not a percentage.",
  },
  {
    tone: "border-good",
    title: "A contextual bandit for the recommendation",
    body: "Arms are courses, the reward is measured competency gain after completion, the context is the officer's profile vector. Semantic retrieval over course descriptions generates candidates; the bandit ranks them. This handles the cold start that collaborative filtering cannot.",
  },
  {
    tone: "border-brass",
    title: "Generated questions are calibrated, not dumped in",
    body: "A generated item enters with a predicted difficulty prior, waits for SME approval, and is then updated from real response data as officers answer it. Generation feeds the item bank; the item bank feeds the estimate. That loop is the centre of the architecture.",
  },
];

export function Landing() {
  usePageTitle("title.landing");
  const { user } = useAuth();
  const page = useRef<HTMLDivElement>(null);
  const hero = useRef<HTMLElement>(null);
  const progress = useRef<HTMLSpanElement>(null);
  useRevealOnScroll(page);

  const [previewRef, previewInView] = useInView<HTMLDivElement>(0.25);

  // The nav gains a background only once the hero is behind it, so the top of
  // the page stays one uninterrupted surface. The progress hairline is written
  // straight to the DOM: a state update on every scroll event would re-render
  // the whole page for a one-pixel line.
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => {
      setScrolled(window.scrollY > 24);
      const max = document.documentElement.scrollHeight - window.innerHeight;
      if (progress.current && max > 0) {
        progress.current.style.width = `${(window.scrollY / max) * 100}%`;
      }
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Pointer effects only where there is a pointer to follow and the user has
  // not asked for stillness.
  const [pointerFine, setPointerFine] = useState(false);
  useEffect(() => {
    const fine = window.matchMedia?.("(hover: hover) and (pointer: fine)").matches;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    setPointerFine(Boolean(fine && !reduced));
  }, []);

  const frame = useRef(0);
  const onHeroMove = (e: MouseEvent<HTMLElement>) => {
    const el = hero.current;
    if (!el || !pointerFine) return;
    const { clientX, clientY } = e;
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      const r = el.getBoundingClientRect();
      const nx = (clientX - r.left) / r.width - 0.5;
      const ny = (clientY - r.top) / r.height - 0.5;
      el.style.setProperty("--mx", `${clientX - r.left}px`);
      el.style.setProperty("--my", `${clientY - r.top}px`);
      el.style.setProperty("--rx", `${(nx * 9).toFixed(2)}deg`);
      el.style.setProperty("--ry", `${(-ny * 7).toFixed(2)}deg`);
    });
  };
  const onHeroLeave = () => {
    const el = hero.current;
    if (!el) return;
    el.style.setProperty("--rx", "0deg");
    el.style.setProperty("--ry", "0deg");
  };

  const primaryTo = user ? "/dashboard" : "/login";
  const primaryLabel = user ? "Go to your dashboard" : "Open the live demo";

  return (
    <div ref={page} className="min-h-full overflow-x-hidden bg-ground">
      <a href="#main" className="skip-link">
        Skip to main content
      </a>

      {/* ------------------------------------------------------------- nav -- */}
      <header
        className={`fixed inset-x-0 top-0 z-50 transition-colors duration-300 ${
          scrolled ? "border-b border-rule bg-ground/85 backdrop-blur-xl" : "border-b border-transparent"
        }`}
      >
        <span
          ref={progress}
          aria-hidden="true"
          className="absolute left-0 top-0 h-px bg-accent shadow-[0_0_8px_var(--color-accent)]"
          style={{ width: "0%" }}
        />
        <div className="mx-auto flex h-16 max-w-[1180px] items-center justify-between gap-6 px-6">
          <Link to="/" className="flex items-center gap-2.5">
            <MarkGlyph className="h-5 w-5 text-accent" />
            <span className="font-serif text-[17px] font-semibold tracking-[0.1em]">
              SANKHYA
            </span>
          </Link>

          <nav aria-label="Sections" className="hidden items-center gap-7 md:flex">
            {[
              ["How it works", "#how"],
              ["Capabilities", "#capabilities"],
              ["The method", "#method"],
              ["Questions", "#questions"],
            ].map(([label, href]) => (
              <a
                key={href}
                href={href}
                className="text-[13.5px] text-ink-2 transition-colors hover:text-ink"
              >
                {label}
              </a>
            ))}
          </nav>

          <div className="flex items-center gap-2.5">
            {!user && (
              <Link
                to="/login"
                className="hidden text-[13.5px] text-ink-2 transition-colors hover:text-ink sm:block"
              >
                Sign in
              </Link>
            )}
            <Pill to={primaryTo} tone="solid" size="sm">
              {user ? "Dashboard →" : "Open the demo"}
            </Pill>
          </div>
        </div>
      </header>

      <main id="main" tabIndex={-1}>
        {/* ----------------------------------------------------------- hero -- */}
        <section
          ref={hero}
          onMouseMove={onHeroMove}
          onMouseLeave={onHeroLeave}
          className="relative overflow-hidden pt-32 pb-24 sm:pt-40 sm:pb-32"
        >
          <div aria-hidden="true" className="grid-rule absolute inset-0 -z-20 opacity-70" />
          {/* Fades the grid out before it reaches the content, so the texture
              never competes with the headline. */}
          <div
            aria-hidden="true"
            className="absolute inset-0 -z-20"
            style={{
              background:
                "radial-gradient(ellipse 70% 55% at 50% 0%, transparent 20%, var(--color-ground) 78%)",
            }}
          />
          {/* Pointer-following light. */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 -z-10 transition-opacity duration-500"
            style={{
              opacity: pointerFine ? 1 : 0,
              background:
                "radial-gradient(560px circle at var(--mx, 50%) var(--my, 30%), rgb(56 239 141 / 0.09), transparent 62%)",
            }}
          />
          <Glow className="left-1/2 top-[-8rem] h-[34rem] w-[46rem] -translate-x-1/2" opacity={0.13} />
          <Glow
            className="left-[8%] top-[26rem] h-[22rem] w-[22rem]"
            colour="var(--color-good)"
            opacity={0.08}
          />

          <div className="mx-auto max-w-[1180px] px-6">
            <div className="word flex justify-center" style={{ ["--d" as string]: "0ms" }}>
              <div className="inline-flex items-center gap-2.5 rounded-full border border-rule bg-surface/70 px-4 py-1.5 backdrop-blur">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-70" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
                </span>
                <span className="text-[12.5px] text-ink-2">
                  Built for MoSPI · Data Informatics &amp; Innovation Division
                </span>
              </div>
            </div>

            <h1 className="mx-auto mt-8 max-w-[19ch] text-center font-serif text-[clamp(2.6rem,7.4vw,5.25rem)] font-light leading-[1.02] tracking-[-0.035em]">
              <SplitWords text="The future of" start={120} />
              <br />
              <SplitWords text="capacity building is" start={330} />
              <br />
              <span className="word inline-block" style={{ ["--d" as string]: "560ms" }}>
                <EvidenceGlyph />
              </span>
              <span className="word inline-block text-gradient" style={{ ["--d" as string]: "620ms" }}>
                evidence
              </span>{" "}
              <span className="word inline-block text-ink-3" style={{ ["--d" as string]: "690ms" }}>
                +
              </span>{" "}
              <span className="word inline-block" style={{ ["--d" as string]: "760ms" }}>
                <SparkGlyph />
              </span>
              <span className="word inline-block text-gradient" style={{ ["--d" as string]: "820ms" }}>
                AI
              </span>
            </h1>

            <p
              className="word mx-auto mt-7 max-w-[58ch] text-center text-[16px] leading-relaxed text-ink-2"
              style={{ ["--d" as string]: "950ms" }}
            >
              iGOT Karmayogi records that an officer attended. SANKHYA measures what
              they can actually do — and keeps the proof, so a promotion board sees a
              trend with evidence behind it, not a certificate.
            </p>

            <div
              className="word mt-9 flex flex-wrap items-center justify-center gap-3"
              style={{ ["--d" as string]: "1050ms" }}
            >
              <Pill to={primaryTo} tone="solid">
                {primaryLabel}
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" className="h-3.5 w-3.5">
                  <path d="M5 12h13M13 6l6 6-6 6" />
                </svg>
              </Pill>
              <Pill href="#how">See how it works</Pill>
            </div>

            <p
              className="word mt-5 text-center font-mono text-[11.5px] text-ink-3"
              style={{ ["--d" as string]: "1150ms" }}
            >
              Four demo roles · no signup · seeded with 204 officers
            </p>

            <div
              ref={previewRef}
              className="word relative mx-auto mt-16 max-w-[980px] sm:mt-20"
              style={{ ["--d" as string]: "1250ms" }}
            >
              <Glow className="inset-x-12 bottom-[-3rem] h-40" opacity={0.2} />
              <ProductPreview active={previewInView} />
              <div
                className="absolute -bottom-10 -left-4 hidden md:block"
                style={{
                  opacity: previewInView ? 1 : 0,
                  transform: previewInView ? "none" : "translateY(12px)",
                  transition: "opacity 0.7s ease 1.9s, transform 0.7s ease 1.9s",
                }}
              >
                <EvidenceTicker active={previewInView} />
              </div>
            </div>
          </div>
        </section>

        {/* --------------------------------------------------- trust strip -- */}
        <section aria-label="Grounded in" className="border-y border-rule py-7">
          <div className="mx-auto max-w-[1180px] px-6">
            <p className="text-center font-mono text-[11px] uppercase tracking-[0.2em] text-ink-3">
              Built against the frameworks the statistical system already uses
            </p>
            <div className="mt-5">
              <Marquee
                items={[
                  "iGOT Karmayogi",
                  "FRAC competency scale",
                  "NSSTA / TPAC",
                  "Mission Karmayogi",
                  "MoSPI ACBP",
                  "Parichay SSO",
                  "Bloom's taxonomy",
                  "2PL Item Response Theory",
                ]}
              />
            </div>
          </div>
        </section>

        {/* -------------------------------------------------------- problem -- */}
        <section className="relative py-24 sm:py-32">
          <div className="mx-auto max-w-[1180px] px-6">
            <SectionHeading
              eyebrow="The gap"
              title={
                <>
                  A completion certificate is a record of{" "}
                  <span className="text-ink-3">attendance</span>, not of{" "}
                  <span className="text-accent">capability</span>.
                </>
              }
              lede="Competency on iGOT is self-declared and progress is measured by courses finished. So an officer who has completed eleven modules and one who can actually design a sampling frame look identical in the data — and the training budget gets allocated on that basis."
            />

            <div className="mt-14 grid gap-4 md:grid-cols-2">
              <Reveal>
                <div className="h-full rounded-xl border border-rule bg-surface p-6">
                  <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-3">
                    Today
                  </div>
                  <ul className="mt-5 space-y-3.5">
                    {[
                      "Competency is whatever the officer ticked",
                      "Progress means courses completed",
                      "Training is chosen from a catalogue, by hand",
                      "Nobody can tell which course changed anything",
                    ].map((line) => (
                      <li key={line} className="flex gap-3 text-[14px] text-ink-2">
                        <span className="mt-[0.45em] h-px w-3.5 shrink-0 bg-rule-strong" />
                        {line}
                      </li>
                    ))}
                  </ul>
                </div>
              </Reveal>

              <Reveal delay={110}>
                <div className="spotlight relative h-full overflow-hidden rounded-xl border border-accent/30 bg-surface p-6" onMouseMove={trackSpotlight}>
                  <Glow className="right-[-6rem] top-[-6rem] h-56 w-56" opacity={0.12} />
                  <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-accent">
                    With SANKHYA
                  </div>
                  <ul className="mt-5 space-y-3.5">
                    {[
                      "Competency is derived from demonstrated work",
                      "Progress is a measured change in level, with a date",
                      "The next course is ranked, and the ranking is explained",
                      "Course efficacy is measured as realised competency gain",
                    ].map((line) => (
                      <li key={line} className="flex gap-3 text-[14px]">
                        <svg viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" className="mt-[0.15em] h-4 w-4 shrink-0">
                          <path d="M20 6 L9 17 L4 12" />
                        </svg>
                        {line}
                      </li>
                    ))}
                  </ul>
                </div>
              </Reveal>
            </div>
          </div>
        </section>

        {/* ---------------------------------------------------- how it works -- */}
        <section id="how" className="relative scroll-mt-20 border-y border-rule bg-surface/30 py-24 sm:py-32">
          <div className="mx-auto max-w-[1180px] px-6">
            <SectionHeading
              eyebrow="How it works"
              title="One loop, and everything else is a view onto it."
              lede="Diagnostics, quizzes, interviews, simulations and supervisor sign-off all write the same kind of row. Levels are derived from those rows — never written directly — which is what buys trend over time, a full audit trail, and multi-signal blending without building any of them as separate features."
            />
            <Reveal delay={120} className="mt-12">
              <EvidenceLoop />
            </Reveal>

            <div className="mt-8 grid gap-4 sm:grid-cols-3">
              {PILLARS.map((p, i) => (
                <Reveal key={p.k} delay={i * 90} className="spotlight h-full rounded-xl border border-rule bg-surface p-5" onMouseMove={trackSpotlight}>
                  <span className="font-mono text-[11px] text-accent">{p.k}</span>
                  <h3 className="mt-3 text-[15px] font-semibold">{p.title}</h3>
                  <p className="mt-2 text-[13.5px] leading-relaxed text-ink-2">{p.body}</p>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* --------------------------------------------------- capabilities -- */}
        <section id="capabilities" className="scroll-mt-20 py-24 sm:py-32">
          <div className="mx-auto max-w-[1180px] px-6">
            <SectionHeading
              eyebrow="Capabilities"
              title="Eight surfaces over one evidence record."
              lede="Each of these is a route in the running application, not a roadmap item."
            />
            <ul className="mt-14 grid gap-px overflow-hidden rounded-xl border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-4">
              {CAPABILITIES.map((c, i) => (
                <Reveal
                  as="li"
                  key={c.title}
                  delay={(i % 4) * 70}
                  className="spotlight group relative bg-ground p-6 transition-colors duration-300 hover:bg-surface"
                  onMouseMove={trackSpotlight}
                >
                  <div className="relative flex h-full flex-col">
                    <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-3 transition-colors group-hover:text-accent">
                      {c.route}
                    </span>
                    <h3 className="mt-3 text-[16px] font-semibold leading-snug">{c.title}</h3>
                    <p className="mt-2.5 text-[13px] leading-relaxed text-ink-2">{c.body}</p>
                  </div>
                  {/* A hairline that draws in on hover, in place of a border that
                      would otherwise sit there permanently adding noise. */}
                  <span
                    aria-hidden="true"
                    className="absolute inset-x-0 bottom-0 h-px origin-left scale-x-0 bg-accent transition-transform duration-500 group-hover:scale-x-100"
                  />
                </Reveal>
              ))}
            </ul>
          </div>
        </section>

        {/* --------------------------------------------------------- method -- */}
        <section id="method" className="relative scroll-mt-20 overflow-hidden border-y border-rule bg-surface/30 py-24 sm:py-32">
          <Glow className="left-[-10rem] top-1/3 h-[26rem] w-[26rem]" colour="var(--color-good)" opacity={0.1} />
          <div className="mx-auto max-w-[1180px] px-6">
            <SectionHeading
              eyebrow="The method"
              title="A calibrated ability estimate, not a quiz score."
              lede="Most of this problem space gets solved with a similarity score and a language model. Both are hard to defend when an officer asks why they were told to take a particular course — or why their level is what it is. Below is the actual estimator, running."
            />

            <Reveal delay={120} className="mt-12">
              <IrtDemo />
            </Reveal>

            <div className="mt-8 grid gap-4 lg:grid-cols-3">
              {METHOD.map((m, i) => (
                <Reveal key={m.title} delay={i * 90}>
                  <div className={`h-full border-l-2 ${m.tone} pl-5`}>
                    <h3 className="text-[15px] font-semibold">{m.title}</h3>
                    <p className="mt-2 text-[13.5px] leading-relaxed text-ink-2">{m.body}</p>
                  </div>
                </Reveal>
              ))}
            </div>

            <Reveal delay={120} className="mt-14">
              <div className="rounded-xl border border-rule bg-surface p-7">
                <Eyebrow>In the seeded system</Eyebrow>
                <div className="mt-7 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
                  <Metric
                    value={204}
                    label="Officers"
                    note="Across 8 divisions in 5 states, on 6 FRAC roles."
                  />
                  <Metric
                    value={3683}
                    label="Evidence records"
                    note="Append-only. Every derived level traces back to these."
                  />
                  <Metric
                    value={12}
                    label="Competencies"
                    note="Over 4 domains: statistical, technical, digital governance, behavioural."
                  />
                  <Metric
                    value={99}
                    label="Smoke checks"
                    note="Run against the live stack, walking the whole demo narrative end to end."
                  />
                </div>
              </div>
            </Reveal>
          </div>
        </section>

        {/* ---------------------------------------------------- integration -- */}
        <section id="integration" className="scroll-mt-20 py-24 sm:py-32">
          <div className="mx-auto max-w-[1180px] px-6">
            <div className="grid gap-12 lg:grid-cols-2 lg:items-center">
              <div>
                <SectionHeading
                  eyebrow="Integration, stated plainly"
                  title="iGOT is a catalogue. This is the matching layer on top of it."
                  lede="There is no public iGOT Karmayogi API. Rather than fake an integration, the connector is built as a documented adapter against the published catalogue schema, backed by a hand-assembled catalogue of real NSSTA and iGOT programmes. Production credentials would be provisioned by DIID; nothing else in the architecture changes when they are."
                />
              </div>

              <Reveal delay={120}>
                <div className="overflow-hidden rounded-xl border border-rule bg-surface font-mono text-[12px]">
                  <div className="flex items-center justify-between border-b border-rule px-4 py-2.5">
                    <span className="text-ink-3">app/services/igot.py</span>
                    <span className="rounded-full border border-brass/40 bg-tint-brass px-2 py-0.5 text-[10px] text-brass">
                      adapter
                    </span>
                  </div>
                  <pre className="overflow-x-auto p-4 leading-[1.75] text-ink-2">
                    <code>
                      <span className="text-ink-3">
                        {"# One interface, two implementations. The mock is seeded\n"}
                        {"# from the published catalogue schema; swapping in the\n"}
                        {"# live client is a constructor change, nothing more.\n"}
                      </span>
                      {"\n"}
                      <span className="text-good">class</span>{" "}
                      <span className="text-ink">CourseCatalogue</span>
                      {"(Protocol):\n"}
                      {"    "}
                      <span className="text-good">def</span>{" "}
                      <span className="text-accent">search</span>
                      {"(self, gap: GapVector) -> list[Course]: ...\n"}
                      {"    "}
                      <span className="text-good">def</span>{" "}
                      <span className="text-accent">completions</span>
                      {"(self, officer_id: int) -> list[Record]: ...\n"}
                    </code>
                  </pre>
                </div>
              </Reveal>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------ questions -- */}
        <section id="questions" className="scroll-mt-20 border-t border-rule bg-surface/30 py-24 sm:py-32">
          <div className="mx-auto max-w-[1180px] px-6">
            <div className="grid gap-12 lg:grid-cols-[380px_minmax(0,1fr)] lg:items-start">
              <SectionHeading
                eyebrow="Hard questions"
                title="What a data-informatics evaluator will ask."
                lede="And what the architecture answers. None of these are hypothetical; each is a design decision you can find in the code."
              />
              <Faq />
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------ cta -- */}
        <section className="relative overflow-hidden border-t border-rule py-24 sm:py-32">
          <Glow className="left-1/2 top-1/2 h-[24rem] w-[42rem] -translate-x-1/2 -translate-y-1/2" opacity={0.13} />
          <div className="mx-auto max-w-[1180px] px-6 text-center">
            <Reveal>
              <h2 className="mx-auto max-w-[20ch] font-serif text-[clamp(2rem,4.6vw,3.25rem)] font-light leading-[1.08] tracking-[-0.03em]">
                Sign in as an officer and watch a level move.
              </h2>
            </Reveal>
            <Reveal delay={90}>
              <p className="mx-auto mt-5 max-w-[54ch] text-[15px] leading-relaxed text-ink-2">
                The demo starts on an officer with a critical leadership gap and an
                inflated self-rating on the same competency. Add evidence and the derived
                level moves — without losing a single earlier record.
              </p>
            </Reveal>
            <Reveal delay={160}>
              <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
                <Pill to={primaryTo} tone="solid">
                  {user ? "Go to your dashboard" : "Open the demo"}
                </Pill>
                <Pill href="#how" tone="ghost">
                  Read the architecture
                </Pill>
              </div>
            </Reveal>
            <Reveal delay={220}>
              <div className="mx-auto mt-10 grid max-w-2xl gap-px overflow-hidden rounded-lg border border-rule bg-rule sm:grid-cols-4">
                {[
                  ["Officer", "learner"],
                  ["Supervisor", "team view"],
                  ["SME", "review queue"],
                  ["Admin", "workforce"],
                ].map(([role, what]) => (
                  <div key={role} className="spotlight bg-ground px-3 py-3.5" onMouseMove={trackSpotlight}>
                    <div className="relative text-[13px] font-medium">{role}</div>
                    <div className="relative mt-0.5 font-mono text-[10.5px] text-ink-3">{what}</div>
                  </div>
                ))}
              </div>
            </Reveal>
          </div>
        </section>
      </main>

      {/* --------------------------------------------------------- footer -- */}
      <footer className="border-t border-rule py-10">
        <div className="mx-auto flex max-w-[1180px] flex-col items-center justify-between gap-5 px-6 sm:flex-row">
          <div className="flex items-center gap-2.5">
            <MarkGlyph className="h-4 w-4 text-accent" />
            <span className="font-serif text-[14px] font-semibold tracking-[0.1em]">
              SANKHYA
            </span>
            <span className="ml-1 font-mono text-[11px] text-ink-3">SIH26101</span>
          </div>
          <p className="text-center font-mono text-[11px] leading-relaxed text-ink-3 sm:text-right">
            Workforce intelligence for India&rsquo;s Official Statistical System.
            <br className="hidden sm:block" /> A prototype built for MoSPI, Data
            Informatics &amp; Innovation Division.
          </p>
        </div>
      </footer>
    </div>
  );
}
