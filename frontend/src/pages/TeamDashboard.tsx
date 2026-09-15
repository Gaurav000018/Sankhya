import { useEffect, useState } from "react";

import { api } from "../api";
import { PageHeader } from "../components/Layout";
import { Card, Empty, ErrorNote, Spinner, StatTile } from "../components/ui";
import type { Heatmap, TeamResponse } from "../types";
import { usePageTitle } from "../hooks/usePageTitle";

/** Four bands, and the number is always printed in the cell — colour alone
 *  fails for a colour-blind reader and prints badly in a report. */
function band(atTarget: number) {
  if (atTarget >= 75) return { bg: "bg-good", fg: "text-white", label: "Met" };
  if (atTarget >= 50) return { bg: "bg-near", fg: "text-white", label: "Near target" };
  if (atTarget >= 25) return { bg: "bg-warn", fg: "text-white", label: "At risk" };
  return { bg: "bg-critical", fg: "text-white", label: "Critical" };
}

export function TeamDashboard() {
  usePageTitle("title.team");

  const [team, setTeam] = useState<TeamResponse | null>(null);
  const [heatmap, setHeatmap] = useState<Heatmap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.get<TeamResponse>("/team/officers"), api.get<Heatmap>("/analytics/heatmap")])
      .then(([t, h]) => {
        setTeam(t);
        setHeatmap(h);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the team view."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner label="Loading team readiness" />;
  if (error) return <ErrorNote message={error} />;
  if (!team) return <Empty>No officers found.</Empty>;

  const cellFor = (division: string, competency: string) =>
    heatmap?.cells.find((c) => c.division === division && c.competency === competency);

  return (
    <>
      <PageHeader
        title="Team readiness"
        subtitle={`Scope: ${team.scope}`}
        meta="Lowest readiness first — this list exists to find who needs attention"
      />

      <div className="mb-4 grid gap-3.5 sm:grid-cols-3">
        <StatTile label="Officers" value={team.summary.officers} />
        <StatTile
          label="With critical gaps"
          value={team.summary.with_critical_gaps}
          note="At least one competency two or more levels below requirement"
        />
        <StatTile label="Mean readiness" value={team.summary.mean_readiness} unit="%" />
      </div>

      <Card
        title="Officers"
        hint="Readiness is measured against the role each officer actually holds"
        className="mb-4"
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-[13px]">
            <thead>
              <tr className="border-b border-rule-strong text-[11px] uppercase tracking-[0.07em] text-ink-3">
                <th scope="col" className="pb-2 pr-4 text-left font-semibold">Officer</th>
                <th scope="col" className="pb-2 pr-4 text-left font-semibold">Role</th>
                <th scope="col" className="pb-2 pr-4 text-right font-semibold">Readiness</th>
                <th scope="col" className="pb-2 pr-4 text-left font-semibold">Widest gap</th>
                <th scope="col" className="pb-2 pr-4 text-right font-semibold">Critical</th>
                <th scope="col" className="pb-2 text-right font-semibold">Evidence</th>
              </tr>
            </thead>
            <tbody>
              {team.officers.slice(0, 30).map((o) => (
                <tr key={o.user_id} className="border-b border-rule last:border-0">
                  <td className="py-2.5 pr-4">
                    <div className="font-semibold">{o.full_name}</div>
                    {!o.fluency_scoring_enabled && (
                      <div className="mt-0.5 text-[11px] text-ink-3">
                        Fluency scoring off (accommodation)
                      </div>
                    )}
                  </td>
                  <td className="py-2.5 pr-4 text-ink-2">{o.role_name ?? "—"}</td>
                  <td className="tabular py-2.5 pr-4 text-right font-mono font-semibold">
                    {o.readiness}%
                  </td>
                  <td className="py-2.5 pr-4 text-ink-2">
                    {o.widest_gap_competency ? (
                      <>
                        <span className="truncate">{o.widest_gap_competency}</span>
                        <span className="tabular ml-2 font-mono text-ink-3">
                          +{o.widest_gap.toFixed(2)}
                        </span>
                      </>
                    ) : (
                      <span className="text-good">All requirements met</span>
                    )}
                  </td>
                  <td
                    className={`tabular py-2.5 pr-4 text-right font-mono ${
                      o.critical_gaps > 0 ? "font-semibold text-critical" : "text-ink-3"
                    }`}
                  >
                    {o.critical_gaps || "—"}
                  </td>
                  <td className="tabular py-2.5 text-right font-mono text-ink-3">
                    {o.evidence_count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {heatmap && heatmap.divisions.length > 0 && (
        <Card
          title="Division × competency readiness"
          hint="Share of officers meeting their own role's requirement. The figure is printed in every cell, so colour is never the only channel."
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] border-collapse text-[11.5px]">
              <caption className="sr-only">
                Percentage of officers meeting their role&rsquo;s requirement, by
                division and competency
              </caption>
              <thead>
                <tr>
                  <th
                    scope="col"
                    className="sticky left-0 z-10 bg-surface pb-2 pr-3 text-left text-[11px] uppercase tracking-[0.07em] text-ink-3"
                  >
                    Division
                  </th>
                  {heatmap.competencies.map((c) => (
                    <th
                      key={c.code}
                      scope="col"
                      title={c.name}
                      className="pb-2 text-center font-mono text-[10px] font-medium text-ink-3"
                    >
                      {c.code.replace(/^(STAT|TECH|DG|BEH)-/, "")}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {heatmap.divisions.map((d) => (
                  <tr key={d.code}>
                    <th
                      scope="row"
                      title={d.name}
                      className="sticky left-0 z-10 bg-surface py-1 pr-3 text-left font-mono text-[11px] font-medium"
                    >
                      {d.code}
                    </th>
                    {heatmap.competencies.map((c) => {
                      const cell = cellFor(d.code, c.code);
                      if (!cell)
                        return (
                          <td key={c.code} className="p-0.5">
                            <div className="bg-surface-2 py-1.5 text-center text-ink-3">—</div>
                          </td>
                        );
                      const b = band(cell.at_target_pct);
                      return (
                        <td key={c.code} className="p-0.5">
                          <div
                            title={`${d.name} · ${c.name}\n${b.label}: ${cell.at_target_pct}% at target, mean L${cell.mean_level} (${cell.officers} officers)`}
                            className={`tabular ${b.bg} ${b.fg} py-1.5 text-center font-mono font-medium`}
                          >
                            {Math.round(cell.at_target_pct)}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-rule pt-3 text-[11.5px] text-ink-2">
            <span className="text-ink-3">% of officers at target</span>
            {[
              { label: "0–24", cls: "bg-critical" },
              { label: "25–49", cls: "bg-warn" },
              { label: "50–74", cls: "bg-near" },
              { label: "75–100", cls: "bg-good" },
            ].map((k) => (
              <span key={k.label} className="flex items-center gap-1.5">
                <span className={`inline-block h-3 w-5 ${k.cls}`} />
                {k.label}
              </span>
            ))}
          </div>
        </Card>
      )}
    </>
  );
}
