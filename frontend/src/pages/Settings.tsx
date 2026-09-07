import { useCallback, useEffect, useState } from "react";

import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import { PageHeader } from "../components/Layout";
import { Card, Empty, ErrorNote, Note, Spinner, StatTile } from "../components/ui";
import { usePageTitle } from "../hooks/usePageTitle";
import { LOCALES, LOCALE_NAMES, useI18n } from "../i18n";

/**
 * Profile settings and the diagnostic self-assessment.
 *
 * The accommodation switch lives here rather than behind a supervisor request:
 * requiring approval to turn off a scoring axis that penalises a speech
 * disability would defeat the purpose of having the switch.
 */

interface DiagnosticCompetency {
  id: number;
  code: string;
  name: string;
  domain: string;
  required_level: number;
  criticality: string;
  already_rated: boolean;
}

interface Diagnostic {
  role: string | null;
  completed: boolean;
  has_any_evidence: boolean;
  level_descriptions: Record<string, string>;
  competencies: DiagnosticCompetency[];
  disclosure: string;
}

export function Settings() {
  usePageTitle("title.settings");
  const { user, signIn } = useAuth();
  const { locale, setLocale } = useI18n();

  const [diagnostic, setDiagnostic] = useState<Diagnostic | null>(null);
  const [ratings, setRatings] = useState<Record<number, number>>({});
  const [fluency, setFluency] = useState(user?.fluency_scoring_enabled ?? true);
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setDiagnostic(await api.get<Diagnostic>("/diagnostic"));
    } catch (e) {
      // A missing FRAC role is a 409 and not an error worth shouting about here.
      if (!(e instanceof ApiError && e.status === 409)) throw e;
    }
  }, []);

  useEffect(() => {
    load()
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load settings."))
      .finally(() => setLoading(false));
  }, [load]);

  useEffect(() => {
    setFluency(user?.fluency_scoring_enabled ?? true);
  }, [user]);

  async function saveFluency(next: boolean) {
    setBusy(true);
    setError(null);
    try {
      await api.patch("/me/settings", { fluency_scoring_enabled: next });
      setFluency(next);
      setSaved(
        next
          ? "Delivery scoring is on."
          : "Delivery scoring is off. Your Knowledge score is unaffected.",
      );
      // Refresh the cached user so other screens agree.
      const token = localStorage.getItem("sankhya.token");
      if (token) await signIn(token);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save that setting.");
    } finally {
      setBusy(false);
    }
  }

  async function submitDiagnostic() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<{ recorded: number; next_step: string }>(
        "/diagnostic",
        {
          ratings: Object.entries(ratings).map(([competency_id, level]) => ({
            competency_id: Number(competency_id),
            level,
          })),
        },
      );
      setSaved(`${result.recorded} ratings recorded. ${result.next_step}`);
      setRatings({});
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not submit the assessment.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Spinner label="Loading" />;

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle={user?.full_name}
        meta={user?.email}
      />

      {error && (
        <div className="mb-4">
          <ErrorNote message={error} />
        </div>
      )}
      {saved && (
        <div className="mb-4">
          <Note>{saved}</Note>
        </div>
      )}

      <div className="mb-4 grid gap-3.5 lg:grid-cols-2">
        <Card title="Interview delivery scoring" hint="Accommodation setting">
          <p className="text-[13px] leading-relaxed text-ink-2">
            The AI interview reports four separate scores. Two of them —
            communication delivery and assurance — are measured from how you
            speak, against your own calibration baseline.
          </p>
          <p className="mt-2.5 text-[13px] leading-relaxed text-ink-2">
            If a speech difference makes those scores unhelpful or unfair, switch
            them off. Your <strong className="text-ink">Knowledge score is not
            affected</strong>, and Knowledge is the only axis recorded against your
            competency profile.
          </p>

          <label className="mt-4 flex cursor-pointer items-start gap-3 border border-rule px-3 py-2.5">
            <input
              type="checkbox"
              id="fluency-scoring"
              checked={fluency}
              disabled={busy}
              onChange={(e) => saveFluency(e.target.checked)}
              className="mt-0.5"
            />
            <span className="text-[13.5px]">
              Score my communication delivery
              <span className="mt-0.5 block text-[11.5px] text-ink-3">
                {fluency
                  ? "On — you will see delivery feedback after each interview."
                  : "Off — delivery and assurance will not be scored."}
              </span>
            </span>
          </label>
        </Card>

        <Card title="Language" hint="Applies to this browser">
          <label htmlFor="settings-locale" className="block text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
            Interface language
          </label>
          <select
            id="settings-locale"
            value={locale}
            onChange={(e) => setLocale(e.target.value as typeof locale)}
            className="mt-1.5 w-full border border-rule-strong bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
          >
            {LOCALES.map((code) => (
              <option key={code} value={code}>
                {LOCALE_NAMES[code]}
              </option>
            ))}
          </select>
          <p className="mt-2.5 text-[12px] leading-relaxed text-ink-3">
            Hindi coverage is complete for the interface. Competency names and
            course titles come from the catalogue and remain in English.
          </p>
        </Card>
      </div>

      {diagnostic && (
        <Card
          title="Diagnostic self-assessment"
          hint={
            diagnostic.completed
              ? "You have done this before — re-rating adds new records rather than replacing the old ones"
              : "Populates your profile so it is not empty while you are assessed properly"
          }
          action={
            Object.keys(ratings).length > 0 ? (
              <button
                disabled={busy}
                onClick={submitDiagnostic}
                className="bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {busy ? "Saving…" : `Save ${Object.keys(ratings).length} rating(s)`}
              </button>
            ) : undefined
          }
        >
          <div className="mb-4">
            <Note tone="brass">{diagnostic.disclosure}</Note>
          </div>

          <div className="mb-4 grid gap-2 sm:grid-cols-5">
            {Object.entries(diagnostic.level_descriptions).map(([level, description]) => (
              <div key={level} className="border border-rule px-2.5 py-2">
                <div className="tabular font-mono text-[13px] font-semibold">L{level}</div>
                <div className="mt-1 text-[11px] leading-snug text-ink-2">{description}</div>
              </div>
            ))}
          </div>

          {diagnostic.competencies.length === 0 ? (
            <Empty>No competencies are defined for your role.</Empty>
          ) : (
            <div className="divide-y divide-rule">
              {diagnostic.competencies.map((competency) => (
                <div
                  key={competency.id}
                  className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 py-3 first:pt-0"
                >
                  <div className="min-w-0">
                    <div className="text-[13.5px] font-semibold">{competency.name}</div>
                    <div className="tabular mt-0.5 font-mono text-[11px] text-ink-3">
                      role requires L{competency.required_level}
                      {competency.already_rated && " · previously rated"}
                    </div>
                  </div>
                  <fieldset className="flex gap-1">
                    <legend className="sr-only">
                      Your level for {competency.name}
                    </legend>
                    {[1, 2, 3, 4, 5].map((level) => {
                      const id = `c${competency.id}-l${level}`;
                      const chosen = ratings[competency.id] === level;
                      return (
                        <label
                          key={level}
                          htmlFor={id}
                          title={diagnostic.level_descriptions[String(level)]}
                          className={`tabular cursor-pointer border px-2.5 py-1 font-mono text-[12px] transition-colors ${
                            chosen
                              ? "border-accent bg-accent text-white"
                              : "border-rule-strong text-ink-2 hover:border-accent"
                          }`}
                        >
                          <input
                            type="radio"
                            id={id}
                            name={`competency-${competency.id}`}
                            checked={chosen}
                            onChange={() =>
                              setRatings((prev) => ({ ...prev, [competency.id]: level }))
                            }
                            className="sr-only"
                          />
                          {level}
                        </label>
                      );
                    })}
                  </fieldset>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {!diagnostic && (
        <Card title="Diagnostic self-assessment">
          <Empty>
            No FRAC role is assigned to your account, so there is nothing to assess
            against. Ask your division administrator.
          </Empty>
        </Card>
      )}

      <div className="mt-4">
        <StatTile
          label="Account"
          value={user?.role ?? "—"}
          note={`${user?.service_years ?? 0} years of service`}
        />
      </div>
    </>
  );
}
