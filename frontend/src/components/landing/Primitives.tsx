import type { MouseEvent, ReactNode } from "react";
import { Link } from "react-router-dom";

import { useCountUp } from "../../hooks/useReveal";

/* Landing-page primitives. Kept apart from `components/ui.tsx` on purpose: the
   product surface optimises for density and legibility over long sessions, the
   landing page optimises for a first ten seconds. Sharing components between
   the two makes both worse. */

/** Wraps a section so its children reveal on scroll, with an index-based
 *  stagger so a grid resolves in reading order. */
export function Reveal({
  children,
  delay = 0,
  className = "",
  as: Tag = "div",
  onMouseMove,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "li" | "section" | "header" | "p" | "h2";
  onMouseMove?: (e: MouseEvent<HTMLElement>) => void;
}) {
  return (
    <Tag className={`reveal ${className}`} data-reveal-delay={delay} onMouseMove={onMouseMove}>
      {children}
    </Tag>
  );
}

/** Splits a line into words that blur in one after another. `start` is the
 *  delay of the first word so consecutive lines can chain. */
export function SplitWords({
  text,
  start = 0,
  step = 70,
  className = "",
}: {
  text: string;
  start?: number;
  step?: number;
  className?: string;
}) {
  return (
    <>
      {text.split(" ").map((word, i) => (
        <span
          key={`${word}-${i}`}
          className={`word inline-block ${className}`}
          style={{ ["--d" as string]: `${start + i * step}ms` }}
        >
          {word}
          {i < text.split(" ").length - 1 ? " " : ""}
        </span>
      ))}
    </>
  );
}

/** Sets the cursor position on a `.spotlight` card so its highlight follows
 *  the pointer. Attach to onMouseMove. */
export function trackSpotlight(e: MouseEvent<HTMLElement>) {
  const el = e.currentTarget;
  const r = el.getBoundingClientRect();
  el.style.setProperty("--mx", `${e.clientX - r.left}px`);
  el.style.setProperty("--my", `${e.clientY - r.top}px`);
}

/** Small uppercase label that opens a section. The rule beside it draws in
 *  with the section, which is what makes it read as a marker rather than a
 *  stray line of text. */
export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <span className="eyebrow-rule h-px w-8 bg-accent" />
      <span className="font-mono text-[11px] font-medium uppercase tracking-[0.22em] text-accent">
        {children}
      </span>
    </div>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  lede,
  align = "left",
}: {
  eyebrow: string;
  title: ReactNode;
  lede?: ReactNode;
  align?: "left" | "center";
}) {
  const centred = align === "center";
  return (
    <div className={`max-w-3xl ${centred ? "mx-auto text-center" : ""}`}>
      <Reveal className={centred ? "flex justify-center" : ""}>
        <Eyebrow>{eyebrow}</Eyebrow>
      </Reveal>
      <Reveal delay={80}>
        <h2 className="mt-5 font-serif text-[clamp(1.75rem,3.4vw,2.75rem)] font-normal leading-[1.15] tracking-[-0.02em]">
          {title}
        </h2>
      </Reveal>
      {lede && (
        <Reveal delay={140}>
          <p className="mt-4 text-[15px] leading-relaxed text-ink-2">{lede}</p>
        </Reveal>
      )}
    </div>
  );
}

/** A number that counts up when it scrolls into view. `value` is the real
 *  figure; `suffix` carries the unit so the digits stay monospaced alone. */
export function Metric({
  value,
  decimals = 0,
  prefix,
  suffix,
  label,
  note,
}: {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  label: string;
  note?: string;
}) {
  const ref = useCountUp(value, { decimals });
  return (
    <div className="border-t border-rule pt-5">
      <div className="tabular flex items-baseline font-mono text-[clamp(1.9rem,3.6vw,2.6rem)] font-medium leading-none">
        {prefix && <span className="text-ink-3">{prefix}</span>}
        <span ref={ref}>{value}</span>
        {suffix && <span className="ml-0.5 text-accent">{suffix}</span>}
      </div>
      <div className="mt-3 text-[13px] font-medium text-ink">{label}</div>
      {note && <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink-3">{note}</p>}
    </div>
  );
}

/** Pill button. `tone="solid"` is the single primary action per viewport.
 *  `to` is an in-app route (client-side navigation); `href` is for anchors. */
export function Pill({
  children,
  to,
  href,
  onClick,
  tone = "ghost",
  size = "md",
  className = "",
}: {
  children: ReactNode;
  to?: string;
  href?: string;
  onClick?: () => void;
  tone?: "solid" | "ghost" | "quiet";
  size?: "sm" | "md";
  className?: string;
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-full font-medium transition-all duration-200 whitespace-nowrap";
  const sizing = size === "sm" ? "px-4 py-2 text-[13px]" : "px-5 py-2.5 text-[14px]";
  const tones = {
    solid:
      "sheen bg-accent text-ground hover:brightness-110 hover:shadow-[0_0_28px_-4px_var(--color-accent)] active:brightness-95",
    ghost:
      "border border-rule-strong text-ink hover:border-accent hover:text-accent hover:bg-tint-accent",
    quiet: "text-ink-2 hover:text-ink",
  }[tone];

  const classes = `${base} ${sizing} ${tones} ${className}`;
  if (to) {
    return (
      <Link to={to} className={classes}>
        {children}
      </Link>
    );
  }
  if (href) {
    return (
      <a href={href} className={classes}>
        {children}
      </a>
    );
  }
  return (
    <button type="button" onClick={onClick} className={classes}>
      {children}
    </button>
  );
}

/** The soft coloured bloom behind hero and section anchors. Purely decorative,
 *  so it is hidden from assistive technology and sits behind everything. */
export function Glow({
  className = "",
  colour = "var(--color-accent)",
  opacity = 0.16,
}: {
  className?: string;
  colour?: string;
  opacity?: number;
}) {
  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute -z-10 rounded-full blur-[110px] animate-drift ${className}`}
      style={{ background: colour, opacity }}
    />
  );
}

/** Infinite horizontal scroll. The list is rendered twice and the track moves
 *  by exactly half its width, so the seam is invisible. Pauses on hover so
 *  anything in it can be read. */
export function Marquee({ items }: { items: string[] }) {
  const doubled = [...items, ...items];
  return (
    <div className="mask-x overflow-hidden">
      <div className="flex w-max animate-marquee gap-14 hover:[animation-play-state:paused]">
        {doubled.map((name, i) => (
          <span
            key={`${name}-${i}`}
            aria-hidden={i >= items.length}
            className="flex items-center gap-4 whitespace-nowrap font-serif text-[15px] tracking-[0.02em] text-ink-2"
          >
            <span className="h-1 w-1 rounded-full bg-accent/60" />
            {name}
          </span>
        ))}
      </div>
    </div>
  );
}
