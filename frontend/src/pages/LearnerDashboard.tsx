import { useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../api";
import { PageHeader } from "../components/Layout";
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
  SourceTag,
  Spinner,
  StatTile,
  StatusPill,
} from "../components/ui";
import type {
  Divergence,
  Evidence,
  FracRole,
  Gap,
  LiftSummary,
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

export function LearnerDashboard() {
  const t = useT();
  usePageTitle("title.dashboard");

  const [twin, setTwin] = useState<SkillTwin | null>(null);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [divergence, setDivergence] = useState<Divergence[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [roles, setRoles] = useState<FracRole[]>([]);
  const [targetRoleId, setTargetRoleId] = useState<number | null>(null);
  const [targetGaps, setTargetGaps] = useState<Gap[]>([]);
  const [lift, setLift] = useState<LiftSummary | null>(null);
  const [reportHash, setReportHash] = useState<string | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
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

        // Default the promotion view to the next rung up.
        const current = roleList.find((x) => x.id === skillTwin.user.frac_role_id);
        const next = roleList.find(
          (x) => x.level_order === (current?.level_order ?? 0) + 1,
        );
        if (next) setTargetRoleId(next.id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load your profile.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!targetRoleId) return;
    api
      .get<Gap[]>(`/gaps/me?target_role_id=${targetRoleId}`)
      .then(setTargetGaps)
      .catch(() => setTargetGaps([]));
  }, [targetRoleId]);

  const competencyNames = useMemo(
    () => new Map(gaps.map((g) => [g.competency_id, g.competency_name])),
    [gaps],
  );

  const openGaps = gaps.filter((g) => g.gap > 0.1);
  const atTarget = gaps.length - openGaps.length;
  const critical = gaps.filter((g) => g.status === "critical").length;
  const totalEvidence = twin?.competencies.reduce((n, c) => n + c.evidence_count, 0) ?? 0;

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

  return (
    <>
      <PageHeader
        title={twin.user.full_name}
        subtitle={twin.role_name ?? "Role not assigned"}
        meta={`${twin.user.service_years} ${t("dashboard.years")} · ${twin.user.email}`}
        action={
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
              className="border border-rule-strong px-4 py-2 text-sm text-ink-2 transition-colors hover:border-accent hover:text-ink disabled:opacity-50"
            >
              {reportBusy ? t("dashboard.reportGenerating") : t("dashboard.report")}
            </button>
            {reportHash && (
              <div className="mt-1.5 font-mono text-[10px] text-ink-3">
                verification {reportHash.slice(0, 16)}…
              </div>
            )}
          </div>
        }
      />

      <div className="mb-4 grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label={t("dashboard.roleReadiness")}
          value={twin.role_readiness}
          unit="%"
          note={t("dashboard.roleReadinessNote")}
        />
        <StatTile
          label={t("dashboard.atTarget")}
          value={atTarget}
          unit={`${t("common.of")} ${gaps.length} ${t("dashboard.competencies")}`}
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
          value={
            [...twin.competencies].sort((a, b) => b.level - a.level)[0]?.competency_code ?? "—"
          }
          note={`L${[...twin.competencies].sort((a, b) => b.level - a.level)[0]?.level ?? 0}`}
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
                      className={gap.status === "critical" ? "font-semibold text-critical" : "font-semibold"}
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

      <div className="grid gap-3.5 lg:grid-cols-[420px_minmax(0,1fr)]">
        <Card
          title={t("dashboard.promotionReadiness")}
          hint={t("dashboard.promotionHint")}
          action={
            <select
              aria-label="Target role for promotion readiness"
              value={targetRoleId ?? ""}
              onChange={(e) => setTargetRoleId(Number(e.target.value) || null)}
              className="border border-rule-strong bg-surface px-2 py-1 text-[12.5px] outline-none focus:border-accent"
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
            <>
              <div className="flex items-baseline gap-3">
                <span className="tabular font-mono text-[32px] font-medium leading-none">
                  {targetReadiness}
                </span>
                <span className="text-sm text-ink-3">% ready for {targetRole.name}</span>
              </div>
              <div className="mt-3 h-1.5 w-full bg-surface-2">
                <div className="h-1.5 bg-accent" style={{ width: `${targetReadiness}%` }} />
              </div>

              <dl className="mt-4 space-y-2 text-[13px]">
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-2">Competencies still short</dt>
                  <dd className="tabular font-mono font-semibold">
                    {targetOpen.length} of {targetGaps.length}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-2">{t("dashboard.serviceRequirement")}</dt>
                  <dd className="tabular font-mono font-semibold">
                    {twin.user.service_years} / {targetRole.min_service_years} years
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-2">{t("dashboard.eligibility")}</dt>
                  <dd className={`font-semibold ${eligible ? "text-good" : "text-warn"}`}>
                    {eligible ? t("dashboard.eligible") : t("dashboard.notEligible")}
                  </dd>
                </div>
              </dl>

              {targetOpen.length > 0 && (
                <div className="mt-4 border-t border-rule pt-3">
                  <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
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
            </>
          )}
        </Card>

        <Card title={t("dashboard.evidenceTimeline")} hint={t("dashboard.evidenceTimelineHint")}>
          {evidence.length === 0 ? (
            <Empty>No evidence recorded yet.</Empty>
          ) : (
            <div className="divide-y divide-rule">
              {evidence.map((item) => (
                <div key={item.id} className="flex items-center gap-4 py-2.5 first:pt-0">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[13px] font-semibold">
                      {competencyNames.get(item.competency_id) ?? `Competency ${item.competency_id}`}
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
                </div>
              ))}
            </div>
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
