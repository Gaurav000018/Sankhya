import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../api";
import { AbilityTrace } from "../components/AbilityScale";
import type { TraceStep } from "../components/AbilityScale";
import { PageHeader } from "../components/Layout";
import { Card, Empty, ErrorNote, LevelBar, Note, Spinner, StatTile, StatusPill } from "../components/ui";
import { usePageTitle } from "../hooks/usePageTitle";
import type { GapStatus } from "../types";

/**
 * Officer records, for an administrator or a supervisor.
 *
 * Every other administrator screen is an aggregate. This is the one that shows
 * a named person, which is why it is built the way it is:
 *
 * **Nothing here can be edited.** There is no form, no override, no "set
 * level". Every level in the platform is derived from evidence and the only way
 * to affect one is to append more, with a source and a confidence. A screen
 * that let an administrator type a number would quietly make the audit trail a
 * fiction.
 *
 * **The evidence travels with the level.** A competency row shows the level,
 * what the role requires, how many observations sit behind it and what the
 * strongest of those was. A readiness figure with no trail is an assertion, and
 * an officer being discussed in a promotion board deserves better than one.
 *
 * **Intervals, not points.** An adaptive assessment reports a range, and a
 * supervisor reading "L2.1" without knowing it means L1.2–L3.0 will
 * over-conclude. Every assessment row carries its width.
 */

interface LearnerRow {
  user_id: number;
  full_name: string;
  email: string;
  account_role: string;
  division: string | null;
  frac_role: string | null;
  service_years: number;
  is_active: boolean;
  readiness: number;
  competencies_required: number;
  competencies_measured: number;
  competencies_at_target: number;
  critical_gaps: number;
  widest_gap_competency: string | null;
  widest_gap: number;
  evidence_count: number;
  demonstrated_count: number;
  assessments: number;
  interviews: number;
  courses_completed: number;
  last_activity: string | null;
}

interface Roster {
  learners: LearnerRow[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  scope: string;
  note?: string;
}

interface Detail {
  profile: {
    user_id: number;
    full_name: string;
    email: string;
    account_role: string;
    division: string | null;
    frac_role: string | null;
    service_years: number;
    is_active: boolean;
    fluency_scoring_enabled: boolean;
  };
  summary: {
    readiness: number;
    competencies_measured: number;
    open_gaps: number;
    critical_gaps: number;
    evidence_records: number;
    demonstrated_records: number;
    assessments: number;
    interviews: number;
    courses_completed: number;
    mean_assessment_interval: number | null;
    last_activity: string | null;
  };
  competencies: {
    competency_id: number;
    competency_name: string;
    current_level: number;
    required_level: number;
    gap: number;
    status: GapStatus;
    evidence_count: number;
    evidence_weight: number;
    strongest_source: string | null;
  }[];
  divergence: {
    competency_id: number;
    competency_name: string;
    self_rated_level: number;
    assessed_level: number;
    divergence: number;
  }[];
  assessments: {
    id: number;
    competency_name: string | null;
    adaptive: boolean;
    items: number;
    correct: number;
    accuracy: number;
    derived_level: number | null;
    level_low: number | null;
    level_high: number | null;
    reliability: number | null;
    stop_reason: string | null;
    mean_item_level: number | null;
    submitted_at: string;
    trace: TraceStep[];
  }[];
  interviews: {
    id: number;
    status: string;
    questions: number;
    scored: number;
    axes: Record<string, number>;
    started_at: string;
  }[];
  learning: {
    id: number;
    course_title: string;
    completed_at: string;
    level_at_completion: number | null;
  }[];
  evidence: {
    id: number;
    competency_name: string | null;
    level_estimate: number;
    confidence: number;
    source: string;
    note: string | null;
    created_at: string;
  }[];
  note: string;
}

interface Filters {
  divisions: { id: number; name: string }[];
  frac_roles: { id: number; name: string }[];
}

interface Coverage {
  officers: number;
  assessed: number;
  interviewed: number;
  assessed_pct: number;
  adaptive_attempts: number;
  mean_interval_width: number | null;
  stop_reasons: Record<string, number>;
  note: string;
}

const SOURCE_LABELS: Record<string, string> = {
  simulation: "Simulation",
  quiz: "Assessment",
  diagnostic: "Diagnostic",
  interview: "AI interview",
  certification: "Certification",
  supervisor: "Supervisor rating",
  learning_activity: "Course completion",
  historical: "Service record",
  self: "Self-assessment",
};

const DEMONSTRATED = new Set(["simulation", "quiz", "diagnostic", "interview"]);

const STOP_LABEL: Record<string, string> = {
  precision: "reached target precision",
  max_items: "hit the item ceiling",
  exhausted: "bank exhausted",
  no_informative_items: "no informative items left",
};

function when(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function AdminLearners() {
  usePageTitle("title.learners");

  const [roster, setRoster] = useState<Roster | null>(null);
  const [filters, setFilters] = useState<Filters | null>(null);
  const [coverage, setCoverage] = useState<Coverage | null>(null);

  const [search, setSearch] = useState("");
  const [divisionId, setDivisionId] = useState<string>("");
  const [roleId, setRoleId] = useState<string>("");
  const [criticalOnly, setCriticalOnly] = useState(false);
  const [sort, setSort] = useState("readiness");
  const [page, setPage] = useState(1);

  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [detailBusy, setDetailBusy] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const query = useMemo(() => {
    const params = new URLSearchParams({ page: String(page), sort });
    if (search.trim()) params.set("search", search.trim());
    if (divisionId) params.set("division_id", divisionId);
    if (roleId) params.set("frac_role_id", roleId);
    if (criticalOnly) params.set("only_with_critical_gaps", "true");
    return params.toString();
  }, [page, sort, search, divisionId, roleId, criticalOnly]);

  const loadRoster = useCallback(async () => {
    setRoster(await api.get<Roster>(`/admin/learners?${query}`));
  }, [query]);

  useEffect(() => {
    // Debounced, because this fires on every keystroke in the search box and
    // the roster query touches every officer's competency profile.
    const timer = setTimeout(() => {
      loadRoster()
        .catch((e) => setError(e instanceof Error ? e.message : "Could not load the roster."))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(timer);
  }, [loadRoster]);

  useEffect(() => {
    api.get<Filters>("/admin/filters").then(setFilters).catch(() => undefined);
    // Admin-only; a supervisor gets a 403 here and simply sees no coverage card.
    api.get<Coverage>("/admin/assessment-coverage").then(setCoverage).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (selected === null) {
      setDetail(null);
      return;
    }
    setDetailBusy(true);
    api
      .get<Detail>(`/admin/learners/${selected}`)
      .then(setDetail)
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Could not load that officer."),
      )
      .finally(() => setDetailBusy(false));
  }, [selected]);

  if (loading) return <Spinner label="Loading the officer roster" />;

  if (selected !== null) {
    return (
      <LearnerRecord
        detail={detail}
        busy={detailBusy}
        onBack={() => setSelected(null)}
      />
    );
  }

  return (
    <>
      <PageHeader
        title="Officer records"
        subtitle={roster ? `${roster.total} officers · ${roster.scope}` : ""}
        meta="Lowest readiness first — this list exists to find who needs attention, not to rank anybody"
      />

      {error && (
        <div className="mb-4">
          <ErrorNote message={error} />
        </div>
      )}

      {coverage && (
        <div className="mb-4 grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile
            label="Officers"
            value={coverage.officers}
            note={`${coverage.assessed} have taken an assessment`}
          />
          <StatTile
            label="Assessment coverage"
            value={coverage.assessed_pct}
            unit="%"
            note="Readiness for the rest rests on weaker evidence"
          />
          <StatTile
            label="Adaptive attempts"
            value={coverage.adaptive_attempts}
            note={`${coverage.interviewed} officers also interviewed`}
          />
          <StatTile
            label="Mean interval width"
            value={coverage.mean_interval_width ?? "—"}
            note="FRAC levels — how sharply the assessment resolves anyone"
          />
        </div>
      )}

      <Card className="mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-[220px] flex-1">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
              Search
            </span>
            <input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Name or email"
              className="w-full border border-rule bg-surface-2 px-3 py-2 text-[13.5px] outline-none focus:border-accent"
            />
          </label>

          {filters && filters.divisions.length > 1 && (
            <label>
              <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
                Division
              </span>
              <select
                value={divisionId}
                onChange={(e) => {
                  setDivisionId(e.target.value);
                  setPage(1);
                }}
                className="border border-rule bg-surface-2 px-3 py-2 text-[13.5px] outline-none focus:border-accent"
              >
                <option value="">All divisions</option>
                {filters.divisions.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>
          )}

          {filters && (
            <label>
              <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
                FRAC role
              </span>
              <select
                value={roleId}
                onChange={(e) => {
                  setRoleId(e.target.value);
                  setPage(1);
                }}
                className="border border-rule bg-surface-2 px-3 py-2 text-[13.5px] outline-none focus:border-accent"
              >
                <option value="">All roles</option>
                {filters.frac_roles.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
          )}

          <label>
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
              Sort
            </span>
            <select
              value={sort}
              onChange={(e) => {
                setSort(e.target.value);
                setPage(1);
              }}
              className="border border-rule bg-surface-2 px-3 py-2 text-[13.5px] outline-none focus:border-accent"
            >
              <option value="readiness">Lowest readiness</option>
              <option value="readiness_desc">Highest readiness</option>
              <option value="name">Name</option>
              <option value="recent">Most recently added</option>
            </select>
          </label>

          <label className="flex cursor-pointer items-center gap-2 pb-2 text-[13px] text-ink-2">
            <input
              type="checkbox"
              checked={criticalOnly}
              onChange={(e) => {
                setCriticalOnly(e.target.checked);
                setPage(1);
              }}
            />
            Critical gaps only
          </label>
        </div>
      </Card>

      {roster && roster.learners.length === 0 ? (
        <Empty>No officers match those filters.</Empty>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-rule text-left text-[10.5px] uppercase tracking-[0.06em] text-ink-3">
                  <th className="pb-2 font-semibold">Officer</th>
                  <th className="pb-2 font-semibold">Division</th>
                  <th className="pb-2 font-semibold">FRAC role</th>
                  <th className="pb-2 text-right font-semibold">Readiness</th>
                  <th className="pb-2 text-right font-semibold">Measured</th>
                  <th className="pb-2 text-right font-semibold">Critical</th>
                  <th className="pb-2 font-semibold">Widest gap</th>
                  <th className="pb-2 text-right font-semibold">Evidence</th>
                  <th className="pb-2 text-right font-semibold">Last seen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {roster?.learners.map((row) => (
                  <tr
                    key={row.user_id}
                    onClick={() => setSelected(row.user_id)}
                    className="cursor-pointer transition-colors hover:bg-surface-2"
                  >
                    <td className="py-2.5 pr-3">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelected(row.user_id);
                        }}
                        className="text-left font-medium hover:text-accent"
                      >
                        {row.full_name}
                      </button>
                      <div className="text-[11px] text-ink-3">{row.email}</div>
                    </td>
                    <td className="py-2.5 pr-3 text-ink-2">{row.division ?? "—"}</td>
                    <td className="py-2.5 pr-3 text-ink-2">{row.frac_role ?? "No role assigned"}</td>
                    <td className="tabular py-2.5 pr-3 text-right font-mono font-semibold">
                      {row.readiness}%
                    </td>
                    {/* How much of that readiness rests on evidence rather than
                        on the default floor. A high figure over two measured
                        competencies is a statement about coverage. */}
                    <td className="tabular py-2.5 pr-3 text-right font-mono text-ink-3">
                      {row.competencies_measured}/{row.competencies_required}
                    </td>
                    <td
                      className={`tabular py-2.5 pr-3 text-right font-mono ${
                        row.critical_gaps > 0 ? "font-semibold text-critical" : "text-ink-3"
                      }`}
                    >
                      {row.critical_gaps}
                    </td>
                    <td className="py-2.5 pr-3 text-ink-2">
                      {row.widest_gap_competency ? (
                        <>
                          <span className="truncate">{row.widest_gap_competency}</span>
                          <span className="tabular ml-1.5 font-mono text-[11px] text-ink-3">
                            −{row.widest_gap}
                          </span>
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="tabular py-2.5 pr-3 text-right font-mono text-ink-3">
                      {row.demonstrated_count}/{row.evidence_count}
                    </td>
                    <td className="py-2.5 text-right text-[11.5px] text-ink-3">
                      {when(row.last_activity)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {roster && roster.pages > 1 && (
            <div className="mt-4 flex items-center justify-between border-t border-rule pt-3">
              <span className="tabular font-mono text-[12px] text-ink-3">
                Page {roster.page} of {roster.pages}
              </span>
              <div className="flex gap-2">
                <button
                  disabled={roster.page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="border border-rule-strong px-3 py-1.5 text-[12.5px] text-ink-2 transition-colors hover:border-accent hover:text-ink disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  disabled={roster.page >= roster.pages}
                  onClick={() => setPage((p) => p + 1)}
                  className="border border-rule-strong px-3 py-1.5 text-[12.5px] text-ink-2 transition-colors hover:border-accent hover:text-ink disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </Card>
      )}

      {roster?.note && (
        <div className="mt-4">
          <Note>{roster.note}</Note>
        </div>
      )}
    </>
  );
}

// --------------------------------------------------------------------------- //
// One officer
// --------------------------------------------------------------------------- //

function LearnerRecord({
  detail,
  busy,
  onBack,
}: {
  detail: Detail | null;
  busy: boolean;
  onBack: () => void;
}) {
  const [openTrace, setOpenTrace] = useState<number | null>(null);

  if (busy || !detail) return <Spinner label="Assembling the record" />;

  const { profile, summary } = detail;

  return (
    <>
      <PageHeader
        title={profile.full_name}
        subtitle={`${profile.frac_role ?? "No FRAC role assigned"} · ${profile.division ?? "No division"} · ${profile.service_years} years of service`}
        meta={profile.email}
        action={
          <button
            onClick={onBack}
            className="border border-rule-strong px-4 py-2 text-sm text-ink-2 transition-colors hover:border-accent hover:text-ink"
          >
            Back to roster
          </button>
        }
      />

      <div className="mb-4 grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Role readiness"
          value={summary.readiness}
          unit="%"
          note="Criticality-weighted against their own role"
        />
        <StatTile
          label="Critical gaps"
          value={summary.critical_gaps}
          note={`${summary.open_gaps} open gaps in total`}
        />
        <StatTile
          label="Evidence records"
          value={summary.evidence_records}
          note={`${summary.demonstrated_records} from demonstrated work`}
        />
        <StatTile
          label="Assessment precision"
          value={
            summary.mean_assessment_interval !== null
              ? `±${(summary.mean_assessment_interval / 2).toFixed(2)}`
              : "—"
          }
          note={
            summary.assessments > 0
              ? `Mean over ${summary.assessments} assessments`
              : "Never assessed"
          }
        />
      </div>

      {summary.assessments === 0 && (
        <div className="mb-4">
          <Note tone="brass">
            <strong className="font-semibold text-ink">
              This officer has never taken an assessment.
            </strong>{" "}
            Their readiness figure rests on course completions, supervisor
            ratings and self-assessment — the weakest sources in the model. Read
            it as a starting point rather than as a measurement.
          </Note>
        </div>
      )}

      <div className="mb-4 grid gap-3.5 lg:grid-cols-[minmax(0,1fr)_400px]">
        <Card
          title="Competency profile"
          hint="Every level is derived from the evidence counted beside it"
        >
          <div className="divide-y divide-rule">
            {detail.competencies.map((c) => (
              <div key={c.competency_id} className="py-2.5 first:pt-0">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="min-w-0 truncate text-[13.5px]">{c.competency_name}</span>
                  <span className="flex shrink-0 items-baseline gap-3">
                    <span className="tabular font-mono text-[13px] font-semibold">
                      L{c.current_level}
                    </span>
                    <span className="tabular font-mono text-[11.5px] text-ink-3">
                      / L{c.required_level}
                    </span>
                    <StatusPill status={c.status} />
                  </span>
                </div>
                <div className="mt-1.5">
                  <LevelBar
                    current={c.current_level}
                    required={c.required_level}
                    status={c.status}
                  />
                </div>
                <div className="tabular mt-1.5 flex flex-wrap gap-x-4 font-mono text-[11px] text-ink-3">
                  <span>
                    {c.evidence_count} observation{c.evidence_count === 1 ? "" : "s"}
                  </span>
                  <span>weight {c.evidence_weight.toFixed(2)}</span>
                  {c.strongest_source && (
                    <span>strongest: {SOURCE_LABELS[c.strongest_source] ?? c.strongest_source}</span>
                  )}
                  {c.evidence_count === 0 && (
                    <span className="text-warn">no evidence — counted at the floor</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>

        <div className="grid gap-3.5">
          {detail.divergence.length > 0 && (
            <Card
              title="Confidence–competence divergence"
              hint="Where the self-rating markedly exceeds assessed evidence"
            >
              <div className="divide-y divide-rule">
                {detail.divergence.map((d) => (
                  <div key={d.competency_id} className="py-2 first:pt-0">
                    <div className="text-[13px]">{d.competency_name}</div>
                    <div className="tabular mt-1 flex gap-4 font-mono text-[11.5px] text-ink-3">
                      <span>self L{d.self_rated_level}</span>
                      <span>assessed L{d.assessed_level}</span>
                      <span className="text-warn">+{d.divergence}</span>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-3">
                <Note tone="brass">
                  A flag for a conversation, not a mark against the officer.
                  Self-assessment carries the lowest weight in the model
                  precisely because this happens.
                </Note>
              </div>
            </Card>
          )}

          <Card title="Interviews" hint="Reported per axis, never combined">
            {detail.interviews.length === 0 ? (
              <Empty>No interviews yet.</Empty>
            ) : (
              <div className="divide-y divide-rule">
                {detail.interviews.map((iv) => (
                  <div key={iv.id} className="py-2.5 first:pt-0">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="text-[13px]">{when(iv.started_at)}</span>
                      <span className="text-[11px] text-ink-3">
                        {iv.scored} of {iv.questions} scored
                      </span>
                    </div>
                    <div className="tabular mt-1 flex flex-wrap gap-x-4 font-mono text-[11.5px] text-ink-3">
                      {Object.entries(iv.axes).map(([axis, value]) => (
                        <span key={axis}>
                          {axis} {value}
                        </span>
                      ))}
                      {Object.keys(iv.axes).length === 0 && <span>not yet scored</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      <div className="mb-4">
        <Card
          title="Adaptive assessments"
          hint="The interval is the point — two overlapping results are not a measured change"
        >
          {detail.assessments.length === 0 ? (
            <Empty>This officer has not taken an assessment.</Empty>
          ) : (
            <div className="divide-y divide-rule">
              {detail.assessments.map((a) => (
                <div key={a.id} className="py-3 first:pt-0">
                  <div className="flex flex-wrap items-baseline justify-between gap-3">
                    <span className="text-[13.5px] font-medium">
                      {a.competency_name ?? "—"}
                    </span>
                    <span className="flex items-baseline gap-4">
                      <span className="tabular font-mono text-[12px] text-ink-3">
                        {a.correct}/{a.items} correct
                      </span>
                      <span className="tabular font-mono text-[13px]">
                        <span className="font-semibold">L{a.derived_level}</span>
                        {a.level_low !== null && (
                          <span className="ml-1.5 text-[11px] text-ink-3">
                            ({a.level_low}–{a.level_high})
                          </span>
                        )}
                      </span>
                      <span className="text-[11px] text-ink-3">{when(a.submitted_at)}</span>
                    </span>
                  </div>
                  <div className="tabular mt-1 flex flex-wrap gap-x-4 font-mono text-[11px] text-ink-3">
                    {a.adaptive ? <span>adaptive</span> : <span>fixed form</span>}
                    {a.reliability !== null && <span>weight {a.reliability}</span>}
                    {a.mean_item_level !== null && (
                      <span>mean question L{a.mean_item_level}</span>
                    )}
                    {a.stop_reason && (
                      <span>{STOP_LABEL[a.stop_reason] ?? a.stop_reason}</span>
                    )}
                    {a.trace.length > 0 && (
                      <button
                        onClick={() => setOpenTrace(openTrace === a.id ? null : a.id)}
                        className="text-accent hover:underline"
                      >
                        {openTrace === a.id ? "hide path" : "show path"}
                      </button>
                    )}
                  </div>

                  {/* The trace matters here more than on the officer's own
                      screen: a bare "L2.1" invites the reading that they are
                      weak, where the path shows whether the estimate was well
                      determined or whether the bank simply ran out near them. */}
                  {openTrace === a.id && a.trace.length > 0 && (
                    <div className="mt-3 border border-rule bg-surface-2 p-3">
                      <AbilityTrace steps={a.trace} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-3.5 lg:grid-cols-[minmax(0,1fr)_400px]">
        <Card title="Evidence trail" hint="Append-only — every level above traces to a row here">
          <div className="max-h-[520px] overflow-y-auto">
            <div className="divide-y divide-rule">
              {detail.evidence.map((ev) => (
                <div key={ev.id} className="py-2.5 first:pt-0">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="min-w-0 truncate text-[13px]">
                      {ev.competency_name ?? "—"}
                    </span>
                    <span className="flex shrink-0 items-baseline gap-3">
                      <span className="tabular font-mono text-[12.5px] font-semibold">
                        L{ev.level_estimate}
                      </span>
                      <span
                        className={`text-[10.5px] font-semibold uppercase tracking-[0.05em] ${
                          DEMONSTRATED.has(ev.source) ? "text-accent" : "text-ink-3"
                        }`}
                      >
                        {SOURCE_LABELS[ev.source] ?? ev.source}
                      </span>
                      <span className="tabular font-mono text-[11px] text-ink-3">
                        w{ev.confidence}
                      </span>
                    </span>
                  </div>
                  {ev.note && (
                    <div className="mt-0.5 text-[11.5px] leading-relaxed text-ink-3">
                      {ev.note}
                    </div>
                  )}
                  <div className="text-[10.5px] text-ink-3">{when(ev.created_at)}</div>
                </div>
              ))}
            </div>
          </div>
        </Card>

        <div className="grid gap-3.5">
          <Card title="Learning completed">
            {detail.learning.length === 0 ? (
              <Empty>No course completions recorded.</Empty>
            ) : (
              <div className="divide-y divide-rule">
                {detail.learning.map((l) => (
                  <div key={l.id} className="py-2 first:pt-0">
                    <div className="text-[13px]">{l.course_title}</div>
                    <div className="tabular mt-0.5 flex gap-3 font-mono text-[11px] text-ink-3">
                      <span>{when(l.completed_at)}</span>
                      {l.level_at_completion !== null && (
                        <span>at L{l.level_at_completion}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Note>{detail.note}</Note>
        </div>
      </div>
    </>
  );
}
