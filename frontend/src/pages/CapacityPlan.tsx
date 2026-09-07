import { useEffect, useState } from "react";

import { api } from "../api";
import { PageHeader } from "../components/Layout";
import { Card, Empty, ErrorNote, Note, Spinner, StatTile } from "../components/ui";
import { usePageTitle } from "../hooks/usePageTitle";

/**
 * The two outputs no learning platform produces: a costed capacity-building
 * draft, and a measurement of whether the courses in the catalogue work.
 *
 * Both carry their caveats on the page rather than in a footnote. A computed
 * plan presented as finished, or a correlation presented as causation, is worse
 * than not producing one.
 */

interface PriorityArea {
  competency_code: string;
  competency_name: string;
  domain: string;
  priority: string;
  officers_short: number;
  officers_assessed: number;
  share_short: number;
  mean_gap: number;
  critical_for_roles: string[];
  top_divisions: { code: string; name: string; officers_short: number }[];
  recommended_courses: { id: number; title: string; provider: string; duration_hours: number }[];
  estimated_officer_hours: number;
}

interface Acbp {
  financial_year: string;
  status: string;
  ministry: string;
  officers_covered: number;
  priority_areas: PriorityArea[];
  totals: {
    priority_areas: number;
    priority_1: number;
    estimated_officer_hours: number;
    estimated_officer_days: number;
  };
  basis: string;
  caveat: string;
}

interface CourseEfficacy {
  course_id: number;
  title: string;
  provider: string | null;
  competency_name: string | null;
  completions: number;
  measured: number;
  median_lift: number | null;
  improved: number;
  verdict: string;
  note: string;
}

interface Efficacy {
  window_days: number;
  courses: CourseEfficacy[];
  summary: { total: number; measurable: number; effective: number; needs_review: number };
  method: string;
  caveat: string;
}

const VERDICT_STYLE: Record<string, string> = {
  effective: "text-good",
  modest: "text-near",
  review: "text-critical",
  provisional: "text-ink-3",
  not_measurable: "text-ink-3",
};

const VERDICT_LABEL: Record<string, string> = {
  effective: "Effective",
  modest: "Modest",
  review: "Review",
  provisional: "Provisional",
  not_measurable: "No data",
};

const PRIORITY_STYLE: Record<string, string> = {
  "Priority 1": "bg-critical text-white",
  "Priority 2": "bg-warn text-white",
  "Priority 3": "bg-rule-strong text-ink",
};

export function CapacityPlan() {
  usePageTitle("title.capacityPlan");

  const [acbp, setAcbp] = useState<Acbp | null>(null);
  const [efficacy, setEfficacy] = useState<Efficacy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<Acbp>("/analytics/acbp"),
      api.get<Efficacy>("/analytics/course-efficacy"),
    ])
      .then(([a, e]) => {
        setAcbp(a);
        setEfficacy(e);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not build the plan."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner label="Computing the capacity building draft" />;
  if (error) return <ErrorNote message={error} />;
  if (!acbp) return <Empty>No data.</Empty>;

  return (
    <>
      <PageHeader
        title={`Annual Capacity Building Plan ${acbp.financial_year}`}
        subtitle={acbp.ministry}
        meta={`Draft · computed from ${acbp.officers_covered} officers' evidence`}
        action={
          <button
            onClick={() => window.print()}
            className="border border-rule-strong px-4 py-2 text-sm text-ink-2 transition-colors hover:border-accent hover:text-ink"
          >
            Print / save as PDF
          </button>
        }
      />

      <div className="mb-4">
        {/* The caveat already opens with "This is a computed draft for review,
            not an approved plan" — prefixing it repeated the sentence. */}
        <Note tone="brass">{acbp.caveat}</Note>
      </div>

      <div className="mb-4 grid gap-3.5 sm:grid-cols-4">
        <StatTile label="Priority areas" value={acbp.totals.priority_areas} />
        <StatTile
          label="At Priority 1"
          value={acbp.totals.priority_1}
          note="Widest shortfall on competencies critical to the role"
        />
        <StatTile
          label="Estimated effort"
          value={acbp.totals.estimated_officer_hours.toLocaleString()}
          unit="officer-hours"
          note={`about ${acbp.totals.estimated_officer_days.toLocaleString()} officer-days`}
        />
        <StatTile label="Officers covered" value={acbp.officers_covered} />
      </div>

      <Card
        title="Priority areas"
        hint={acbp.basis}
        className="mb-4"
      >
        <div className="divide-y divide-rule">
          {acbp.priority_areas.map((area) => (
            <div key={area.competency_code} className="py-4 first:pt-0 last:pb-0">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <span
                    className={`px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.05em] ${
                      PRIORITY_STYLE[area.priority] ?? PRIORITY_STYLE["Priority 3"]
                    }`}
                  >
                    {area.priority}
                  </span>
                  <span className="text-[14px] font-semibold">{area.competency_name}</span>
                </div>
                <span className="tabular font-mono text-[13px]">
                  {area.officers_short} of {area.officers_assessed} short{" "}
                  <span className="text-ink-3">({area.share_short}%)</span>
                </span>
              </div>

              <div className="mt-2 h-1.5 w-full bg-surface-2">
                <div
                  className={`h-1.5 ${
                    area.share_short >= 50 ? "bg-critical" : area.share_short >= 30 ? "bg-warn" : "bg-near"
                  }`}
                  style={{ width: `${Math.min(100, area.share_short)}%` }}
                />
              </div>

              <div className="mt-3 grid gap-3 text-[12.5px] sm:grid-cols-3">
                <div>
                  <div className="mb-1 text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-3">
                    Target group
                  </div>
                  <div className="text-ink-2">
                    {area.critical_for_roles.length > 0
                      ? `Critical for ${area.critical_for_roles.join(", ")}`
                      : "All grades"}
                  </div>
                  <div className="tabular mt-0.5 font-mono text-[11.5px] text-ink-3">
                    mean gap {area.mean_gap} levels
                  </div>
                </div>

                <div>
                  <div className="mb-1 text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-3">
                    Worst affected
                  </div>
                  <div className="text-ink-2">
                    {area.top_divisions.map((d) => `${d.code} (${d.officers_short})`).join(", ") || "—"}
                  </div>
                </div>

                <div>
                  <div className="mb-1 text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-3">
                    Recommended intervention
                  </div>
                  <div className="text-ink-2">
                    {area.recommended_courses[0]?.title ?? "No course in the catalogue"}
                  </div>
                  <div className="tabular mt-0.5 font-mono text-[11.5px] text-ink-3">
                    ~{area.estimated_officer_hours.toLocaleString()} officer-hours
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {efficacy && (
        <Card
          title="Course efficacy"
          hint={`Observed competency lift, ${efficacy.window_days} days either side of completion`}
        >
          <div className="mb-4 grid gap-3.5 sm:grid-cols-3">
            <StatTile
              label="Measurable"
              value={`${efficacy.summary.measurable} / ${efficacy.summary.total}`}
              note="Officers with assessment evidence on both sides"
            />
            <StatTile label="Showing clear lift" value={efficacy.summary.effective} />
            <StatTile
              label="Flagged for review"
              value={efficacy.summary.needs_review}
              note="No measurable improvement"
            />
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-[13px]">
              <caption className="sr-only">
                Course efficacy: observed competency lift, sample size and verdict
                for each course in the catalogue
              </caption>
              <thead>
                <tr className="border-b border-rule-strong text-[11px] uppercase tracking-[0.07em] text-ink-3">
                  <th scope="col" className="pb-2 pr-4 text-left font-semibold">Course</th>
                  <th scope="col" className="pb-2 pr-4 text-left font-semibold">Competency</th>
                  <th scope="col" className="pb-2 pr-4 text-right font-semibold">Sample</th>
                  <th scope="col" className="pb-2 pr-4 text-right font-semibold">Median lift</th>
                  <th scope="col" className="pb-2 text-left font-semibold">Verdict</th>
                </tr>
              </thead>
              <tbody>
                {efficacy.courses.map((c) => (
                  <tr key={c.course_id} className="border-b border-rule last:border-0">
                    <td className="py-2.5 pr-4">
                      <div className="font-semibold">{c.title}</div>
                      <div className="text-[11px] text-ink-3">{c.provider}</div>
                    </td>
                    <td className="py-2.5 pr-4 text-ink-2">{c.competency_name ?? "—"}</td>
                    <td className="tabular py-2.5 pr-4 text-right font-mono text-ink-3">
                      {c.measured ? `${c.improved}/${c.measured}` : "—"}
                    </td>
                    <td
                      className={`tabular py-2.5 pr-4 text-right font-mono font-semibold ${
                        c.median_lift === null
                          ? "text-ink-3"
                          : c.median_lift > 0.1
                            ? "text-good"
                            : c.median_lift < 0
                              ? "text-critical"
                              : "text-ink-2"
                      }`}
                    >
                      {c.median_lift === null
                        ? "—"
                        : `${c.median_lift > 0 ? "+" : ""}${c.median_lift.toFixed(2)}`}
                    </td>
                    <td className={`py-2.5 text-[12px] ${VERDICT_STYLE[c.verdict] ?? ""}`}>
                      {VERDICT_LABEL[c.verdict] ?? c.verdict}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 space-y-2 border-t border-rule pt-3 text-[11.5px] leading-relaxed text-ink-3">
            <p>
              <strong className="font-semibold text-ink-2">Method.</strong> {efficacy.method}
            </p>
            <p>
              <strong className="font-semibold text-ink-2">Caveat.</strong> {efficacy.caveat}
            </p>
          </div>
        </Card>
      )}
    </>
  );
}
