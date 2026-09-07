import { useT } from "../i18n";
import type { CompetencyLevel, Gap } from "../types";

/**
 * Competency radar: assessed level against role requirement.
 *
 * Axes are drawn for every competency in the framework, including ones with no
 * evidence — a chart that silently drops axes misrepresents coverage. Those
 * points are hollow, so "we have not measured this" is visibly different from
 * "this scored low".
 */

const SIZE = 300;
const CENTRE = SIZE / 2;
const MAX_RADIUS = 108;
const LEVELS = 5;

interface Props {
  competencies: CompetencyLevel[];
  gaps: Gap[];
}

function point(index: number, count: number, level: number) {
  const angle = (2 * Math.PI * index) / count - Math.PI / 2;
  const radius = (Math.max(0, Math.min(LEVELS, level)) / LEVELS) * MAX_RADIUS;
  return {
    x: CENTRE + radius * Math.cos(angle),
    y: CENTRE + radius * Math.sin(angle),
    angle,
  };
}

export function CompetencyRadar({ competencies, gaps }: Props) {
  const t = useT();
  if (competencies.length < 3) return null;

  const required = new Map(gaps.map((g) => [g.competency_id, g.required_level]));
  const count = competencies.length;

  const assessedPath = competencies
    .map((c, i) => {
      const p = point(i, count, c.level);
      return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
    })
    .join(" ");

  const requiredPath = competencies
    .map((c, i) => {
      const p = point(i, count, required.get(c.competency_id) ?? 0);
      return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
    })
    .join(" ");

  const weakest = gaps.find((g) => g.status === "critical")?.competency_id;

  return (
    <div>
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="mx-auto block h-auto w-full max-w-[340px] overflow-visible"
        role="img"
        aria-label="Competency profile: assessed level against role requirement"
      >
        {[1, 2, 3, 4, 5].map((ring) => (
          <polygon
            key={ring}
            points={competencies
              .map((_, i) => {
                const p = point(i, count, ring);
                return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
              })
              .join(" ")}
            fill="none"
            stroke={ring === LEVELS ? "var(--color-rule-strong)" : "var(--color-rule)"}
            strokeWidth="1"
          />
        ))}

        {competencies.map((c, i) => {
          const p = point(i, count, LEVELS);
          return (
            <line
              key={c.competency_id}
              x1={CENTRE}
              y1={CENTRE}
              x2={p.x}
              y2={p.y}
              stroke="var(--color-rule)"
              strokeWidth="1"
            />
          );
        })}

        <polygon
          points={requiredPath}
          fill="none"
          stroke="var(--color-brass)"
          strokeWidth="1.5"
          strokeDasharray="4 3"
        />
        <polygon
          points={assessedPath}
          fill="var(--color-accent)"
          fillOpacity="0.14"
          stroke="var(--color-accent)"
          strokeWidth="2"
        />

        {competencies.map((c, i) => {
          const p = point(i, count, c.level);
          const isWeakest = c.competency_id === weakest;
          return (
            <circle
              key={c.competency_id}
              cx={p.x}
              cy={p.y}
              r={isWeakest ? 4 : 3}
              fill={
                !c.is_confident
                  ? "var(--color-surface)"
                  : isWeakest
                    ? "var(--color-critical)"
                    : "var(--color-accent)"
              }
              stroke={c.is_confident ? "none" : "var(--color-ink-3)"}
              strokeWidth="1.5"
            >
              <title>
                {c.competency_name}: L{c.level}
                {c.is_confident ? "" : " (not enough evidence to be confident)"}
              </title>
            </circle>
          );
        })}

        {competencies.map((c, i) => {
          const p = point(i, count, LEVELS + 0.62);
          const anchor =
            Math.abs(p.x - CENTRE) < 12 ? "middle" : p.x > CENTRE ? "start" : "end";
          return (
            <text
              key={c.competency_id}
              x={p.x}
              y={p.y}
              textAnchor={anchor}
              dominantBaseline="middle"
              fontSize="9.5"
              fill={
                c.competency_id === weakest ? "var(--color-critical)" : "var(--color-ink-2)"
              }
              fontWeight={c.competency_id === weakest ? 600 : 400}
            >
              {c.competency_code}
            </text>
          );
        })}
      </svg>

      <div className="mt-3 flex flex-wrap justify-center gap-x-5 gap-y-1 border-t border-rule pt-3 text-[11.5px] text-ink-2">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-[3px] w-3.5 bg-accent" />
          {t("common.assessed")}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0 w-3.5 border-t-2 border-dashed border-brass" />
          {t("common.roleRequirement")}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full border border-ink-3 bg-surface" />
          {t("common.thinEvidence")}
        </span>
      </div>
    </div>
  );
}
