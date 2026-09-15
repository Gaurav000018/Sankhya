import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, api } from "../api";
import { GettingStarted } from "../components/GettingStarted";
import { PageHeader } from "../components/Layout";
import { Icon } from "../components/portal";
import { CompetencyRadar } from "../components/Radar";
import { usePageTitle } from "../hooks/usePageTitle";
import { useT } from "../i18n";
import type { MessageKey } from "../i18n";
import {
  Card,
  Empty,
  ErrorNote,
  LevelBar,
  Note,
  ProgressBar,
  SourceTag,
  Spinner,
  StatTile,
  StatusPill,
  btnPrimary,
  btnSecondary,
} from "../components/ui";
import type {
  Divergence,
  Evidence,
  FracRole,
  Gap,
  LiftSummary,
  ReadinessForecast,
  Recommendation,
  SkillTwin,
} from "../types";

const SOURCE_KEYS: Record<string, MessageKey> = {
  simulation: "source.simulation",
  quiz: "source.quiz",
  diagnostic: "source.diagnostic",
  interview: "source.interview",
  certification: "source.certification",
  supervisor: "source.supervisor",
  learning_activity: "source.learning_activity",
  historical: "source.historical",
  self: "source.self",
};

const DOMAIN_LABELS: Record<string, string> = {
  statistical: "Statistical",
  technical: "Technical",
  digital_governance: "Digital governance",
  behavioural: "Behavioural",
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function titleCase(s: string) {
  return DOMAIN_LABELS[s] ?? s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function LearnerDashboard() {
  const t = useT();
  usePageTitle("title.dashboard");

  const [twin, setTwin] = useState<SkillTwin | null>(null);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [divergence, setDivergence] = useState<Divergence[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [roles, setRoles] = useState<FracRole[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [targetRoleId, setTargetRoleId] = useState<number | null>(null);
  const [targetGaps, setTargetGaps] = useState<Gap[]>([]);
  const [forecast, setForecast] = useState<ReadinessForecast | null>(null);
  const [lift, setLift] = useState<LiftSummary | null>(null);
  const [reportHash, setReportHash] = useState<string | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [openReason, setOpenReason] = useState<number | null>(null);
  const [showAllGaps, setShowAllGaps] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        // Named, not single letters: `t` here would shadow the translation
        // function from the enclosing scope.
        const [skillTwin, gapList, divergences, evidenceRows, roleList, liftData] =
          await Promise.all([
            api.get<SkillTwin>("/skill-twin/me"),
            api.get<Gap[]>("/gaps/me"),
            api.get<Divergence[]>("/divergence/me"),
            api.get<Evidence[]>("/evidence/me?limit=8"),
            api.get<FracRole[]>("/frac/roles"),
            api.get<LiftSummary>("/lift/me?days=180"),
          ]);
        setLift(liftData);
        setTwin(skillTwin);
        setGaps(gapList);
        setDivergence(divergences);
        setEvidence(evidenceRows);
        setRoles(roleList);

        // Default the promotion view to the next rung up. Someone already at
        // the top of the ladder has no next rung, so fall back to the first
        // role rather than leaving the select showing an option that is not
        // actually selected.
        const current = roleList.find((x) => x.id === skillTwin.user.frac_role_id);
        const next = roleList.find(
          (x) => x.level_order === (current?.level_order ?? 0) + 1,
        );
        setTargetRoleId(next?.id ?? roleList[0]?.id ?? null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load your profile.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Ranking is the slowest call on the page, so it loads on its own rather than
  // holding up the whole dashboard.
  useEffect(() => {
    api
      .get<Recommendation[]>("/recommendations/me")
      .then(setRecommendations)
      .catch(() => setRecommendations([]));
  }, []);

  useEffect(() => {
    if (!targetRoleId) return;
    api
      .get<Gap[]>(`/gaps/me?target_role_id=${targetRoleId}`)
      .then(setTargetGaps)
      .catch(() => setTargetGaps([]));
    api
      .get<ReadinessForecast>(`/promotion/forecast?target_role_id=${targetRoleId}`)
      .then(setForecast)
      .catch(() => setForecast(null));
  }, [targetRoleId]);

  const competencyNames = useMemo(
    () => new Map(gaps.map((g) => [g.competency_id, g.competency_name])),
    [gaps],
  );

  const openGaps = gaps.filter((g) => g.gap > 0.1);
  const atTarget = gaps.length - openGaps.length;
  const critical = gaps.filter((g) => g.status === "critical").length;
  const totalEvidence = twin?.competencies.reduce((n, c) => n + c.evidence_count, 0) ?? 0;
  const strongest = twin
    ? [...twin.competencies].sort((a, b) => b.level - a.level)[0]
    : undefined;

  // Largest gap first, so the rows that need action lead the table.
  const gapRows = useMemo(() => [...gaps].sort((a, b) => b.gap - a.gap), [gaps]);
  const visibleGapRows = showAllGaps ? gapRows : gapRows.slice(0, 6);

  const targetRole = roles.find((r) => r.id === targetRoleId);
  const targetOpen = targetGaps.filter((g) => g.gap > 0.1);
  const targetReadiness = targetGaps.length
    ? Math.round(
        (100 * targetGaps.reduce((s, g) => s + Math.min(g.current_level, g.required_level), 0)) /
          targetGaps.reduce((s, g) => s + g.required_level, 0),
      )
    : 0;
  const eligible =
    targetRole && twin ? twin.user.service_years >= targetRole.min_service_years : false;

  if (loading) return <Spinner label={t("common.loading")} />;
  if (error) return <ErrorNote message={error} />;
  if (!twin) return <Empty>No profile found.</Empty>;

  // A newly confirmed officer has no evidence and usually no role yet. The rest
  // of this page exists to interpret evidence, so with none it renders 0%
  // readiness and an empty chart — which reads as broken rather than as empty.
  if (totalEvidence === 0) return <GettingStarted twin={twin} />;

  const reportButton = (
    <div className="text-right">
      <button
        disabled={reportBusy}
        onClick={async () => {
          setReportBusy(true);
          try {
            setReportHash(await api.downloadEvidenceReport(180));
          } catch (e) {
            setError(e instanceof ApiError ? e.message : "Could not generate the report.");
          } finally {
            setReportBusy(false);
          }
        }}
        className={btnSecondary}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
          <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />
        </svg>
        {reportBusy ? t("dashboard.reportGenerating") : t("dashboard.report")}
      </button>
      {reportHash && (
        <div className="mt-1 text-[11.5px] text-ink-3">
          Verification code {reportHash.slice(0, 16)}…
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("nav.dashboard")}
        subtitle="Your competency record, open gaps and development plan"
        action={reportButton}
      />

      {/* -------------------------------------------------- profile summary -- */}
      <section aria-label="Officer profile" className="rounded border border-rule bg-surface">
        <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
          <div className="flex min-w-0 items-start gap-4">
            <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full border border-rule bg-surface-2 text-accent">
              <Icon name="user" size={28} />
            </span>
            <div className="min-w-0">
              <div className="text-[18px] font-semibold text-ink">{twin.user.full_name}</div>
              <div className="text-[13.5px] text-ink-2">
                {twin.role_name ?? "Designation not assigned"}
              </div>
              <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[13px]">
                <dt className="text-ink-3">Officer ID</dt>
                <dd className="tabular text-ink">SAN-{String(twin.user.id).padStart(5, "0")}</dd>
                <dt className="text-ink-3">Service</dt>
                <dd className="text-ink">
                  {twin.user.service_years} {t("dashboard.years")}
                </dd>
                <dt className="text-ink-3">Email</dt>
                <dd className="truncate text-ink">{twin.user.email}</dd>
              </dl>
            </div>
          </div>

          <div className="rounded border border-rule bg-surface-2 p-4">
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-[13.5px] font-semibold text-ink">
                {t("dashboard.roleReadiness")}
              </span>
              <span className="text-[12px] text-ink-3">{twin.role_name ?? ""}</span>
            </div>
            <div className="mt-2">
              <ProgressBar
                value={twin.role_readiness}
                label={t("dashboard.roleReadiness")}
                tone={critical > 0 ? "warn" : "good"}
              />
            </div>
            <p className="mt-2 text-[12px] leading-snug text-ink-3">
              {t("dashboard.roleReadinessNote")}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 border-t border-rule bg-surface-2 px-5 py-3">
          <Link to="/quiz" className={btnPrimary}>
            <Icon name="quiz" size={16} />
            Take an assessment
          </Link>
          <Link to="/interview" className={btnSecondary}>
            <Icon name="interview" size={16} />
            Start an interview
          </Link>
          <Link to="/learning" className={btnSecondary}>
            <Icon name="learning" size={16} />
            Development plan
          </Link>
        </div>
      </section>

      {/* ---------------------------------------------------------- metrics -- */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label={t("dashboard.atTarget")}
          value={atTarget}
          unit={`${t("common.of")} ${gaps.length}`}
          note={
            critical
              ? t("dashboard.criticalGapsCount", { count: critical })
              : t("dashboard.noCriticalGaps")
          }
        />
        <StatTile
          label={t("dashboard.evidenceRecords")}
          value={totalEvidence}
          note={t("dashboard.evidenceNote")}
        />
        <StatTile
          label={t("dashboard.strongestArea")}
          value={strongest ? `L${strongest.level}` : "—"}
          note={strongest?.competency_name}
        />
        <StatTile
          label="Change in last 180 days"
          value={
            lift ? `${lift.summary.mean_change > 0 ? "+" : ""}${lift.summary.mean_change.toFixed(2)}` : "—"
          }
          unit="levels (mean)"
          note={
            lift
              ? `${lift.summary.improved} improved · ${lift.summary.declined} declined`
              : undefined
          }
        />
      </div>

      {divergence.length > 0 && (
        <Note tone="brass">
          <strong className="font-semibold text-ink">Self-rating differs from assessed level.</strong>{" "}
          You rated yourself L{divergence[0].self_rated_level} in {divergence[0].competency_name};
          assessed evidence places you at L{divergence[0].assessed_level}. This is for discussion
          with your supervisor and is not a mark against you — self-assessment carries the lowest
          weight in the model.
        </Note>
      )}

      {/* ------------------------------------------------ competency status -- */}
      <Card
        title="Competency status"
        hint={`${t("dashboard.frcScale")} · largest gap first`}
        flush
        action={
          gapRows.length > 6 && (
            <button
              type="button"
              onClick={() => setShowAllGaps(!showAllGaps)}
              className="text-[13px] font-medium text-accent hover:underline"
            >
              {showAllGaps ? "Show fewer" : `Show all ${gapRows.length}`}
            </button>
          )
        }
      >
        {gapRows.length === 0 ? (
          <div className="p-4">
            <Empty>{t("dashboard.allMet")}</Empty>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table min-w-[760px]">
              <caption className="sr-only">Competency status against your role requirement</caption>
              <thead>
                <tr>
                  <th scope="col">Competency</th>
                  <th scope="col">Domain</th>
                  <th scope="col" className="text-right">Current</th>
                  <th scope="col" className="text-right">Required</th>
                  <th scope="col" className="w-40">Level</th>
                  <th scope="col">Evidence</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {visibleGapRows.map((gap) => (
                  <tr key={gap.competency_id}>
                    <td className="font-medium text-ink">{gap.competency_name}</td>
                    <td className="text-ink-2">{titleCase(gap.domain)}</td>
                    <td className="tabular text-right font-semibold">L{gap.current_level}</td>
                    <td className="tabular text-right text-ink-2">L{gap.required_level}</td>
                    <td>
                      <LevelBar
                        current={gap.current_level}
                        required={gap.required_level}
                        status={gap.status}
                      />
                    </td>
                    <td className="whitespace-nowrap text-ink-3">
                      <SourceTag source={gap.strongest_source} />{" "}
                      <span className="tabular">
                        {gap.evidence_count} {t("common.records")}
                      </span>
                    </td>
                    <td>
                      <StatusPill status={gap.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ------------------------------ recommendations and promotion -------- */}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Card
          title="Recommended learning"
          hint="Ranked on relevance, level fit, urgency and peer completion"
          action={
            <Link to="/learning" className="text-[13px] font-medium text-accent hover:underline">
              Full development plan
            </Link>
          }
          flush
        >
          {recommendations.length === 0 ? (
            <div className="p-4">
              <Empty>No recommendations yet.</Empty>
            </div>
          ) : (
            <ol className="divide-y divide-rule">
              {recommendations.slice(0, 3).map((rec, i) => {
                const open = openReason === rec.id;
                return (
                  <li key={rec.id} className="px-4 py-3.5">
                    <div className="flex items-start gap-3">
                      <span className="tabular mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-sm bg-accent text-[12px] font-semibold text-white">
                        {i + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                          <h3 className="text-[14px] font-semibold text-ink">{rec.course.title}</h3>
                          <span className="tabular text-[12.5px] text-ink-3">
                            {rec.course.duration_hours} hours
                          </span>
                        </div>
                        <p className="mt-0.5 text-[12.5px] text-ink-3">
                          {rec.course.provider ?? rec.course.source} · covers L{rec.course.level_from}–L
                          {rec.course.level_to}
                        </p>
                        <p className="mt-1 text-[13px] text-ink-2">
                          Addresses <span className="font-medium text-ink">{rec.competency_name}</span>{" "}
                          (current L{rec.current_level.toFixed(2)}, required L
                          {rec.required_level.toFixed(2)})
                        </p>
                        <button
                          type="button"
                          onClick={() => setOpenReason(open ? null : rec.id)}
                          aria-expanded={open}
                          className="mt-1.5 text-[12.5px] font-medium text-accent hover:underline"
                        >
                          {open ? "Hide reason" : "Why this course?"}
                        </button>
                        {open && (
                          <div className="mt-2 rounded border border-rule bg-surface-2 p-3">
                            <p className="text-[12.5px] leading-relaxed text-ink-2">{rec.reason}</p>
                            <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 border-t border-rule pt-2 text-[12px] sm:grid-cols-4">
                              {(
                                [
                                  ["Relevance", rec.signals.relevance],
                                  ["Level fit", rec.signals.level_fit],
                                  ["Urgency", rec.signals.urgency],
                                  ["Peers", rec.signals.peers],
                                ] as const
                              )
                                .filter(([, v]) => typeof v === "number")
                                .map(([name, v]) => (
                                  <div key={name} className="flex justify-between gap-2">
                                    <dt className="text-ink-3">{name}</dt>
                                    <dd className="tabular font-semibold text-ink">
                                      {(v as number).toFixed(2)}
                                    </dd>
                                  </div>
                                ))}
                            </dl>
                          </div>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </Card>

        <Card
          title={t("dashboard.promotionReadiness")}
          hint={t("dashboard.promotionHint")}
          action={
            <select
              aria-label="Target role for promotion readiness"
              value={targetRoleId ?? ""}
              onChange={(e) => setTargetRoleId(Number(e.target.value) || null)}
              className="rounded border border-rule-strong bg-surface px-2 py-1 text-[13px]"
            >
              {roles.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          }
        >
          {!targetRole ? (
            <Empty>Choose a target role.</Empty>
          ) : (
            <div className="space-y-4">
              <div>
                <div className="mb-1.5 text-[13px] text-ink-2">
                  Readiness for <span className="font-semibold text-ink">{targetRole.name}</span>{" "}
                  ({targetRole.grade})
                </div>
                <ProgressBar
                  value={targetReadiness}
                  label={`Readiness for ${targetRole.name}`}
                  tone={targetReadiness >= 80 ? "good" : "warn"}
                />
              </div>

              <table className="data-table">
                <tbody>
                  <tr>
                    <th scope="row" className="w-1/2">Competencies still short</th>
                    <td className="tabular font-semibold">
                      {targetOpen.length} of {targetGaps.length}
                    </td>
                  </tr>
                  <tr>
                    <th scope="row">{t("dashboard.serviceRequirement")}</th>
                    <td className="tabular font-semibold">
                      {twin.user.service_years} / {targetRole.min_service_years} years
                    </td>
                  </tr>
                  <tr>
                    <th scope="row">{t("dashboard.eligibility")}</th>
                    <td className={`font-semibold ${eligible ? "text-good" : "text-warn"}`}>
                      {eligible ? t("dashboard.eligible") : t("dashboard.notEligible")}
                    </td>
                  </tr>
                </tbody>
              </table>

              {targetOpen.length > 0 && (
                <div>
                  <div className="mb-1 text-[13px] font-semibold text-ink">
                    Largest gaps for this role
                  </div>
                  <ul className="divide-y divide-rule rounded border border-rule text-[13px]">
                    {targetOpen.slice(0, 3).map((g) => (
                      <li key={g.competency_id} className="flex justify-between gap-3 px-3 py-2">
                        <span className="truncate text-ink-2">{g.competency_name}</span>
                        <span className="tabular shrink-0 font-semibold">
                          +{g.gap.toFixed(2)} levels
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* The forecast extrapolates the officer's own rate of movement.
                  Where a gap is not moving, it says so rather than inventing a
                  date — a projected date nobody can hit is worse than none. */}
              {forecast && (
                <div className="rounded border border-rule bg-surface-2 p-3 text-[13px]">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="font-semibold text-ink">Forecast</span>
                    <span className="tabular text-[12px] text-ink-3">
                      {forecast.monthly_rate > 0
                        ? `+${forecast.monthly_rate.toFixed(3)} levels per month`
                        : "No measurable rate yet"}
                    </span>
                  </div>
                  <p className="mt-1 leading-relaxed text-ink-2">
                    {forecast.slowest?.projected_date ? (
                      <>
                        Slowest competency:{" "}
                        <span className="font-medium text-ink">
                          {forecast.slowest.competency_name}
                        </span>
                        , projected to reach target by{" "}
                        <span className="font-semibold text-ink">
                          {forecast.slowest.projected_date}
                        </span>
                        .
                      </>
                    ) : (
                      <>
                        {forecast.gaps_stalled} of {forecast.open_gaps} open gaps are not moving,
                        so no completion date is projected for them.
                      </>
                    )}
                  </p>
                  <p className="mt-1 text-[12.5px]">
                    <span className="font-semibold text-good">{forecast.gaps_on_track} on track</span>
                    <span className="mx-2 text-rule-strong">|</span>
                    <span className="font-semibold text-warn">{forecast.gaps_stalled} stalled</span>
                  </p>
                </div>
              )}

              <Link to="/promotion" className="inline-block text-[13px] font-medium text-accent hover:underline">
                Open promotion simulator
              </Link>
            </div>
          )}
        </Card>
      </div>

      {/* ---------------------------------------- secondary, collapsed -------- */}
      <h2 className="pt-2 text-[15px] font-semibold text-ink">Progress and records</h2>

      {lift && lift.summary.measured > 0 && (
        <Card
          collapsible
          defaultOpen
          flush
          title={`Progress over the last ${lift.window_days} days`}
          hint={`${lift.summary.improved} improved · ${lift.summary.steady} steady · ${lift.summary.declined} declined · ${lift.summary.evidence_added} new records`}
        >
          <div className="overflow-x-auto">
            <table className="data-table min-w-[520px]">
              <thead>
                <tr>
                  <th scope="col">Competency</th>
                  <th scope="col" className="text-right">{lift.window_days} days ago</th>
                  <th scope="col" className="text-right">Now</th>
                  <th scope="col" className="text-right">Change</th>
                </tr>
              </thead>
              <tbody>
                {lift.competencies
                  .filter((c) => Math.abs(c.change) >= 0.15)
                  .slice(0, 8)
                  .map((c) => (
                    <tr key={c.competency_id}>
                      <td className="text-ink">{c.competency_name}</td>
                      <td className="tabular text-right text-ink-2">L{c.level_then.toFixed(2)}</td>
                      <td className="tabular text-right font-medium">L{c.level_now.toFixed(2)}</td>
                      <td
                        className={`tabular text-right font-semibold ${
                          c.change > 0 ? "text-good" : "text-critical"
                        }`}
                      >
                        {c.change > 0 ? "+" : ""}
                        {c.change.toFixed(2)}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <p className="border-t border-rule px-4 py-2.5 text-[12px] leading-relaxed text-ink-3">
            {lift.note}
          </p>
        </Card>
      )}

      <Card
        collapsible
        defaultOpen={false}
        title={t("dashboard.competencyProfile")}
        hint="Chart of assessed level against role requirement"
      >
        <div className="mx-auto max-w-[460px]">
          <CompetencyRadar competencies={twin.competencies} gaps={gaps} />
        </div>
      </Card>

      <Card
        collapsible
        defaultOpen={false}
        flush
        title="Recent evidence records"
        hint={t("dashboard.evidenceTimelineHint")}
      >
        {evidence.length === 0 ? (
          <div className="p-4">
            <Empty>No evidence recorded yet.</Empty>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table min-w-[560px]">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Competency</th>
                  <th scope="col">Source</th>
                  <th scope="col" className="text-right">Level</th>
                  <th scope="col" className="text-right">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {evidence.map((item) => (
                  <tr key={item.id}>
                    <td className="tabular whitespace-nowrap text-ink-2">{formatDate(item.created_at)}</td>
                    <td className="text-ink">
                      {competencyNames.get(item.competency_id) ?? `Competency ${item.competency_id}`}
                    </td>
                    <td className="text-ink-2">
                      {SOURCE_KEYS[item.source] ? t(SOURCE_KEYS[item.source]) : item.source}
                    </td>
                    <td className="tabular text-right font-semibold">L{item.level_estimate}</td>
                    <td className="tabular text-right text-ink-2">{item.confidence}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="border-t border-rule px-4 py-2.5 text-[12px] leading-relaxed text-ink-3">
          Demonstrated work counts for more than course completion, and self-assessment counts for
          least. Corrections are added as new records; existing records are never edited.
        </p>
      </Card>
    </div>
  );
}
