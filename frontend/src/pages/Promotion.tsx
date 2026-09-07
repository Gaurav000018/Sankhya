import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../api";
import { PageHeader } from "../components/Layout";
import { Card, Empty, ErrorNote, Note, Spinner, StatTile } from "../components/ui";
import type {
  Competency,
  FracRole,
  PromotionSimulation,
  ReadinessForecast,
  Recommendation,
} from "../types";
import { usePageTitle } from "../hooks/usePageTitle";

/**
 * "What if I did these courses?" and "when do I get there?".
 *
 * Both answers are projections, and the page says so in the places an officer
 * will actually read rather than once in small print at the bottom. The
 * simulator in particular is easy to misread as a promise: it is built on
 * course completion, which this system treats as the weakest kind of evidence,
 * so every projected figure is shown next to what actually confirms it.
 */

/** Where the readiness bar sits, projected against current. */
function ReadinessBar({ now, projected }: { now: number; projected: number }) {
  const gain = Math.max(0, projected - now);
  return (
    <div>
      <div className="flex h-6 w-full overflow-hidden border border-rule-strong bg-surface-2">
        <div
          className="bg-accent"
          style={{ width: `${Math.min(100, now)}%` }}
          role="presentation"
        />
        <div
          className="bg-near"
          style={{ width: `${Math.min(100 - Math.min(100, now), gain)}%` }}
          role="presentation"
        />
      </div>
      <div className="mt-1.5 flex justify-between text-[11px] text-ink-3">
        <span>
          <span className="inline-block h-2 w-2 bg-accent align-middle" /> Now {now.toFixed(1)}%
        </span>
        {gain > 0 && (
          <span>
            <span className="inline-block h-2 w-2 bg-near align-middle" /> Projected{" "}
            {projected.toFixed(1)}%
          </span>
        )}
      </div>
    </div>
  );
}

export function Promotion() {
  usePageTitle("title.promotion");

  const [roles, setRoles] = useState<FracRole[]>([]);
  const [targetRoleId, setTargetRoleId] = useState<number | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [competencyNames, setCompetencyNames] = useState<Record<number, string>>({});
  const [selected, setSelected] = useState<number[]>([]);
  const [simulation, setSimulation] = useState<PromotionSimulation | null>(null);
  const [forecast, setForecast] = useState<ReadinessForecast | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);

  const load = useCallback(async (roleId: number | null) => {
    const query = roleId ? `?target_role_id=${roleId}` : "";
    const [r, recs, fc, comps] = await Promise.all([
      api.get<FracRole[]>("/frac/roles"),
      api.get<Recommendation[]>(`/recommendations/me${query}`),
      api.get<ReadinessForecast>(`/promotion/forecast${query}`),
      api.get<Competency[]>("/frac/competencies"),
    ]);
    setRoles(r);
    setCompetencyNames(Object.fromEntries(comps.map((c) => [c.id, c.name])));
    setRecommendations(recs);
    setForecast(fc);
    // Start from what the recommender already suggested, so the page opens on a
    // real plan rather than an empty form the officer has to fill in first.
    setSelected(recs.slice(0, 3).map((rec) => rec.course.id));
    setSimulation(null);
  }, []);

  useEffect(() => {
    setLoading(true);
    load(targetRoleId)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Could not load your promotion outlook."),
      )
      .finally(() => setLoading(false));
  }, [load, targetRoleId]);

  const runSimulation = useCallback(async () => {
    setSimulating(true);
    setError(null);
    try {
      const result = await api.post<PromotionSimulation>("/promotion/simulate", {
        course_ids: selected,
        target_role_id: targetRoleId,
      });
      setSimulation(result);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not run that simulation.");
    } finally {
      setSimulating(false);
    }
  }, [selected, targetRoleId]);

  function toggle(courseId: number) {
    setSelected((current) =>
      current.includes(courseId)
        ? current.filter((id) => id !== courseId)
        : [...current, courseId],
    );
    setSimulation(null);
  }

  const selectedHours = useMemo(
    () =>
      recommendations
        .filter((r) => selected.includes(r.course.id))
        .reduce((sum, r) => sum + r.course.duration_hours, 0),
    [recommendations, selected],
  );

  if (loading) return <Spinner label="Working out where you stand" />;

  const targetRole = roles.find((r) => r.id === targetRoleId);

  return (
    <>
      <PageHeader
        title="Promotion outlook"
        subtitle={
          targetRole
            ? `Against ${targetRole.name}`
            : "Against the requirements of your current role"
        }
        meta="Projections, not commitments — what confirms a level is an assessment"
        action={
          <select
            aria-label="Simulate against a target role"
            value={targetRoleId ?? ""}
            onChange={(e) => setTargetRoleId(Number(e.target.value) || null)}
            className="border border-rule-strong bg-surface px-2.5 py-1.5 text-[12.5px] outline-none focus:border-accent"
          >
            <option value="">My current role</option>
            {roles.map((r) => (
              <option key={r.id} value={r.id}>
                Aiming for {r.name}
              </option>
            ))}
          </select>
        }
      />

      {error && <ErrorNote message={error} />}

      {forecast && (
        <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile
            label="Readiness now"
            value={forecast.readiness_now.toFixed(1)}
            unit="%"
            note="Weighted by how critical each competency is to the role"
          />
          <StatTile
            label="Movement"
            value={forecast.monthly_rate.toFixed(3)}
            unit="levels/mo"
            note={`Measured over the last ${forecast.window_days} days`}
          />
          <StatTile
            label="Gaps on track"
            value={`${forecast.gaps_on_track} of ${forecast.open_gaps}`}
            note="Accumulating enough evidence to close"
          />
          <StatTile
            label="Stalled"
            value={forecast.gaps_stalled}
            note="No date projected — nothing is moving here"
          />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_1.15fr]">
        <Card
          title="Build a plan"
          hint="Pick courses and see what they would do to your readiness"
        >
          {recommendations.length === 0 ? (
            <Empty>
              No courses are recommended for this role right now, so there is
              nothing to simulate.
            </Empty>
          ) : (
            <>
              <ul className="space-y-2">
                {recommendations.map((rec) => {
                  const checked = selected.includes(rec.course.id);
                  const ownCompetency =
                    rec.course.competency_id === null
                      ? null
                      : competencyNames[rec.course.competency_id];
                  // A course can be recommended against a gap it does not
                  // itself belong to. The simulator credits the course's own
                  // competency, so saying otherwise here would set up a
                  // contradiction two clicks later.
                  const substituted =
                    ownCompetency != null &&
                    rec.course.competency_id !== rec.competency_id;
                  return (
                    <li key={rec.id}>
                      <label
                        htmlFor={`course-${rec.course.id}`}
                        className={`flex cursor-pointer items-start gap-3 border px-3.5 py-3 ${
                          checked ? "border-accent bg-surface-2" : "border-rule bg-surface"
                        }`}
                      >
                        <input
                          id={`course-${rec.course.id}`}
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggle(rec.course.id)}
                          className="mt-0.5"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block text-[13px] font-medium">
                            {rec.course.title}
                          </span>
                          <span className="mt-0.5 block text-[11.5px] text-ink-3">
                            {ownCompetency ?? rec.competency_name} · L
                            {rec.course.level_from.toFixed(1)}–
                            {rec.course.level_to.toFixed(1)} · {rec.course.duration_hours}h
                          </span>
                          {substituted && (
                            <span className="mt-1 block text-[11px] leading-relaxed text-ink-2">
                              Suggested against your {rec.competency_name} gap, but it
                              builds {ownCompetency} — that is the competency a
                              simulation will move.
                            </span>
                          )}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>

              <div className="mt-4 flex items-center justify-between gap-3 border-t border-rule pt-4">
                <span className="text-[11.5px] text-ink-3">
                  {selected.length} selected · {selectedHours}h
                </span>
                <button
                  type="button"
                  onClick={runSimulation}
                  disabled={simulating || selected.length === 0}
                  className="border border-accent bg-accent px-4 py-2 text-[12.5px] font-medium text-surface disabled:border-rule disabled:bg-surface-2 disabled:text-ink-3"
                >
                  {simulating ? "Working it out…" : "Simulate"}
                </button>
              </div>
            </>
          )}
        </Card>

        <Card
          title="What that would do"
          hint={simulation ? simulation.assumptions : "Choose courses and simulate"}
        >
          {!simulation ? (
            <Empty>
              Nothing simulated yet. Pick courses on the left — the first three
              recommendations are already selected.
            </Empty>
          ) : simulation.error ? (
            <ErrorNote message={simulation.error} />
          ) : (
            <>
              <ReadinessBar
                now={simulation.readiness_now}
                projected={simulation.readiness_projected}
              />

              <div className="mt-4 flex items-baseline gap-6 border-b border-rule pb-4">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
                    Projected gain
                  </div>
                  <div className="tabular mt-1 font-mono text-[22px] leading-none">
                    +{simulation.gain.toFixed(1)}
                    <span className="ml-1 text-sm text-ink-3">points</span>
                  </div>
                </div>
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
                    Effort
                  </div>
                  <div className="tabular mt-1 font-mono text-[22px] leading-none">
                    {simulation.total_hours}
                    <span className="ml-1 text-sm text-ink-3">
                      h · ~{simulation.estimated_weeks}w
                    </span>
                  </div>
                </div>
              </div>

              <ol className="mt-4 space-y-3">
                {simulation.steps.map((step, index) => (
                  <li key={`${step.course_id}-${index}`} className="border-l-2 border-rule pl-3.5">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="text-[13px] font-medium">{step.title}</span>
                      <span
                        className={`tabular shrink-0 font-mono text-[12px] ${
                          step.readiness_gain > 0 ? "text-good" : "text-ink-3"
                        }`}
                      >
                        {step.readiness_gain > 0 ? "+" : ""}
                        {step.readiness_gain.toFixed(1)}pp
                      </span>
                    </div>
                    <div className="mt-0.5 text-[11.5px] text-ink-3">
                      {step.competency_name} · L{step.level_before.toFixed(2)} → L
                      {step.level_after.toFixed(2)} · {step.duration_hours}h
                    </div>
                    {step.note && (
                      <p className="mt-1.5 text-[11.5px] leading-relaxed text-ink-2">
                        {step.note}
                      </p>
                    )}
                  </li>
                ))}
              </ol>

              {simulation.excluded.length > 0 && (
                <div className="mt-4 border-t border-rule pt-4">
                  <h3 className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
                    Not counted toward this role
                  </h3>
                  <ul className="mt-2 space-y-1.5">
                    {simulation.excluded.map((item) => (
                      <li key={item.course_id} className="text-[11.5px] text-ink-2">
                        <span className="font-medium">{item.title ?? `Course ${item.course_id}`}</span>{" "}
                        — {item.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <Note tone="brass">{simulation.caveat}</Note>
            </>
          )}
        </Card>
      </div>

      {forecast && (
        <Card
          className="mt-6"
          title="When you would get there"
          hint={`At the rate evidence has actually accumulated over ${forecast.window_days} days`}
        >
          {forecast.projections.length === 0 ? (
            <Empty>
              No open gaps against this role, so there is nothing to project.
            </Empty>
          ) : (
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="border-b border-rule text-left text-[11px] uppercase tracking-[0.07em] text-ink-3">
                  <th scope="col" className="pb-2 font-semibold">Competency</th>
                  <th scope="col" className="pb-2 text-right font-semibold">Gap</th>
                  <th scope="col" className="pb-2 text-right font-semibold">Levels / month</th>
                  <th scope="col" className="pb-2 text-right font-semibold">Projected</th>
                </tr>
              </thead>
              <tbody>
                {forecast.projections.map((p) => (
                  <tr key={p.competency_name} className="border-b border-rule last:border-0">
                    <td className="py-2.5">
                      {p.competency_name}
                      {p.note && (
                        <span className="mt-0.5 block text-[11px] text-ink-3">{p.note}</span>
                      )}
                    </td>
                    <td className="tabular py-2.5 text-right font-mono">{p.gap.toFixed(2)}</td>
                    <td className="tabular py-2.5 text-right font-mono">
                      {p.monthly_rate.toFixed(3)}
                    </td>
                    <td
                      className={`py-2.5 text-right ${
                        p.projected_date ? "text-good" : "text-warn"
                      }`}
                    >
                      {p.projected_date ?? "No date"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <Note tone="brass">{forecast.caveat}</Note>
        </Card>
      )}
    </>
  );
}
