import { useCallback, useEffect, useState } from "react";

import { ApiError, api } from "../api";
import { PageHeader } from "../components/Layout";
import { Card, Empty, ErrorNote, Note, Spinner, StatTile } from "../components/ui";
import type { FracRole, Gap, LearningPath, Recommendation } from "../types";
import { usePageTitle } from "../hooks/usePageTitle";

/**
 * Recommendations and learning paths.
 *
 * The signal breakdown is shown, not hidden behind the score. A recommendation
 * an officer cannot interrogate is a search result with extra steps.
 */

const SIGNAL_LABELS: Record<string, string> = {
  relevance: "Addresses the competency",
  level_fit: "Matches your level band",
  urgency: "Gap width and criticality",
  peers: "Taken by officers in your role",
};

function SignalBars({ signals }: { signals: Recommendation["signals"] }) {
  return (
    <div className="space-y-1.5">
      {(["relevance", "level_fit", "urgency", "peers"] as const).map((key) => {
        const value = signals[key] ?? 0;
        return (
          <div key={key} className="flex items-center gap-2.5">
            <span className="w-[168px] shrink-0 text-[11.5px] text-ink-2">
              {SIGNAL_LABELS[key]}
            </span>
            <div className="h-1.5 flex-1 bg-surface-2">
              <div className="h-1.5 bg-accent" style={{ width: `${Math.min(100, value * 100)}%` }} />
            </div>
            <span className="tabular w-9 shrink-0 text-right font-mono text-[10.5px] text-ink-3">
              {value.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

const STATUS_STYLE: Record<string, string> = {
  available: "border-accent text-accent",
  locked: "border-rule text-ink-3",
  in_progress: "border-accent text-accent",
  completed: "border-good text-good",
};

export function Learning() {
  usePageTitle("title.learning");

  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [paths, setPaths] = useState<LearningPath[]>([]);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [roles, setRoles] = useState<FracRole[]>([]);
  const [targetRoleId, setTargetRoleId] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (roleId: number | null) => {
    const query = roleId ? `?target_role_id=${roleId}` : "";
    const [recs, p, g, r] = await Promise.all([
      api.get<Recommendation[]>(`/recommendations/me${query}`),
      api.get<LearningPath[]>("/learning-paths/me"),
      api.get<Gap[]>(`/gaps/me${query}`),
      api.get<FracRole[]>("/frac/roles"),
    ]);
    setRecommendations(recs);
    setPaths(p);
    setGaps(g.filter((x) => x.gap > 0.1));
    setRoles(r);
    setExpanded((current) => current ?? recs[0]?.id ?? null);
  }, []);

  useEffect(() => {
    load(targetRoleId)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load your plan."))
      .finally(() => setLoading(false));
  }, [load, targetRoleId]);

  async function buildPath(competencyId: number) {
    setBusy(competencyId);
    setError(null);
    try {
      const query = targetRoleId ? `&target_role_id=${targetRoleId}` : "";
      await api.post<LearningPath>(`/learning-paths?competency_id=${competencyId}${query}`);
      await load(targetRoleId);
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Could not build a path for that competency.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function markComplete(courseId: number) {
    setBusy(courseId);
    try {
      await api.post(`/courses/${courseId}/complete`);
      await load(targetRoleId);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not record that completion.");
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <Spinner label="Working out what would close your gaps" />;

  const totalHours = paths.reduce((sum, p) => sum + p.total_hours, 0);
  const pathedCompetencies = new Set(paths.map((p) => p.competency_id));
  const targetRole = roles.find((r) => r.id === targetRoleId);

  return (
    <>
      <PageHeader
        title="Your development plan"
        subtitle={
          targetRole
            ? `Against ${targetRole.name}, a role you are aiming for`
            : "Against the requirements of your current role"
        }
        meta="Every recommendation states which gap it closes and why"
        action={
          <select
            aria-label="Interview against a target role"
            value={targetRoleId ?? ""}
            onChange={(e) => {
              setLoading(true);
              setTargetRoleId(Number(e.target.value) || null);
            }}
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

      {error && (
        <div className="mb-4">
          <ErrorNote message={error} />
        </div>
      )}

      <div className="mb-4 grid gap-3.5 sm:grid-cols-4">
        <StatTile label="Open gaps" value={gaps.length} />
        <StatTile label="Recommendations" value={recommendations.length} />
        <StatTile label="Active paths" value={paths.length} />
        <StatTile
          label="Study time planned"
          value={totalHours}
          unit="hours"
          note={paths.length ? `~${Math.max(...paths.map((p) => p.estimated_weeks))} weeks` : undefined}
        />
      </div>

      {paths.length > 0 && (
        <div className="mb-4 grid gap-3.5">
          {paths.map((path) => {
            const shortfall = path.reaches_level < path.target_level;
            return (
              <Card
                key={path.id}
                title={`Path: ${path.competency_name}`}
                hint={`L${path.current_level} → L${path.reaches_level} · ${path.total_hours}h · about ${path.estimated_weeks} weeks`}
              >
                {shortfall && (
                  <div className="mb-3">
                    <Note tone="brass">
                      This path reaches <strong className="font-semibold text-ink">L{path.reaches_level}</strong>,
                      short of the L{path.target_level} your role requires. The catalogue does not
                      currently go further on this competency.
                    </Note>
                  </div>
                )}

                <ol className="space-y-0">
                  {path.items.map((item, index) => (
                    <li key={item.course.id} className="grid grid-cols-[28px_minmax(0,1fr)] gap-3">
                      <div className="flex flex-col items-center">
                        <div
                          className={`flex h-6 w-6 shrink-0 items-center justify-center border text-[11px] font-mono ${STATUS_STYLE[item.status]}`}
                        >
                          {index + 1}
                        </div>
                        {index < path.items.length - 1 && (
                          <div className="w-px flex-1 bg-rule" style={{ minHeight: 24 }} />
                        )}
                      </div>

                      <div className="pb-4">
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                          <span className="text-[13.5px] font-semibold">{item.course.title}</span>
                          <span className="tabular shrink-0 font-mono text-[11px] text-ink-3">
                            L{item.course.level_from}–{item.course.level_to} · {item.course.duration_hours}h
                          </span>
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-[11.5px] text-ink-3">
                          <span className="bg-surface-2 px-1.5 py-0.5 font-mono text-[10.5px]">
                            {item.course.provider}
                          </span>
                          <span
                            className={
                              item.status === "available" ? "text-accent" : "text-ink-3"
                            }
                          >
                            {item.status === "available" ? "Start here" : "Locked until earlier steps are done"}
                          </span>
                          {item.included_because && (
                            <span className="italic">{item.included_because}</span>
                          )}
                        </div>
                        {item.status === "available" && (
                          <button
                            disabled={busy === item.course.id}
                            onClick={() => markComplete(item.course.id)}
                            className="mt-2 border border-rule-strong px-3 py-1 text-[12px] text-ink-2 transition-colors hover:border-accent hover:text-ink disabled:opacity-50"
                          >
                            {busy === item.course.id ? "Recording…" : "Mark complete"}
                          </button>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              </Card>
            );
          })}
        </div>
      )}

      <Card
        title="Recommended courses"
        hint="Ranked across all your open gaps. Open one to see how it was ranked."
      >
        {recommendations.length === 0 ? (
          <Empty>
            No recommendations — either every competency meets its requirement, or the
            catalogue has nothing that fits your level bands.
          </Empty>
        ) : (
          <div className="divide-y divide-rule">
            {recommendations.map((rec) => {
              const open = expanded === rec.id;
              return (
                <div key={rec.id} className="py-3.5 first:pt-0 last:pb-0">
                  <button
                    onClick={() => setExpanded(open ? null : rec.id)}
                    aria-expanded={open}
                    aria-label={`${open ? "Hide" : "Show"} why ${rec.course.title} was recommended`}
                    className="flex w-full items-start justify-between gap-4 text-left"
                  >
                    <div className="min-w-0">
                      <div className="text-[14px] font-semibold">{rec.course.title}</div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-[11.5px] text-ink-3">
                        <span className="bg-surface-2 px-1.5 py-0.5 font-mono text-[10.5px]">
                          {rec.course.provider}
                        </span>
                        <span>{rec.competency_name}</span>
                        <span className="tabular font-mono">
                          L{rec.current_level} → L{rec.required_level}
                        </span>
                        <span>{rec.course.duration_hours}h</span>
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="tabular font-mono text-[15px] font-semibold">
                        {rec.score.toFixed(2)}
                      </div>
                      <div className="text-[10.5px] text-ink-3">{open ? "hide" : "why?"}</div>
                    </div>
                  </button>

                  {open && (
                    <div className="mt-3 grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
                      <div>
                        <Note>{rec.reason}</Note>
                        <p className="mt-2.5 text-[12.5px] leading-relaxed text-ink-2">
                          {rec.course.description}
                        </p>
                        {!pathedCompetencies.has(rec.competency_id) && (
                          <button
                            disabled={busy === rec.competency_id}
                            onClick={() => buildPath(rec.competency_id)}
                            className="mt-3 bg-accent px-3.5 py-1.5 text-[12.5px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                          >
                            {busy === rec.competency_id
                              ? "Building…"
                              : `Build a path for ${rec.competency_name}`}
                          </button>
                        )}
                      </div>

                      <div>
                        <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
                          How this was ranked
                        </div>
                        <SignalBars signals={rec.signals} />
                        <p className="mt-2.5 text-[11px] leading-relaxed text-ink-3">
                          {rec.signals.peer_count
                            ? `${rec.signals.peer_count} officers in your role have completed it. `
                            : "No officers in your role have completed it yet. "}
                          Matching uses{" "}
                          {rec.signals.semantic ? "semantic" : "lexical"} similarity
                          {rec.signals.embedder ? ` (${rec.signals.embedder})` : ""}.
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {gaps.length > 0 && (
        <div className="mt-4">
          <Card title="Gaps without a path yet" hint="Build one to get an ordered sequence">
            <div className="flex flex-wrap gap-2">
              {gaps
                .filter((g) => !pathedCompetencies.has(g.competency_id))
                .map((g) => (
                  <button
                    key={g.competency_id}
                    disabled={busy === g.competency_id}
                    onClick={() => buildPath(g.competency_id)}
                    className="border border-rule-strong px-3 py-1.5 text-[12.5px] text-ink-2 transition-colors hover:border-accent hover:text-ink disabled:opacity-50"
                  >
                    {g.competency_name}
                    <span className="tabular ml-2 font-mono text-[11px] text-ink-3">
                      +{g.gap.toFixed(2)}
                    </span>
                  </button>
                ))}
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
