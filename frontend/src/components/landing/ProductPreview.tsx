import { useEffect, useState } from "react";

import { prefersReducedMotionNow, useCountUp } from "../../hooks/useReveal";

/**
 * The hero's product shot.
 *
 * Drawn rather than screenshotted. A screenshot goes stale the moment the
 * dashboard changes, renders soft on a high-DPI display, and cannot animate.
 * This is built from the same tokens as the real thing, so it stays honest
 * about the interface it is advertising: the numbers below are the seeded
 * demo officer's actual figures.
 *
 * `active` flips once the frame is in view: the radar draws itself, the bars
 * fill, the figures count. All of it is CSS transitions off a single boolean,
 * so nothing here runs a timer.
 */

const AXES = [
  "STAT-SAMP",
  "STAT-INDEX",
  "STAT-NAS",
  "DG-PRIV",
  "DG-QUAL",
  "TECH-ANL",
  "BEH-COMM",
  "BEH-LEAD",
];

/** Assessed against required, per axis, on the 0-5 FRAC scale. */
const ASSESSED = [4.25, 3.4, 3.1, 3.6, 3.18, 2.56, 3.9, 2.49];
const REQUIRED = [4.0, 3.8, 3.5, 3.9, 3.7, 3.5, 4.0, 4.53];

const GAPS = [
  { name: "Team Leadership", from: 2.49, to: 4.53, tone: "critical" },
  { name: "GIS & Spatial", from: 2.15, to: 4.0, tone: "warn" },
  { name: "Data Analytics", from: 2.56, to: 3.5, tone: "near" },
];

const R = 74;
const C = 100;

function polygon(values: number[]) {
  return values
    .map((v, i) => {
      const angle = (2 * Math.PI * i) / values.length - Math.PI / 2;
      const radius = (Math.min(5, Math.max(0, v)) / 5) * R;
      return `${(C + radius * Math.cos(angle)).toFixed(1)},${(C + radius * Math.sin(angle)).toFixed(1)}`;
    })
    .join(" ");
}

function Count({ value }: { value: number }) {
  const ref = useCountUp(value, { durationMs: 1100 });
  return <span ref={ref}>{value}</span>;
}

export function ProductPreview({ active }: { active: boolean }) {
  return (
    <div className="relative">
      {/* Tilted in 3D and steered by the pointer via --rx/--ry, which the hero
          sets on itself; CSS custom properties inherit, so the frame just
          reads them. */}
      <div className="parallax relative rounded-xl border border-rule bg-surface shadow-[0_40px_120px_-30px_rgb(0_0_0/0.9)] will-change-transform">
        {/* Window chrome */}
        <div className="flex items-center gap-2 border-b border-rule px-4 py-2.5">
          <span className="h-2.5 w-2.5 rounded-full bg-critical/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-warn/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-good/70" />
          <div className="ml-3 flex-1 rounded-md bg-surface-2 px-3 py-1 font-mono text-[10px] text-ink-3">
            sankhya.mospi.gov.in/dashboard
          </div>
        </div>

        <div className="p-4">
          {/* Identity row */}
          <div className="flex items-end justify-between gap-4">
            <div>
              <div className="font-serif text-[15px] font-medium">A. Venkatesan</div>
              <div className="mt-0.5 font-mono text-[9.5px] text-ink-3">
                DEPUTY DIRECTOR · 14.5 YRS · ESD
              </div>
            </div>
            <div className="rounded-full border border-accent/40 bg-tint-accent px-2.5 py-1 font-mono text-[9.5px] text-accent">
              <Count value={83} />% ROLE READY
            </div>
          </div>

          {/* Stat strip */}
          <div className="mt-3 grid grid-cols-4 gap-2">
            {[
              { v: 83, u: "%", l: "READINESS" },
              { v: 5, u: "/12", l: "AT TARGET" },
              { v: 45, u: "", l: "EVIDENCE" },
              { v: 1, u: "", l: "CRITICAL" },
            ].map((s) => (
              <div key={s.l} className="rounded-md border border-rule bg-surface-2 px-2.5 py-2">
                <div className="tabular font-mono text-[15px] font-medium leading-none">
                  <Count value={s.v} />
                  <span className="text-[10px] text-ink-3">{s.u}</span>
                </div>
                <div className="mt-1.5 font-mono text-[8px] tracking-[0.08em] text-ink-3">
                  {s.l}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-2.5 grid grid-cols-[190px_minmax(0,1fr)] gap-2.5">
            {/* Radar */}
            <div className="rounded-md border border-rule bg-surface-2 p-2">
              <div className="font-mono text-[8px] tracking-[0.08em] text-ink-3">
                COMPETENCY PROFILE
              </div>
              <svg viewBox="0 0 200 200" className="mt-1 w-full overflow-visible">
                {[1, 2, 3, 4, 5].map((ring) => (
                  <polygon
                    key={ring}
                    points={polygon(AXES.map(() => ring))}
                    fill="none"
                    stroke="var(--color-rule-strong)"
                    strokeOpacity={ring === 5 ? 0.55 : 0.25}
                    strokeWidth="1"
                  />
                ))}
                {AXES.map((axis, i) => {
                  const angle = (2 * Math.PI * i) / AXES.length - Math.PI / 2;
                  return (
                    <line
                      key={axis}
                      x1={C}
                      y1={C}
                      x2={C + R * Math.cos(angle)}
                      y2={C + R * Math.sin(angle)}
                      stroke="var(--color-rule-strong)"
                      strokeOpacity="0.25"
                    />
                  );
                })}
                {/* Requirement ring draws first, then the assessed shape traces
                    itself over it and fills. */}
                <polygon
                  points={polygon(REQUIRED)}
                  fill="none"
                  stroke="var(--color-brass)"
                  strokeWidth="1.5"
                  strokeDasharray="3 3"
                  style={{ opacity: active ? 0.8 : 0, transition: "opacity 0.8s ease 0.2s" }}
                />
                <polygon
                  points={polygon(ASSESSED)}
                  pathLength={1}
                  fill="var(--color-accent)"
                  stroke="var(--color-accent)"
                  strokeWidth="2"
                  style={{
                    strokeDasharray: 1,
                    strokeDashoffset: active ? 0 : 1,
                    fillOpacity: active ? 0.16 : 0,
                    transition:
                      "stroke-dashoffset 1.6s cubic-bezier(0.16,1,0.3,1) 0.3s, fill-opacity 0.9s ease 1.4s",
                    filter: "drop-shadow(0 0 6px rgb(56 239 141 / 0.55))",
                  }}
                />
                {ASSESSED.map((v, i) => {
                  const angle = (2 * Math.PI * i) / ASSESSED.length - Math.PI / 2;
                  const radius = (v / 5) * R;
                  const weakest = v === Math.min(...ASSESSED);
                  return (
                    <circle
                      key={AXES[i]}
                      cx={C + radius * Math.cos(angle)}
                      cy={C + radius * Math.sin(angle)}
                      r={weakest ? 4 : 2.6}
                      fill={weakest ? "var(--color-critical)" : "var(--color-accent)"}
                      style={{
                        opacity: active ? 1 : 0,
                        transition: `opacity 0.4s ease ${0.5 + i * 0.15}s`,
                      }}
                    />
                  );
                })}
              </svg>
            </div>

            {/* Gap list */}
            <div className="rounded-md border border-rule bg-surface-2 p-2.5">
              <div className="font-mono text-[8px] tracking-[0.08em] text-ink-3">
                RANKED GAPS
              </div>
              {/* Capped, because a progress bar stretched across 500px reads as
                  an empty rule rather than a measurement. */}
              <div className="mt-2 max-w-[340px] space-y-2.5">
                {GAPS.map((g, i) => {
                  const colour = {
                    critical: "bg-critical",
                    warn: "bg-warn",
                    near: "bg-near",
                  }[g.tone]!;
                  return (
                    <div key={g.name}>
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="truncate text-[10px] font-medium">{g.name}</span>
                        <span className="tabular shrink-0 font-mono text-[9.5px] text-ink-3">
                          {g.from.toFixed(2)} → {g.to.toFixed(2)}
                        </span>
                      </div>
                      <div className="relative mt-1.5 h-1 w-full rounded-full bg-ground">
                        <div
                          className={`absolute left-0 top-0 h-1 rounded-full ${colour}`}
                          style={{
                            width: active ? `${(g.from / 5) * 100}%` : "0%",
                            transition: `width 1.1s cubic-bezier(0.16,1,0.3,1) ${0.6 + i * 0.18}s`,
                          }}
                        />
                        <div
                          className="absolute top-[-2px] h-2 w-[2px] rounded bg-brass"
                          style={{ left: `${(g.to / 5) * 100}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* The recommendation, with its reason — the thing the product is
                  actually for. */}
              <div
                className="mt-3 rounded-md border border-accent/25 bg-tint-accent p-2"
                style={{
                  opacity: active ? 1 : 0,
                  transform: active ? "none" : "translateY(6px)",
                  transition: "opacity 0.6s ease 1.6s, transform 0.6s ease 1.6s",
                }}
              >
                <div className="font-mono text-[8px] tracking-[0.08em] text-accent">
                  RECOMMENDED NEXT
                </div>
                <div className="mt-1 text-[10px] font-medium leading-snug">
                  Leading a Division · NSSTA
                </div>
                <div className="mt-0.5 text-[9px] leading-snug text-ink-3">
                  Covers L3→L4.7, the band your widest gap sits in.
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Live-cursor flourish: a caret blinking in the corner of the frame,
            so the shot reads as a running system rather than a still. */}
        <div className="absolute bottom-3 right-4 flex items-center gap-1.5">
          <span className="font-mono text-[9px] text-ink-3">derived</span>
          <span className="inline-block h-3 w-[6px] animate-blink bg-accent" />
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ ticker --- */

const FEED = [
  { competency: "GIS & Spatial Analysis", source: "simulation", level: 3.05 },
  { competency: "Communication & Statistical Reporting", source: "quiz", level: 3.35 },
  { competency: "Team Leadership & Coordination", source: "supervisor", level: 2.6 },
  { competency: "Data Governance & Quality Assurance", source: "diagnostic", level: 3.2 },
  { competency: "Estimation & Weighting", source: "interview", level: 4.2 },
  { competency: "Sampling & Survey Design", source: "certification", level: 4.31 },
  { competency: "Data Analytics & Machine Learning", source: "quiz", level: 2.72 },
];

interface Row {
  id: number;
  competency: string;
  source: string;
  level: number;
  at: number;
}

/**
 * The append-only record, appending.
 *
 * A small card that sits over the corner of the product shot and gains a new
 * evidence row every couple of seconds. It exists to make the one idea of the
 * platform — rows are added, never edited — visible without a paragraph. The
 * rows use the seeded competency names and real source types; the timings are
 * the only invented thing.
 */
export function EvidenceTicker({ active }: { active: boolean }) {
  // Newest first, so rows[0].id is always the high-water mark.
  const [rows, setRows] = useState<Row[]>(() =>
    FEED.slice(0, 3)
      .map((f, i) => ({ ...f, id: i, at: Date.now() - (3 - i) * 4000 }))
      .reverse(),
  );

  useEffect(() => {
    if (!active || prefersReducedMotionNow()) return;
    const timer = window.setInterval(() => {
      // The id comes from the previous state, not from a counter in this
      // closure: StrictMode replays updaters and HMR re-runs effects, and a
      // counter in either case hands out the same id twice — which React
      // reports as duplicate keys.
      setRows((prev) => {
        const id = (prev[0]?.id ?? -1) + 1;
        const item = FEED[id % FEED.length];
        return [{ ...item, id, at: Date.now() }, ...prev].slice(0, 3);
      });
    }, 2600);
    return () => window.clearInterval(timer);
  }, [active]);

  const ago = (at: number) => {
    const s = Math.round((Date.now() - at) / 1000);
    return s < 2 ? "just now" : `${s}s ago`;
  };

  return (
    <div className="w-[300px] rounded-lg border border-rule bg-surface/95 p-3 shadow-[0_24px_60px_-20px_rgb(0_0_0/0.9)] backdrop-blur">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[9.5px] uppercase tracking-[0.14em] text-ink-3">
          evidence stream
        </span>
        <span className="flex items-center gap-1.5 font-mono text-[9.5px] text-accent">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-70" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
          </span>
          append-only
        </span>
      </div>
      <ul className="mt-2.5 space-y-1.5">
        {rows.map((r, i) => (
          <li
            key={r.id}
            className={`${i === 0 ? "ticker-row" : ""} flex items-center gap-2.5 rounded-md border border-rule bg-surface-2 px-2.5 py-1.5`}
            style={{ opacity: 1 - i * 0.28 }}
          >
            <span className="tabular shrink-0 font-mono text-[11px] font-medium text-accent">
              L{r.level.toFixed(2)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[11px]">{r.competency}</span>
              <span className="block font-mono text-[9px] text-ink-3">{r.source}</span>
            </span>
            <span className="shrink-0 font-mono text-[9px] text-ink-3">{ago(r.at)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------ evidence loop --- */

/**
 * The evidence loop, drawn as the architecture diagram it is.
 *
 * This is the one idea the whole platform rests on, so it gets a real diagram
 * rather than four icons in a row: signals flow in, become append-only
 * evidence, derive a profile, rank gaps, produce a path — and completing that
 * path emits new evidence, closing the circuit. Three packets travel the
 * circuit continuously; they pass *under* the node boxes, so they read as
 * entering and leaving each stage.
 */
export function EvidenceLoop() {
  const sources = [
    { label: "Diagnostic", weight: "0.85" },
    { label: "Adaptive quiz", weight: "0.90" },
    { label: "AI interview", weight: "0.80" },
    { label: "Simulation", weight: "0.95" },
    { label: "Supervisor", weight: "0.70" },
    { label: "Self-rating", weight: "0.30" },
  ];

  const circuit =
    "M145,100 H567 V196 Q567,208 555,208 H84 Q72,208 72,196 V100 H145";

  return (
    <div className="rounded-xl border border-rule bg-surface p-5 sm:p-7">
      <div className="grid items-center gap-6 lg:grid-cols-[190px_minmax(0,1fr)]">
        {/* Inputs, each labelled with the weight it carries. Showing the weights
            is the point: self-rating is in the list, and it counts for least. */}
        <ul className="space-y-1.5">
          {sources.map((s, i) => (
            <li
              key={s.label}
              className="flex items-center justify-between gap-3 rounded-md border border-rule bg-surface-2 px-3 py-2 text-[12px]"
            >
              <span className="flex items-center gap-2">
                <span
                  className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent"
                  style={{ ["--d" as string]: `${i * 400}ms` }}
                />
                <span className={s.label === "Self-rating" ? "text-ink-3" : "text-ink"}>
                  {s.label}
                </span>
              </span>
              <span className="tabular font-mono text-[10px] text-ink-3">×{s.weight}</span>
            </li>
          ))}
        </ul>

        {/* The circuit */}
        <div className="relative">
          <svg
            viewBox="0 0 640 250"
            className="w-full overflow-visible"
            role="img"
            aria-label="Evidence flows into an append-only record, which derives a competency profile, which ranks gaps, which produces a learning path; completing that path emits new evidence."
          >
            <defs>
              <marker id="ar" markerWidth="9" markerHeight="9" refX="7" refY="3.2" orient="auto">
                <path d="M0,0 L7,3.2 L0,6.4 z" fill="var(--color-rule-strong)" />
              </marker>
              <marker id="ar-accent" markerWidth="9" markerHeight="9" refX="7" refY="3.2" orient="auto">
                <path d="M0,0 L7,3.2 L0,6.4 z" fill="var(--color-accent)" />
              </marker>
              <path id="circuit" d={circuit} />
            </defs>

            {/* The return edge. Dashed and animated so the loop is legible as a
                loop even in a still screenshot. */}
            <path
              d="M567 128 L567 196 Q567 208 555 208 L84 208 Q72 208 72 196 L72 136"
              fill="none"
              stroke="var(--color-accent)"
              strokeWidth="1.5"
              strokeDasharray="5 5"
              markerEnd="url(#ar-accent)"
              opacity="0.85"
            >
              <animate
                attributeName="stroke-dashoffset"
                from="200"
                to="0"
                dur="5s"
                repeatCount="indefinite"
              />
            </path>

            {[145, 310, 475].map((x) => (
              <line
                key={x}
                x1={x + 4}
                y1="100"
                x2={x + 16}
                y2="100"
                stroke="var(--color-rule-strong)"
                strokeWidth="1.5"
                markerEnd="url(#ar)"
              />
            ))}

            {/* Packets. Drawn before the nodes so the boxes occlude them. */}
            {[0, 2, 4].map((begin) => (
              <circle key={begin} r="3.2" fill="var(--color-accent)" style={{ filter: "drop-shadow(0 0 4px var(--color-accent))" }}>
                <animateMotion dur="6s" begin={`${begin}s`} repeatCount="indefinite">
                  <mpath href="#circuit" />
                </animateMotion>
              </circle>
            ))}

            {[
              { x: 0, label: "evidence", sub: "append-only", accent: true },
              { x: 165, label: "profile", sub: "derived" },
              { x: 330, label: "gaps", sub: "ranked" },
              { x: 495, label: "path", sub: "iGOT courses" },
            ].map((node) => (
              <g key={node.label}>
                <rect
                  x={node.x}
                  y="72"
                  width="145"
                  height="56"
                  rx="7"
                  fill="var(--color-surface-2)"
                  stroke={node.accent ? "var(--color-accent)" : "var(--color-rule-strong)"}
                  strokeWidth={node.accent ? 1.5 : 1}
                />
                <text
                  x={node.x + 72}
                  y="96"
                  textAnchor="middle"
                  fontSize="14"
                  fontFamily="var(--font-mono)"
                  fill={node.accent ? "var(--color-accent)" : "var(--color-ink)"}
                >
                  {node.label}
                </text>
                <text
                  x={node.x + 72}
                  y="113"
                  textAnchor="middle"
                  fontSize="10.5"
                  fill="var(--color-ink-3)"
                >
                  {node.sub}
                </text>
              </g>
            ))}

            <text
              x="320"
              y="230"
              textAnchor="middle"
              fontSize="11"
              fill="var(--color-accent)"
              fontFamily="var(--font-mono)"
            >
              learning completed → new evidence
            </text>

            <text x="0" y="30" fontSize="11.5" fill="var(--color-ink-3)">
              Nothing writes a competency score directly.
            </text>
            <text x="0" y="48" fontSize="11.5" fill="var(--color-ink-3)">
              Every level traces back to the artefact that produced it.
            </text>
          </svg>
        </div>
      </div>
    </div>
  );
}
