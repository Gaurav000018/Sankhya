import { useT } from "../i18n";

/**
 * Ability and item difficulty, drawn on one axis.
 *
 * This is the whole idea of item response theory made visible, and it is the
 * only honest way to explain to an officer why the questions keep changing:
 * their ability and each question's difficulty are points on the same scale,
 * and the next question is always the one nearest the current estimate.
 *
 * Two things are deliberate.
 *
 * **The interval is drawn, not the point.** A twelve-item multiple-choice test
 * supports an estimate of about ±0.65 of a FRAC level at 95%. Drawing a single
 * marker would assert a precision the assessment does not have, and the band
 * narrowing question by question is the clearest evidence that the test is
 * working.
 *
 * **Every channel is doubled.** The band carries a numeric range beneath it and
 * the difficulty marker carries its own label, so nothing here depends on
 * colour or position alone.
 */

const MIN_LEVEL = 1;
const MAX_LEVEL = 5;

/** Position on the L1–L5 axis as a percentage, clamped to the track. */
function at(level: number): number {
  const clamped = Math.max(MIN_LEVEL, Math.min(MAX_LEVEL, level));
  return ((clamped - MIN_LEVEL) / (MAX_LEVEL - MIN_LEVEL)) * 100;
}

export interface Ability {
  theta: number;
  se: number;
  level: number;
  level_low: number;
  level_high: number;
  reliability: number;
}

export function AbilityScale({
  ability,
  itemLevel,
  requiredLevel,
  label = "Where the estimate sits",
}: {
  ability: Ability;
  /** The difficulty of the question currently on screen, if one is open. */
  itemLevel?: number | null;
  /** The level this competency requires for the officer's role. */
  requiredLevel?: number | null;
  label?: string;
}) {
  const low = at(ability.level_low);
  const high = at(ability.level_high);

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <span className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
          {label}
        </span>
        <span className="tabular font-mono text-[12px] text-ink-2">
          L{ability.level.toFixed(2)}{" "}
          <span className="text-ink-3">
            (L{ability.level_low.toFixed(1)}–L{ability.level_high.toFixed(1)})
          </span>
        </span>
      </div>

      <div
        role="img"
        aria-label={
          `Estimated level ${ability.level.toFixed(2)} of 5, ` +
          `95% interval ${ability.level_low.toFixed(1)} to ${ability.level_high.toFixed(1)}` +
          (itemLevel != null ? `. Current question difficulty ${itemLevel.toFixed(1)}` : "")
        }
        className="relative h-9"
      >
        {/* The track */}
        <div className="absolute inset-x-0 top-4 h-1.5 bg-surface-2" />

        {/* The 95% interval */}
        <div
          className="absolute top-4 h-1.5 bg-accent-dim transition-all duration-500"
          style={{ left: `${low}%`, width: `${Math.max(high - low, 0.8)}%` }}
        />

        {/* The point estimate */}
        <div
          className="absolute top-[11px] h-[14px] w-[2.5px] bg-accent transition-all duration-500"
          style={{ left: `calc(${at(ability.level)}% - 1.25px)` }}
        />

        {/* What the role requires, if known — brass marks a requirement
            everywhere else in the product, so it does here too. */}
        {requiredLevel != null && (
          <div
            className="absolute top-[13px] h-2.5 w-0.5 bg-brass"
            style={{ left: `calc(${at(requiredLevel)}% - 1px)` }}
            title={`Required: L${requiredLevel}`}
          />
        )}

        {/* The question on screen. Above the track rather than on it, so it
            never hides the estimate it is being compared against. */}
        {itemLevel != null && (
          <div
            className="absolute top-0 transition-all duration-500"
            style={{ left: `${at(itemLevel)}%` }}
          >
            <div className="-translate-x-1/2">
              <div className="tabular whitespace-nowrap font-mono text-[10px] leading-none text-brass">
                L{itemLevel.toFixed(1)}
              </div>
              <div className="mx-auto mt-0.5 h-2 w-px bg-brass" />
            </div>
          </div>
        )}
      </div>

      <div className="tabular mt-1 flex justify-between font-mono text-[10px] text-ink-3">
        {[1, 2, 3, 4, 5].map((level) => (
          <span key={level}>L{level}</span>
        ))}
      </div>
    </div>
  );
}

export interface TraceStep {
  sequence: number;
  difficulty_level: number | null;
  is_correct: boolean;
  skipped: boolean;
  level_after: number | null;
  se_after: number | null;
  information: number | null;
  asked_because: string | null;
}

/**
 * The path the test walked: difficulty chased ability, and the band closed.
 *
 * The shape is the argument. A reader who sees question difficulty tracking the
 * estimate understands adaptive testing without reading a word of the
 * explanation beside it, and a reader who sees the band close understands why
 * the test stopped where it did.
 *
 * Half SVG and half positioned elements, for a reason worth stating: the band
 * and the line are drawn in a stretched viewBox, which is right for them —
 * horizontal scale is arbitrary and their shape survives it. Per-question
 * markers do not survive it. A circle under a ten-to-one non-uniform scale is a
 * smear, so those are laid over the chart as positioned elements where a round
 * dot stays round at any card width.
 */
export function AbilityTrace({ steps }: { steps: TraceStep[] }) {
  const t = useT();
  if (steps.length === 0) return null;

  const W = 100;
  const H = 46;
  const PAD_X = 3;

  const x = (i: number) =>
    PAD_X + (i / Math.max(steps.length - 1, 1)) * (W - 2 * PAD_X);
  // Inverted: L5 at the top, the way every other level display in the product
  // reads.
  const y = (level: number) =>
    H - ((Math.max(1, Math.min(5, level)) - 1) / 4) * H;

  const estimates = steps.filter((s) => s.level_after != null);
  const line = estimates
    .map((s, i) => `${i === 0 ? "M" : "L"}${x(s.sequence)},${y(s.level_after!)}`)
    .join(" ");

  // The uncertainty band, forward along the upper bound and back along the
  // lower one. Without it the estimate line reads as far more certain than it is.
  const band =
    estimates.length > 1
      ? estimates
          .map(
            (s, i) =>
              `${i === 0 ? "M" : "L"}${x(s.sequence)},${y(s.level_after! + 1.96 * (s.se_after ?? 0) * (2 / 3))}`,
          )
          .join(" ") +
        " " +
        estimates
          .slice()
          .reverse()
          .map(
            (s) =>
              `L${x(s.sequence)},${y(s.level_after! - 1.96 * (s.se_after ?? 0) * (2 / 3))}`,
          )
          .join(" ") +
        " Z"
      : "";

  const describe = (s: TraceStep) =>
    `Question ${s.sequence + 1}: difficulty L${s.difficulty_level?.toFixed(1)}, ` +
    `${s.skipped ? "skipped" : s.is_correct ? "correct" : "incorrect"}, ` +
    `estimate L${s.level_after?.toFixed(2)}`;

  return (
    <div className="flex gap-2">
      {/* Level labels live outside the SVG because the chart uses
          `preserveAspectRatio="none"` to stretch horizontally, which would
          squash any text drawn inside it. */}
      <div
        aria-hidden
        className="tabular flex h-40 shrink-0 flex-col justify-between font-mono text-[10px] text-ink-3"
      >
        {[5, 4, 3, 2, 1].map((level) => (
          <span key={level} className="leading-none">
            L{level}
          </span>
        ))}
      </div>

      <div className="min-w-0 flex-1">
        {/* The band and the line stretch with the container, which is what we
            want — their shape is the message and horizontal scale is arbitrary.
            The per-question markers do NOT: a circle under a non-uniform scale
            becomes a wide ellipse, and at a typical container width it stretched
            about ten to one, which read as a smear rather than a data point. So
            they are laid over the chart as positioned elements instead, where a
            round dot stays round however wide the card is. */}
        <div className="relative h-40">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            preserveAspectRatio="none"
            className="absolute inset-0 h-full w-full"
            aria-hidden
          >
            {[2, 3, 4].map((level) => (
              <line
                key={level}
                x1={0}
                x2={W}
                y1={y(level)}
                y2={y(level)}
                stroke="var(--color-rule)"
                strokeWidth={0.25}
              />
            ))}
            {band && <path d={band} fill="var(--color-accent-dim)" opacity={0.45} />}
            {line && (
              <path
                d={line}
                fill="none"
                stroke="var(--color-accent)"
                strokeWidth={0.8}
                vectorEffect="non-scaling-stroke"
              />
            )}
          </svg>

          <div
            role="img"
            aria-label={
              `Adaptive path over ${steps.length} questions. ` +
              steps.map(describe).join(". ")
            }
            className="absolute inset-0"
          >
            {steps.map((s) =>
              s.difficulty_level == null ? null : (
                <span
                  key={s.sequence}
                  title={describe(s)}
                  style={{
                    left: `${x(s.sequence)}%`,
                    top: `${(y(s.difficulty_level) / H) * 100}%`,
                  }}
                  className={`absolute -translate-x-1/2 -translate-y-1/2 leading-none ${
                    s.is_correct ? "text-good" : "text-critical"
                  }`}
                >
                  {/* Shape as well as colour: the two marks stay distinguishable
                      in greyscale and for a reader who cannot tell them apart. */}
                  {s.is_correct ? (
                    <span className="block h-[7px] w-[7px] rounded-full bg-good" />
                  ) : (
                    <span className="block font-mono text-[12px] font-semibold">&times;</span>
                  )}
                </span>
              ),
            )}
          </div>
        </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[11px] text-ink-3">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-good" />
          {t("quiz.legend.correct")}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="font-mono text-critical">&times;</span>
          {t("quiz.legend.incorrect")}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-3 bg-accent" />
          {t("quiz.legend.estimate")}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-3 bg-accent-dim" />
          {t("quiz.legend.interval")}
        </span>
        <span className="text-ink-3">
          Horizontal axis: question order, 1 to {steps.length}.
        </span>
      </div>
      </div>
    </div>
  );
}
