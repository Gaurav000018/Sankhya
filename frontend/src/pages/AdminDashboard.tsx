import { useEffect, useState } from "react";

import { api } from "../api";
import { PageHeader } from "../components/Layout";
import { Card, Empty, ErrorNote, Note, Spinner, StatTile } from "../components/ui";
import type { AdminOverview } from "../types";
import { usePageTitle } from "../hooks/usePageTitle";

const DOMAIN_LABELS: Record<string, string> = {
  statistical: "Statistical",
  technical: "Technical",
  digital_governance: "Digital governance",
  behavioural: "Behavioural",
};

const SOURCE_LABELS: Record<string, string> = {
  simulation: "Simulation",
  quiz: "Quiz",
  diagnostic: "Diagnostic",
  interview: "AI interview",
  certification: "Certification",
  supervisor: "Supervisor rating",
  learning_activity: "Course completion",
  historical: "Service record",
  self: "Self-assessment",
};

/** Sources that show someone doing the work, rather than attending or claiming. */
const DEMONSTRATED = new Set(["simulation", "quiz", "diagnostic", "interview"]);

export function AdminDashboard() {
  usePageTitle("title.workforce");

  const [data, setData] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<AdminOverview>("/analytics/overview")
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load analytics."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner label="Aggregating the national picture" />;
  if (error) return <ErrorNote message={error} />;
  if (!data) return <Empty>No data.</Empty>;

  const maxEvidence = Math.max(...data.evidence_mix.map((e) => e.count), 1);
  const priorities = data.by_competency.slice(0, 5);

  return (
    <>
      <PageHeader
        title="Workforce intelligence"
        subtitle="Ministry of Statistics and Programme Implementation"
        meta="All figures derived from evidence records, not self-declaration"
      />

      <div className="mb-4 grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Officers" value={data.officers} note={`Across ${data.divisions} divisions`} />
        <StatTile label="Evidence records" value={data.evidence_records.toLocaleString()} />
        <StatTile
          label="Demonstrated evidence"
          value={data.demonstrated_evidence_pct}
          unit="%"
          note="From assessment or observed work, rather than attendance or self-rating"
        />
        <StatTile
          label="Weakest competency"
          value={priorities[0]?.code ?? "—"}
          note={`${priorities[0]?.at_target_pct ?? 0}% of officers at target`}
        />
      </div>

      <div className="mb-4 grid gap-3.5 lg:grid-cols-[minmax(0,1fr)_400px]">
        <Card
          title="Capacity building priorities"
          hint="Competencies ranked by the share of officers falling short of their own role's requirement"
        >
          <div className="divide-y divide-rule">
            {priorities.map((c) => (
              <div key={c.code} className="py-3 first:pt-0">
                <div className="flex items-baseline justify-between gap-3">
                  <div className="min-w-0">
                    <span className="text-[13.5px] font-semibold">{c.name}</span>
                    <span className="ml-2 text-[11px] uppercase tracking-[0.05em] text-ink-3">
                      {DOMAIN_LABELS[c.domain] ?? c.domain}
                    </span>
                  </div>
                  <span className="tabular shrink-0 font-mono text-[13px] font-semibold">
                    {c.at_target_pct}%
                  </span>
                </div>
                <div className="mt-2 h-1.5 w-full bg-surface-2">
                  <div
                    className={`h-1.5 ${
                      c.at_target_pct < 40 ? "bg-critical" : c.at_target_pct < 60 ? "bg-warn" : "bg-near"
                    }`}
                    style={{ width: `${c.at_target_pct}%` }}
                  />
                </div>
                <div className="tabular mt-1.5 flex gap-4 font-mono text-[11.5px] text-ink-3">
                  <span>mean L{c.mean_level}</span>
                  <span>required L{c.mean_required}</span>
                  <span>{c.officers_below_target} officers short</span>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4">
            <Note>
              <strong className="font-semibold text-ink">
                This is the input to the Annual Capacity Building Plan.
              </strong>{" "}
              Mission Karmayogi requires each ministry to publish an ACBP; these
              priorities are computed from {data.evidence_records.toLocaleString()} evidence
              records rather than assembled by hand. Draft generation is the next step.
            </Note>
          </div>
        </Card>

        <div className="grid gap-3.5">
          <Card
            title="Where our knowledge comes from"
            hint="A platform leaning on self-assessment is not measuring competency"
          >
            <div className="space-y-2">
              {data.evidence_mix.map((e) => (
                <div key={e.source} className="flex items-center gap-3">
                  <span className="w-[120px] shrink-0 text-[12.5px] text-ink-2">
                    {SOURCE_LABELS[e.source] ?? e.source}
                  </span>
                  <div className="h-3 flex-1 bg-surface-2">
                    <div
                      className={`h-3 ${DEMONSTRATED.has(e.source) ? "bg-accent" : "bg-rule-strong"}`}
                      style={{ width: `${(100 * e.count) / maxEvidence}%` }}
                    />
                  </div>
                  <span className="tabular w-12 shrink-0 text-right font-mono text-[11.5px] text-ink-3">
                    {e.count}
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-3 border-t border-rule pt-2.5 text-[11.5px] leading-relaxed text-ink-3">
              Shaded bars are demonstrated performance. Course completion and
              self-assessment carry the least weight in the derived level.
            </div>
          </Card>

          <Card title="Officers by role">
            <div className="space-y-1.5">
              {data.by_role.map((r) => (
                <div key={r.code} className="flex items-baseline justify-between gap-3 text-[13px]">
                  <span className="text-ink-2">{r.name}</span>
                  <span className="tabular font-mono font-semibold">{r.officers}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      <Card
        title="Division standing"
        hint="Share of officers meeting the requirements of the roles they hold"
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[600px] text-[13px]">
              <caption className="sr-only">
                Division standing: officers, mean assessed level, and the share
                meeting the requirements of the roles they hold
              </caption>
            <thead>
              <tr className="border-b border-rule-strong text-[11px] uppercase tracking-[0.07em] text-ink-3">
                <th scope="col" className="pb-2 pr-4 text-left font-semibold">Division</th>
                <th scope="col" className="pb-2 pr-4 text-left font-semibold">State</th>
                <th scope="col" className="pb-2 pr-4 text-right font-semibold">Officers</th>
                <th scope="col" className="pb-2 pr-4 text-right font-semibold">Mean level</th>
                <th scope="col" className="pb-2 text-left font-semibold">At target</th>
              </tr>
            </thead>
            <tbody>
              {data.by_division.map((d) => (
                <tr key={d.code} className="border-b border-rule last:border-0">
                  <td className="py-2.5 pr-4">
                    <span className="font-mono text-[11.5px] text-ink-3">{d.code}</span>
                    <span className="ml-2 font-semibold">{d.name}</span>
                  </td>
                  <td className="py-2.5 pr-4 text-ink-2">{d.state}</td>
                  <td className="tabular py-2.5 pr-4 text-right font-mono">{d.officers}</td>
                  <td className="tabular py-2.5 pr-4 text-right font-mono">L{d.mean_level}</td>
                  <td className="py-2.5">
                    <div className="flex items-center gap-2.5">
                      <div className="h-1.5 w-32 bg-surface-2">
                        <div
                          className={`h-1.5 ${
                            d.at_target_pct < 45 ? "bg-critical" : d.at_target_pct < 60 ? "bg-warn" : "bg-near"
                          }`}
                          style={{ width: `${d.at_target_pct}%` }}
                        />
                      </div>
                      <span className="tabular font-mono text-[12px] font-semibold">
                        {d.at_target_pct}%
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
