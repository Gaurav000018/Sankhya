import { useState } from "react";

import { Reveal } from "./Primitives";

/**
 * The questions an evaluator from a data-informatics division actually asks,
 * with the answers the architecture gives. Answering them on the page is
 * cheaper than being asked them in the room.
 */
const QUESTIONS: { q: string; a: string }[] = [
  {
    q: "How do you calibrate item difficulty with no historical response data?",
    a: "A generated item enters the bank with a difficulty prior predicted from its text and Bloom level. As officers answer it, the prior is updated from real responses — Bayesian updating, item by item. Difficulty and discrimination are stored per question and recomputed on demand, so a new item is provisional and says so, and a well-used one is calibrated.",
  },
  {
    q: "What stops the model generating a factually wrong question?",
    a: "Three things in sequence. Generation is retrieval-grounded: the question is written against a retrieved passage and carries a citation to the page it came from. A validation pass rejects items whose distractors are trivially wrong or whose citation cannot be verified in the source. Then nothing reaches an officer until a subject-matter expert approves it in the review queue.",
  },
  {
    q: "How is this different from what iGOT Karmayogi already does?",
    a: "iGOT is a catalogue with completion tracking. This is the matching layer on top of it: it measures what an officer can do, works out what they need, ranks the catalogue against that need, and then measures whether the course changed anything. iGOT stays the system of record for content; SANKHYA becomes the system of record for capability.",
  },
  {
    q: "What happens with an officer who has no assessment history?",
    a: "Cold start is handled twice. The competency estimate starts from a role-based prior rather than zero, and tightens as the first diagnostic comes in. The recommender is a contextual bandit, which explores deliberately when it has no history for a profile — the failure mode of collaborative filtering, where a new officer gets nothing, does not arise.",
  },
  {
    q: "Is the AI scoring the interview?",
    a: "It scores four independent axes — knowledge, structure, communication, fluency — and there is deliberately no composite. The transcript is shown and can be corrected by the officer before scoring; speech recognition is not the last word. Fluency scoring is opt-in per officer, because a disfluency count is not a fair measure for everyone.",
  },
  {
    q: "Can this scale to the whole statistical system?",
    a: "The expensive parts are already outside the request path: generation and speech run on a worker, embeddings are stored in pgvector, and every derived level is recomputed from indexed evidence rows rather than held as mutable state. The seeded system carries 204 officers and ~3,700 records; the shape of the schema does not change at 20,000.",
  },
];

export function Faq() {
  const [open, setOpen] = useState<number>(0);

  return (
    <ul className="divide-y divide-rule rounded-xl border border-rule bg-surface">
      {QUESTIONS.map((item, i) => {
        const isOpen = open === i;
        return (
          <Reveal as="li" key={item.q} delay={i * 60}>
            <button
              type="button"
              aria-expanded={isOpen}
              aria-controls={`faq-${i}`}
              onClick={() => setOpen(isOpen ? -1 : i)}
              className="flex w-full items-start justify-between gap-6 px-5 py-4 text-left transition-colors hover:bg-surface-2/60 sm:px-6"
            >
              <span className="flex items-baseline gap-4">
                <span className="tabular shrink-0 font-mono text-[11px] text-accent">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="text-[15px] font-medium leading-snug">{item.q}</span>
              </span>
              {/* Plus that rotates into a cross. */}
              <span
                aria-hidden="true"
                className="relative mt-1 h-4 w-4 shrink-0 transition-transform duration-300"
                style={{ transform: isOpen ? "rotate(45deg)" : "none" }}
              >
                <span className="absolute left-1/2 top-0 h-4 w-px -translate-x-1/2 bg-ink-2" />
                <span className="absolute left-0 top-1/2 h-px w-4 -translate-y-1/2 bg-ink-2" />
              </span>
            </button>
            {/* 0fr → 1fr is the one way to animate to an unknown height without
                measuring it. */}
            <div
              id={`faq-${i}`}
              className="grid transition-[grid-template-rows] duration-400 ease-[cubic-bezier(0.16,1,0.3,1)]"
              style={{ gridTemplateRows: isOpen ? "1fr" : "0fr" }}
            >
              <div className="overflow-hidden">
                <p className="px-5 pb-5 pl-[calc(1.25rem+1.75rem)] text-[13.5px] leading-relaxed text-ink-2 sm:px-6 sm:pl-[calc(1.5rem+1.75rem)]">
                  {item.a}
                </p>
              </div>
            </div>
          </Reveal>
        );
      })}
    </ul>
  );
}
