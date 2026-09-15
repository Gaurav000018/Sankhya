/**
 * The questions an evaluator from a data-informatics division actually asks,
 * with the answers the running system gives. Native <details> elements: they
 * are keyboard- and screen-reader-accessible without any script.
 */
const QUESTIONS: { q: string; a: string }[] = [
  {
    q: "How is an officer's competency level worked out?",
    a: "Every quiz, diagnostic, simulation, interview answer and certificate is stored as a dated evidence record. A level is derived from those records, weighted by how trustworthy each kind of source is (a work simulation counts most, a self-rating least) and faded over a 365-day half-life so recent performance matters more. Every level on screen can be traced back to the records behind it.",
  },
  {
    q: "What stops a generated question from being factually wrong?",
    a: "A generated question must quote the passage of the uploaded document it was drawn from, and it is rejected if that quotation cannot be found in the source. It then waits in a review queue, and no officer sees it until a subject-matter expert approves it.",
  },
  {
    q: "How is this different from iGOT Karmayogi?",
    a: "iGOT is the catalogue of courses with completion tracking. SANKHYA works alongside it: it measures what an officer can do, finds the gap against their FRAC role, ranks catalogue courses against that gap, and then reports whether competency actually moved after a course.",
  },
  {
    q: "What happens for an officer with no assessment history?",
    a: "The officer starts from a short self-rating, recorded at the lowest weight, and a diagnostic. Levels resting on thin evidence are marked as not yet confident, so nobody is judged on a single data point.",
  },
  {
    q: "Is the AI interview used to decide promotions?",
    a: "No. The interview reports five separate ratings with no overall score, and only the Knowledge rating is added to the competency record. Mistakes are flagged only against answers approved by a subject-matter expert. Camera analysis runs inside the officer's browser, is shown only to the officer and never affects any score, readiness figure or supervisor view.",
  },
  {
    q: "Where does the data live?",
    a: "The platform runs on-premise with open-weight models, so officer data does not leave government infrastructure and no paid external AI service is required. This prototype contains only synthetic records.",
  },
];

export function Faq() {
  return (
    <div className="divide-y divide-rule rounded border border-rule bg-surface">
      {QUESTIONS.map((item, i) => (
        <details key={item.q} className="group" open={i === 0}>
          <summary className="flex cursor-pointer list-none items-start justify-between gap-4 px-5 py-3.5 text-[14.5px] font-semibold text-ink hover:bg-surface-2 [&::-webkit-details-marker]:hidden">
            <span>
              <span className="tabular mr-2 text-accent">{i + 1}.</span>
              {item.q}
            </span>
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
              className="mt-1 shrink-0 text-accent group-open:rotate-180"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </summary>
          <p className="px-5 pb-4 pl-10 text-[13.5px] leading-relaxed text-ink-2">{item.a}</p>
        </details>
      ))}
    </div>
  );
}
