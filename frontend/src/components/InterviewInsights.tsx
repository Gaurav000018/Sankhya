import { Card, Empty, Note } from "./ui";
import type { Disclosable, InterviewAnalytics } from "../types";

/**
 * Aggregate interview results for a supervisor or administrator.
 *
 * The design problem here is withheld figures. A blank cell reads as "nothing
 * to see", which is the opposite of what suppression means — so a suppressed
 * value is rendered as the word "withheld" with the cohort size next to it, and
 * the reader can tell the difference between "no gap" and "too few people to
 * say".
 *
 * There is no camera data on this screen and none available to it. Officers are
 * told their camera feedback is theirs alone, and the server does not expose it
 * to this endpoint at all.
 */

function Figure({ figure, suffix = "" }: { figure: Disclosable; suffix?: string }) {
  if (figure.suppressed) {
    return (
      <span
        className="text-[13px] text-ink-3"
        title={figure.reason ?? "Withheld: too few officers to publish."}
      >
        withheld
        <span className="ml-1 text-[11px]">({figure.officers})</span>
      </span>
    );
  }
  return (
    <span className="tabular font-mono text-[15px]">
      {figure.value === null ? "—" : figure.value}
      {suffix}
    </span>
  );
}

const AXIS_LABELS: Record<string, string> = {
  knowledge: "Knowledge",
  structure: "Structure",
  communication: "Communication",
  confidence: "Confidence",
};

export function InterviewInsights({ data }: { data: InterviewAnalytics | null }) {
  if (!data) {
    return (
      <Card title="Interview insights">
        <Empty>
          No interviews have been completed yet, or none within your division.
        </Empty>
      </Card>
    );
  }

  const { cohort } = data;

  return (
    <Card
      title="Interview insights"
      hint={`${cohort.officers_interviewed} officer(s), ${cohort.sessions_completed} session(s), ${cohort.answers_scored} answers scored`}
    >
      {cohort.below_disclosure_threshold && (
        <div className="mb-4">
          <Note tone="brass">
            Fewer than {data.disclosure.min_cohort} officers have been interviewed
            here, so the figures below are withheld rather than shown. This is not
            a sign that nothing was found — it is that publishing a mean over this
            few people identifies them.
          </Note>
        </div>
      )}

      <h3 className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
        Mean by axis
      </h3>
      <dl className="mt-2 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {Object.entries(data.axes).map(([axis, figure]) => (
          <div key={axis}>
            <dt className="text-[11.5px] text-ink-2">{AXIS_LABELS[axis] ?? axis}</dt>
            <dd className="mt-0.5">
              <Figure figure={figure} />
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-[11px] leading-relaxed text-ink-3">
        Delivery is deliberately absent: it is not scored for officers who have
        switched it off, so a mean over it would compare two different
        populations without saying so.
      </p>

      {data.weakest_competencies.length > 0 && (
        <div className="mt-5 overflow-x-auto">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
            Where officers struggled
          </h3>
          <table className="mt-2 w-full min-w-[420px] text-[13px]">
            <caption className="sr-only">
              Mean Knowledge per competency across interviews, withheld where too
              few answers were recorded to publish
            </caption>
            <thead>
              <tr className="border-b border-rule text-[11px] uppercase tracking-[0.07em] text-ink-3">
                <th scope="col" className="pb-2 pr-4 text-left font-semibold">Competency</th>
                <th scope="col" className="pb-2 pr-4 text-right font-semibold">Answers</th>
                <th scope="col" className="pb-2 text-right font-semibold">Mean knowledge</th>
              </tr>
            </thead>
            <tbody>
              {data.weakest_competencies.map((row) => (
                <tr key={row.competency_id} className="border-b border-rule last:border-0">
                  <td className="py-2 pr-4">
                    {row.competency_name}
                    {row.is_weak === true && (
                      <span className="ml-2 text-[11px] font-semibold text-warn">
                        below target
                      </span>
                    )}
                  </td>
                  <td className="tabular py-2 pr-4 text-right font-mono text-[12px] text-ink-3">
                    {row.answers}
                  </td>
                  <td className="py-2 text-right">
                    <Figure figure={row.mean_knowledge} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data.most_missed_points.length > 0 && (
        <div className="mt-5">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
            Most missed points
          </h3>
          <ul className="mt-2 space-y-1">
            {data.most_missed_points.slice(0, 6).map((row) => (
              <li key={row.point} className="flex items-baseline gap-2.5 text-[12.5px]">
                <span className="tabular w-8 shrink-0 text-right font-mono text-ink-3">
                  {row.times}×
                </span>
                <span className="text-ink-2">{row.point}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] leading-relaxed text-ink-3">
            A point missed repeatedly across officers is usually a gap in the
            training material rather than in the officers.
          </p>
        </div>
      )}

      <Note>{data.disclosure.note}</Note>
    </Card>
  );
}
