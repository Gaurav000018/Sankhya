import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, api } from "../api";
import { GettingStarted } from "../components/GettingStarted";
import { CompetencyRadar } from "../components/Radar";
import { ReadinessRing } from "../components/ReadinessRing";
import { useCountUp } from "../hooks/useReveal";
import { usePageTitle } from "../hooks/usePageTitle";
import { useT } from "../i18n";
import type { MessageKey } from "../i18n";
import {
  Card,
  Empty,
  ErrorNote,
  LevelBar,
  Note,
  SourceTag,
  Spinner,
  StatusPill,
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

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 31) return `${days} days ago`;
  const months = Math.floor(days / 30);
  return months === 1 ? "1 month ago" : `${months} months ago`;
}

/** A figure that counts up on first paint. The digits are monospaced and the
 *  final value is written before the animation starts, so the row never
 *  reflows as the number grows. */
function Figure({
  value,
  decimals = 0,
  className = "",
}: {
  value: number;
  decimals?: number;
  className?: string;
}) {
  const ref = useCountUp(value, { decimals, durationMs: 900 });
  return (
    <span ref={ref} className={`tabular font-mono ${className}`}>
      {value}
    </span>
  );
}

function Tile({
  label,
  value,
  decimals = 0,
  unit,
  note,
  tone,
}: {
  label: string;
  value: number | string;
  decimals?: number;
  unit?: string;
  note?: string;
  tone?: "accent" | "critical";
}) {
  const accentRing =
    tone === "critical"
      ? "border-critical/35 hover:border-critical/60"
      : tone === "accent"
        ? "border-accent/30 hover:border-accent/55"
        : "border-rule hover:border-rule-strong";
  return (
    <div
      className={`rounded-lg border bg-surface px-5 py-4 transition-colors duration-300 ${accentRing}`}
    >
      <div className="text-[10.5px] font-semibold uppercase tracking-[0.09em] text-ink-3">
        {label}
      </div>
      <div className="mt-2.5 flex items-baseline gap-1.5">
        {typeof value === "number" ? (
          <Figure
            value={value}
            decimals={decimals}
            className={`text-[30px] font-medium leading-none ${
              tone === "critical" ? "text-critical" : ""
            }`}
          />
        ) : (
          <span className="tabular font-mono text-[26px] font-medium leading-none">
            {value}
          </span>
        )}
        {unit && <span className="text-[13px] text-ink-3">{unit}</span>}
      </div>
      {note && <div className="mt-2 text-[12px] leading-snug text-ink-2">{note}</div>}
    </div>
  );
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

  // Ranking runs a bandit over the catalogue and is the slowest call on the
  // page, so it loads on its own rather than holding up the whole dashboard.
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
  // readiness, an empty radar and a "strongest area" chosen from competencies
  // nobody has measured — which reads as broken rather than as empty.
  if (totalEvidence === 0) return <GettingStarted twin={twin} />;

  return (
    <>
      {/* ------------------------------------------------------- identity -- */}
      <section className="relative mb-4 overflow-hidden rounded-xl border border-rule bg-surface">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute right-[-8rem] top-[-10rem] -z-10 h-72 w-72 rounded-full bg-accent opacity-[0.07] blur-[90px]"
        />
        <div className="flex flex-wrap items-center justify-between gap-6 p-6">
          <div className="flex items-center gap-6">
            <ReadinessRing
              value={twin.role_readiness}
              label={t("dashboard.roleReadiness")}
              tone={critical > 0 ? "warn" : "accent"}
            />
            <div>
              <h1
                tabIndex={-1}
                ref={(node) => {
                  // Moving focus to the heading on navigation is what tells a
                  // screen reader the page changed. A client-side route change
                  // is otherwise silent.
                  if (node && node.dataset.focused !== "1") {
                    node.dataset.focused = "1";
                    node.focus({ preventScroll: true });
                  }
                }}
                className="font-serif text-[28px] font-medium leading-tight tracking-[-0.015em]"
              >
                {twin.user.full_name}
              </h1>
              <p className="mt-1 text-[14px] text-ink-2">
                {twin.role_name ?? "Role not assigned"}
              </p>
              <p className="mt-2 font-mono text-[11.5px] text-ink-3">
                {twin.user.service_years} {t("dashboard.years")} · {twin.user.email}
              </p>
              <p className="mt-1.5 max-w-[42ch] text-[12px] leading-snug text-ink-3">
                {t("dashboard.roleReadinessNote")}
              </p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                <Link
                  to="/quiz"
                  className="rounded-full border border-rule-strong px-3 py-1 text-[12px] text-ink-2 transition-colors hover:border-accent hover:text-accent"
                >
                  Take an assessment
                </Link>
                <Link
                  to="/interview"
                  className="rounded-full border border-rule-strong px-3 py-1 text-[12px] text-ink-2 transition-colors hover:border-accent hover:text-accent"
                >
                  Start an interview
                </Link>
                <Link
                  to="/learning"
                  className="rounded-full border border-rule-strong px-3 py-1 text-[12px] text-ink-2 transition-colors hover:border-accent hover:text-accent"
                >
                  Development plan
                </Link>
              </div>
            </div>
          </div>

          <div className="text-right">
            <button
              disabled={reportBusy}
              onClick={async () => {
                setReportBusy(true);
                try {
                  setReportHash(await api.downloadEvidenceReport(180));
                } catch (e) {
                  setError(
                    e instanceof ApiError ? e.message : "Could not generate the report.",
                  );
                } finally {
                  setReportBusy(false);
                }
              }}
              className="rounded-full bg-accent px-4 py-2 text-[13px] font-medium text-ground transition-[filter] hover:brightness-110 disabled:opacity-50"
            >
              {reportBusy ? t("dashboard.reportGenerating") : t("dashboard.report")}
            </button>
            {reportHash && (
              <div className="mt-2 font-mono text-[10px] text-ink-3">
                verification {reportHash.slice(0, 16)}…
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------- stats -- */}
      <div className="mb-4 grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        <Tile
          label={t("dashboard.atTarget")}
          value={atTarget}
          unit={`${t("common.of")} ${gaps.length} ${t("dashboard.competencies")}`}
          note={
            critical
              ? t("dashboard.criticalGapsCount", { count: critical })
              : t("dashboard.noCriticalGaps")
          }
          tone={critical ? "critical" : "accent"}
        />
        <Tile
          label={t("dashboard.evidenceRecords")}
          value={totalEvidence}
          note={t("dashboard.evidenceNote")}
        />
        <Tile
          label={t("dashboard.strongestArea")}
          value={strongest?.competency_code ?? "—"}
          note={`${strongest?.competency_name ?? ""} · L${strongest?.level ?? 0}`}
        />
        <Tile
          label="Movement · 180 days"
          value={lift?.summary.mean_change ?? 0}
          decimals={2}
          unit="mean level change"
          note={
            lift
              ? `${lift.summary.improved} improved · ${lift.summary.declined} declined · ${lift.summary.evidence_added} new records`
              : undefined
          }
        />
      </div>

      {divergence.length > 0 && (
        <div className="mb-4">
          <Note tone="brass">
            <strong className="font-semibold text-ink">
              Confidence–competence divergence detected.
            </strong>{" "}
            You rated yourself L{divergence[0].self_rated_level} on{" "}
            {divergence[0].competency_name}; assessed evidence places you at L
            {divergence[0].assessed_level}. This is flagged for a conversation with your
            supervisor, not a mark against you — self-assessment carries the lowest weight
            in the model precisely because this happens.
          </Note>
        </div>
      )}

      {/* ------------------------------------------------ profile and gaps -- */}
      <div className="mb-4 grid gap-3.5 lg:grid-cols-[420px_minmax(0,1fr)]">
        <Card title={t("dashboard.competencyProfile")} hint={t("dashboard.frcScale")}>
          <CompetencyRadar competencies={twin.competencies} gaps={gaps} />
        </Card>

        <Card title={t("dashboard.gaps")} hint={t("dashboard.gapsHint")}>
          {openGaps.length === 0 ? (
            <Empty>{t("dashboard.allMet")}</Empty>
          ) : (
            <div className="divide-y divide-rule">
              {openGaps.slice(0, 6).map((gap) => (
                <div
                  key={gap.competency_id}
                  className="grid grid-cols-[minmax(0,1fr)_104px_120px_92px] items-center gap-3 py-3 first:pt-0"
                >
                  <div className="min-w-0">
                    <div
                      className={`truncate text-[13.5px] font-semibold ${
                        gap.status === "critical" ? "text-critical" : ""
                      }`}
                    >
                      {gap.competency_name}
                    </div>
                    <div className="mt-0.5 flex items-center gap-1.5 text-[11.5px] text-ink-3">
                      <SourceTag source={gap.strongest_source} />
                      <span>
                        {gap.evidence_count} {t("common.records")}
                      </span>
                    </div>
                  </div>
                  <div className="tabular whitespace-nowrap font-mono text-[13px]">
                    <span
                      className={
                        gap.status === "critical"
                          ? "font-semibold text-critical"
                          : "font-semibold"
                      }
                    >
                      {gap.current_level}
                    </span>
                    <span className="text-rule-strong"> → </span>
                    {gap.required_level}
                  </div>
                  <LevelBar
                    current={gap.current_level}
                    required={gap.required_level}
                    status={gap.status}
                  />
                  <div className="text-right">
                    <StatusPill status={gap.status} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* ------------------------------------------------- recommendations -- */}
      {recommendations.length > 0 && (
        <div className="mb-4">
          <Card
            title="What to do next"
            hint="Ranked by a contextual bandit over the catalogue — open a card to see why it was chosen"
            action={
              <Link
                to="/learning"
                className="text-[12.5px] text-accent transition-opacity hover:opacity-80"
              >
                Full development plan →
              </Link>
            }
          >
            <ul className="grid gap-3 lg:grid-cols-3">
              {recommendations.slice(0, 3).map((rec, i) => {
                const open = openReason === rec.id;
                return (
                  <li
                    key={rec.id}
                    className="flex flex-col rounded-lg border border-rule bg-surface-2 p-4 transition-colors hover:border-accent/45"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-accent">
                        #{i + 1} · {rec.course.provider ?? rec.course.source}
                      </span>
                      <span className="tabular shrink-0 font-mono text-[10.5px] text-ink-3">
                        {rec.course.duration_hours}h
                      </span>
                    </div>

                    <h3 className="mt-2 text-[14px] font-semibold leading-snug">
                      {rec.course.title}
                    </h3>
                    <p className="mt-1.5 text-[12px] leading-relaxed text-ink-2">
                      Closes{" "}
                      <span className="text-ink">{rec.competency_name}</span>, where you
                      are at L{rec.current_level.toFixed(2)} against L
                      {rec.required_level.toFixed(2)}.
                    </p>

                    {/* Level band the course covers, against the gap it targets. */}
                    <div className="mt-3">
                      <div className="relative h-1 w-full rounded-full bg-ground">
                        <div
                          className="absolute top-0 h-1 rounded-full bg-accent/70"
                          style={{
                            left: `${(rec.course.level_from / 5) * 100}%`,
                            width: `${((rec.course.level_to - rec.course.level_from) / 5) * 100}%`,
                          }}
                        />
                        <div
                          className="absolute top-[-2px] h-2 w-0.5 rounded bg-ink"
                          style={{ left: `${(rec.current_level / 5) * 100}%` }}
                          title={`You: L${rec.current_level.toFixed(2)}`}
                        />
                        <div
                          className="absolute top-[-2px] h-2 w-0.5 rounded bg-brass"
                          style={{ left: `${(rec.required_level / 5) * 100}%` }}
                          title={`Required: L${rec.required_level.toFixed(2)}`}
                        />
                      </div>
                      <div className="mt-1.5 flex justify-between font-mono text-[9.5px] text-ink-3">
                        <span>covers L{rec.course.level_from}</span>
                        <span>L{rec.course.level_to}</span>
                      </div>
                    </div>

                    <button
                      onClick={() => setOpenReason(open ? null : rec.id)}
                      aria-expanded={open}
                      className="mt-3 self-start text-[11.5px] text-ink-3 transition-colors hover:text-accent"
                    >
                      {open ? "Hide reasoning" : "Why this course?"}
                    </button>
                    {open && (
                      <div className="mt-2 rounded-md border-l-2 border-accent bg-tint-accent p-3">
                        <p className="text-[11.5px] leading-relaxed text-ink-2">
                          {rec.reason}
                        </p>
                        <dl className="mt-2.5 grid grid-cols-2 gap-x-3 gap-y-1 border-t border-rule pt-2 font-mono text-[10px] text-ink-3">
                          {(
                            [
                              ["relevance", rec.signals.relevance],
                              ["level fit", rec.signals.level_fit],
                              ["urgency", rec.signals.urgency],
                              ["peers", rec.signals.peers],
                            ] as const
                          )
                            .filter(([, v]) => typeof v === "number")
                            .map(([name, v]) => (
                              <div key={name} className="flex justify-between gap-2">
                                <dt>{name}</dt>
                                <dd className="tabular text-ink-2">
                                  {(v as number).toFixed(2)}
                                </dd>
                              </div>
                            ))}
                        </dl>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </Card>
        </div>
      )}

      {/* --------------------------------------------------------- movement -- */}
      {lift && lift.summary.measured > 0 && (
        <div className="mb-4">
          <Card
            title={`Movement over the last ${lift.window_days} days`}
            hint={`${lift.summary.improved} improved · ${lift.summary.steady} steady · ${lift.summary.declined} declined · ${lift.summary.evidence_added} new records`}
          >
            <div className="divide-y divide-rule">
              {lift.competencies
                .filter((c) => Math.abs(c.change) >= 0.15)
                .slice(0, 6)
                .map((c) => (
                  <div
                    key={c.competency_id}
                    className="grid grid-cols-[minmax(0,1fr)_150px_110px] items-center gap-3 py-2.5 first:pt-0"
                  >
                    <span className="truncate text-[13.5px]">{c.competency_name}</span>
                    <div className="tabular flex items-center gap-2 font-mono text-[12px] text-ink-3">
                      <span>L{c.level_then.toFixed(2)}</span>
                      <span className="text-rule-strong">→</span>
                      <span className="text-ink">L{c.level_now.toFixed(2)}</span>
                    </div>
                    <span
                      className={`tabular text-right font-mono text-[13px] font-semibold ${
                        c.change > 0 ? "text-good" : "text-critical"
                      }`}
                    >
                      {c.change > 0 ? "+" : ""}
                      {c.change.toFixed(2)}
                    </span>
                  </div>
                ))}
            </div>
            <p className="mt-3 border-t border-rule pt-3 text-[11.5px] leading-relaxed text-ink-3">
              {lift.note}
            </p>
          </Card>
        </div>
      )}

      {/* ------------------------------------------- promotion and evidence -- */}
      <div className="grid gap-3.5 lg:grid-cols-[420px_minmax(0,1fr)]">
        <Card
          title={t("dashboard.promotionReadiness")}
          hint={t("dashboard.promotionHint")}
          action={
            <select
              aria-label="Target role for promotion readiness"
              value={targetRoleId ?? ""}
              onChange={(e) => setTargetRoleId(Number(e.target.value) || null)}
              className="rounded-md border border-rule-strong bg-surface px-2 py-1 text-[12.5px] outline-none focus:border-accent"
            >
              {roles.map((r) => (
                <option key={r.id} value={r.id} className="bg-surface">
                  {r.name}
                </option>
              ))}
            </select>
          }
        >
          {!targetRole ? (
            <Empty>Choose a target role.</Empty>
          ) : (
            <>
              <div className="flex items-center gap-5">
                <ReadinessRing
                  value={targetReadiness}
                  label={`ready for ${targetRole.grade}`}
                  size={104}
                  tone={targetReadiness >= 80 ? "accent" : "warn"}
                />
                <dl className="min-w-0 flex-1 space-y-2 text-[12.5px]">
                  <div className="flex justify-between gap-3">
                    <dt className="text-ink-2">Still short</dt>
                    <dd className="tabular font-mono font-semibold">
                      {targetOpen.length} of {targetGaps.length}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-ink-2">{t("dashboard.serviceRequirement")}</dt>
                    <dd className="tabular font-mono font-semibold">
                      {twin.user.service_years} / {targetRole.min_service_years} yr
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-ink-2">{t("dashboard.eligibility")}</dt>
                    <dd className={`font-semibold ${eligible ? "text-good" : "text-warn"}`}>
                      {eligible ? t("dashboard.eligible") : t("dashboard.notEligible")}
                    </dd>
                  </div>
                </dl>
              </div>

              {targetOpen.length > 0 && (
                <div className="mt-4 border-t border-rule pt-3">
                  <div className="mb-2 text-[10.5px] font-semibold uppercase tracking-[0.09em] text-ink-3">
                    What stands between you and this role
                  </div>
                  <ul className="space-y-1.5 text-[12.5px] text-ink-2">
                    {targetOpen.slice(0, 3).map((g) => (
                      <li key={g.competency_id} className="flex justify-between gap-3">
                        <span className="truncate">{g.competency_name}</span>
                        <span className="tabular shrink-0 font-mono">
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
                <div className="mt-4 rounded-md border border-rule bg-surface-2 p-3">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-[10.5px] font-semibold uppercase tracking-[0.09em] text-ink-3">
                      Forecast
                    </span>
                    <span className="tabular font-mono text-[11px] text-ink-3">
                      {forecast.monthly_rate > 0
                        ? `+${forecast.monthly_rate.toFixed(3)} levels / month`
                        : "no measurable rate"}
                    </span>
                  </div>
                  <p className="mt-2 text-[12px] leading-relaxed text-ink-2">
                    {forecast.slowest?.projected_date ? (
                      <>
                        The binding constraint is{" "}
                        <span className="text-ink">
                          {forecast.slowest.competency_name}
                        </span>
                        , projected to reach target around{" "}
                        <span className="text-brass">
                          {forecast.slowest.projected_date}
                        </span>
                        .
                      </>
                    ) : (
                      <>
                        {forecast.gaps_stalled} of {forecast.open_gaps} open gaps are not
                        moving, so no completion date is projected for them.
                      </>
                    )}
                  </p>
                  <div className="mt-2 flex gap-4 font-mono text-[10.5px] text-ink-3">
                    <span className="text-good">{forecast.gaps_on_track} on track</span>
                    <span className="text-warn">{forecast.gaps_stalled} stalled</span>
                  </div>
                </div>
              )}
            </>
          )}
        </Card>

        <Card title={t("dashboard.evidenceTimeline")} hint={t("dashboard.evidenceTimelineHint")}>
          {evidence.length === 0 ? (
            <Empty>No evidence recorded yet.</Empty>
          ) : (
            <ol className="relative">
              {evidence.map((item, i) => (
                <li key={item.id} className="relative flex items-center gap-4 py-2.5 pl-6">
                  {/* Spine plus node, so the list reads as a chronology rather
                      than a table of unrelated rows. */}
                  <span
                    aria-hidden="true"
                    className={`absolute left-[3px] top-0 w-px bg-rule ${
                      i === 0 ? "top-1/2" : ""
                    } ${i === evidence.length - 1 ? "h-1/2" : "h-full"}`}
                  />
                  <span
                    aria-hidden="true"
                    className={`absolute left-0 top-1/2 h-[7px] w-[7px] -translate-y-1/2 rounded-full ${
                      i === 0 ? "bg-accent" : "bg-rule-strong"
                    }`}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[13px] font-semibold">
                      {competencyNames.get(item.competency_id) ??
                        `Competency ${item.competency_id}`}
                    </div>
                    <div className="mt-0.5 text-[11.5px] text-ink-3">
                      {SOURCE_KEYS[item.source] ? t(SOURCE_KEYS[item.source]) : item.source}
                      {item.confidence < 1 && ` · confidence ${item.confidence}`}
                    </div>
                  </div>
                  <div className="tabular font-mono text-[13px] font-semibold">
                    L{item.level_estimate}
                  </div>
                  <div className="w-24 shrink-0 text-right text-[11.5px] text-ink-3">
                    {timeAgo(item.created_at)}
                  </div>
                </li>
              ))}
            </ol>
          )}
          <div className="mt-4 flex items-start gap-2 border-t border-rule pt-3 text-[11.5px] leading-relaxed text-ink-3">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" className="mt-0.5 shrink-0">
              <rect x="4" y="10" width="16" height="10" rx="1" /><path d="M8 10V7a4 4 0 0 1 8 0v3" />
            </svg>
            Demonstrated work counts for more than course completion, and self-assessment
            counts for least. Corrections are new records, never edits.
          </div>
        </Card>
      </div>
    </>
  );
}
