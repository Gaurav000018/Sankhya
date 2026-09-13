import { useEffect, useRef, useState } from "react";

/**
 * Role readiness as a ring.
 *
 * A single percentage is the one number an officer looks for first, so it gets
 * the largest, quietest treatment on the page. The ring is a second channel for
 * the same value rather than the only one — the figure is always printed in the
 * middle, and the accessible name carries it too.
 *
 * The arc sweeps from zero on mount. `pathLength="100"` normalises the geometry
 * so the dash maths is in percent and does not change if the radius does.
 */
export function ReadinessRing({
  value,
  label,
  size = 132,
  tone = "accent",
}: {
  value: number;
  label: string;
  size?: number;
  tone?: "accent" | "warn" | "critical";
}) {
  const [shown, setShown] = useState(0);
  const done = useRef(false);

  useEffect(() => {
    const target = Math.max(0, Math.min(100, value));
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduced || done.current) {
      setShown(target);
      done.current = true;
      return;
    }
    done.current = true;
    const start = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / 1100);
      setShown(target * (1 - Math.pow(1 - p, 4)));
      if (p < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [value]);

  const stroke = {
    accent: "var(--color-accent)",
    warn: "var(--color-warn)",
    critical: "var(--color-critical)",
  }[tone];

  return (
    <div
      className="relative shrink-0"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${label}: ${Math.round(value)} percent`}
    >
      <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
        <circle
          cx="50"
          cy="50"
          r="43"
          fill="none"
          stroke="var(--color-surface-2)"
          strokeWidth="7"
        />
        <circle
          cx="50"
          cy="50"
          r="43"
          fill="none"
          stroke={stroke}
          strokeWidth="7"
          strokeLinecap="round"
          pathLength="100"
          strokeDasharray={`${shown} 100`}
          style={{ filter: `drop-shadow(0 0 5px ${stroke})` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="tabular font-mono text-[26px] font-medium leading-none">
          {Math.round(shown)}
          <span className="text-[15px] text-ink-3">%</span>
        </span>
        <span className="mt-1.5 max-w-[86px] text-center text-[9.5px] font-medium uppercase leading-tight tracking-[0.08em] text-ink-3">
          {label}
        </span>
      </div>
    </div>
  );
}
