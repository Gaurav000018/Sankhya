import { Link } from "react-router-dom";

import { useAuth } from "../auth";
import { DemoAccess } from "../components/DemoAccess";
import { Faq } from "../components/landing/Faq";
import { Icon, PublicShell } from "../components/portal";
import { btnPrimary, btnSecondary } from "../components/ui";
import { usePageTitle } from "../hooks/usePageTitle";

const SERVICES: { icon: string; title: string; body: string; role: string }[] = [
  {
    icon: "dashboard",
    title: "Digital Skill Twin",
    body: "Your level in each of 12 FRAC competencies, derived from dated evidence and traceable to its records.",
    role: "All officers",
  },
  {
    icon: "quiz",
    title: "Competency assessments",
    body: "Quizzes drawn from an SME-approved question bank, with explanations after submission.",
    role: "All officers",
  },
  {
    icon: "interview",
    title: "AI interview practice",
    body: "Role-based spoken or typed interviews with ratings, key-term coverage and flagged mistakes.",
    role: "All officers",
  },
  {
    icon: "learning",
    title: "Learning recommendations",
    body: "iGOT and NSSTA courses ranked against your measured gaps, in prerequisite order.",
    role: "All officers",
  },
  {
    icon: "promotion",
    title: "Promotion readiness",
    body: "Distance to the next post, a what-if simulator for chosen courses, and a forecast.",
    role: "All officers",
  },
  {
    icon: "review",
    title: "Question generation and review",
    body: "Questions generated from uploaded circulars and manuals, each citing its source, approved by an SME.",
    role: "Subject experts",
  },
  {
    icon: "team",
    title: "Team competency view",
    body: "Where a division stands against role requirements, competency by competency.",
    role: "Supervisors",
  },
  {
    icon: "workforce",
    title: "Workforce analytics and ACBP",
    body: "Capacity-building priorities, observed course effect and a draft Annual Capacity Building Plan.",
    role: "Administrators",
  },
];

const FIGURES: [string, string][] = [
  ["12", "FRAC competencies"],
  ["4", "competency domains"],
  ["6", "role grades"],
  ["8", "divisions"],
  ["21", "catalogue courses"],
];

const MATERIAL_STEPS: { title: string; body: string }[] = [
  {
    title: "Upload the source.",
    body: "A circular, a manual, a training deck or a recorded lecture. PDF, Word, PowerPoint and audio are read directly.",
  },
  {
    title: "Questions are generated with citations.",
    body: "Each multiple-choice question carries the page and the exact sentence it was drawn from, plus an explanation and a reason for every wrong option.",
  },
  {
    title: "Unverifiable questions are discarded.",
    body: "If the quoted sentence cannot be found in the passage, the question is thrown away before any person sees it.",
  },
  {
    title: "A subject expert approves or rejects.",
    body: "Only approved questions ever reach an officer, and the reviewer sees the source passage next to the question.",
  },
  {
    title: "Difficulty is re-estimated from real answers.",
    body: "Once 25 officers have attempted an item, its difficulty is re-fitted from how they actually answered rather than from the author's guess.",
  },
];

const REFERENCES: { name: string; body: string; href?: string }[] = [
  {
    name: "Mission Karmayogi and the FRAC framework",
    body: "supplies the roles, activities and competencies every level on this portal is measured against, and the Annual Capacity Building Plan it must produce.",
    href: "https://cbc.gov.in",
  },
  {
    name: "iGOT Karmayogi",
    body: "supplies the course catalogue and the competency taxonomy that recommendations are drawn from.",
    href: "https://igotkarmayogi.gov.in",
  },
  {
    name: "NSSTA",
    body: "supplies the TPAC-recommended training programmes offered alongside iGOT courses.",
    href: "https://nssta.gov.in",
  },
  {
    name: "MoSPI",
    body: "supplies the divisions, job roles and statistical products the competency vocabulary is written around.",
    href: "https://www.mospi.gov.in",
  },
  {
    name: "Bhashini, MeitY",
    body: "supplies Indian-language speech recognition, translation and speech output, so an officer can be assessed in their own language.",
    href: "https://bhashini.gov.in",
  },
  {
    name: "Parichay, NIC",
    body: "supplies the government's own single sign-on for officials, replacing the password login in a real deployment.",
    href: "https://parichay.nic.in",
  },
  {
    name: "GIGW 3.0 and WCAG 2.1 AA",
    body: "set the accessibility rules this portal is checked against on every build.",
  },
  {
    name: "Item response theory",
    body: "supplies the measurement model. Lord (1980) and van der Linden and Glas (2010) on adaptive testing; the three-parameter model is used here because a four-option question can be guessed.",
  },
];

const STEPS: { title: string; body: string }[] = [
  { title: "Sign in", body: "Use your official email with a password, one-time code or authenticator app." },
  { title: "Get assessed", body: "Take a quiz or an interview. Each result is added to your evidence record." },
  { title: "Review your gaps", body: "See your level against your role requirement for every competency." },
  { title: "Follow your plan", body: "Complete recommended courses; your record shows whether you improved." },
];

const NOTICES: { date: string; text: string }[] = [
  { date: "15 Sep 2026", text: "Interview practice now flags mistakes against approved answers and shows key-term coverage." },
  { date: "15 Sep 2026", text: "Guided journey added for officers using the portal for the first time." },
  { date: "14 Sep 2026", text: "Sign-in with Google is available where the deployment enables it." },
  { date: "08 Sep 2026", text: "Live speech feedback during interviews, processed in the browser." },
];

const ROLES: [string, string][] = [
  ["Officer", "Own competency record, assessments, interview practice, learning plan and promotion readiness."],
  ["Supervisor", "Everything an officer has, plus the competency position of their division."],
  ["Subject-matter expert", "Upload source material and approve or reject generated questions."],
  ["Administrator", "Workforce analytics, course effect and the draft capacity building plan."],
];

export function Landing() {
  usePageTitle("title.landing");
  const { user } = useAuth();

  const headerAction = user ? (
    <Link to="/dashboard" className={btnPrimary}>
      Go to dashboard
    </Link>
  ) : (
    <div className="flex items-center gap-2">
      <Link to="/register" className="hidden text-[13.5px] font-medium text-accent hover:underline sm:inline">
        Register
      </Link>
      <Link to="/login" className={btnPrimary}>
        Officer login
      </Link>
    </div>
  );

  return (
    <PublicShell right={headerAction}>
      {/* Section menu, in the portal pattern of a plain navy bar. */}
      <nav aria-label="Sections" className="bg-accent">
        <ul className="mx-auto flex max-w-[1440px] overflow-x-auto px-2 text-[13.5px] text-white sm:px-4">
          {[
            ["Home", "#top"],
            ["Live demonstration", "#demo"],
            ["Services", "#services"],
            ["How it works", "#how"],
            ["Reference material", "#material"],
            ["Who can use it", "#roles"],
            ["FAQs", "#faq"],
          ].map(([label, href]) => (
            <li key={href}>
              <a href={href} className="block whitespace-nowrap px-4 py-2.5 hover:bg-accent-strong">
                {label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <div id="top" className="mx-auto max-w-[1440px] space-y-10 px-4 py-8 sm:px-6">
        {/* ------------------------------------------------ introduction -- */}
        <section className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <div className="rounded border border-rule bg-surface p-6 sm:p-8">
            <p className="text-[13px] font-semibold text-accent">
              Aligned with Mission Karmayogi and the FRAC competency framework
            </p>
            <h1 className="mt-2 text-[26px] font-bold leading-tight text-ink sm:text-[30px]">
              Competency Management Portal for Officers of the Statistical System
            </h1>
            <p className="mt-3 max-w-[64ch] text-[15px] leading-relaxed text-ink-2">
              SANKHYA measures what each officer can actually do, identifies the gap against their
              job role, recommends the iGOT Karmayogi course that closes it, and turns departmental
              training material into reviewed assessments.
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              {user ? (
                <Link to="/dashboard" className={btnPrimary}>
                  Go to your dashboard
                </Link>
              ) : (
                <>
                  <a href="#demo" className={btnPrimary}>
                    Open the live demonstration
                  </a>
                  <Link to="/login" className={btnSecondary}>
                    Officer login
                  </Link>
                  <Link to="/register" className={btnSecondary}>
                    New registration
                  </Link>
                </>
              )}
            </div>
            <dl className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded border border-rule bg-rule sm:grid-cols-5">
              {FIGURES.map(([value, label]) => (
                <div key={label} className="bg-surface-2 px-3 py-3 text-center">
                  <dt className="sr-only">{label}</dt>
                  <dd>
                    <span className="tabular block text-[22px] font-bold text-accent">{value}</span>
                    <span className="block text-[12px] text-ink-3">{label}</span>
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          <aside aria-labelledby="notices" className="rounded border border-rule bg-surface">
            <h2 id="notices" className="border-b border-rule bg-surface-2 px-4 py-2.5 text-[14.5px] font-semibold text-ink">
              What&rsquo;s new
            </h2>
            <ul className="divide-y divide-rule">
              {NOTICES.map((n) => (
                <li key={n.text} className="px-4 py-3">
                  <div className="tabular text-[12px] font-semibold text-accent">{n.date}</div>
                  <p className="mt-0.5 text-[13.5px] leading-snug text-ink-2">{n.text}</p>
                </li>
              ))}
            </ul>
            <p className="border-t border-rule px-4 py-2.5 text-[12px] text-ink-3">
              Prototype for Smart India Hackathon 2026 · synthetic data
            </p>
          </aside>
        </section>

        {/* ------------------------------------------- live demonstration -- */}
        <section id="demo" aria-labelledby="demo-h" className="scroll-mt-4">
          <h2 id="demo-h" className="border-b border-rule pb-2 text-[19px] font-semibold text-ink">
            Live demonstration
          </h2>
          <p className="mt-3 max-w-[92ch] text-[14.5px] leading-relaxed text-ink-2">
            Open the portal as any of the four roles, with no sign-up. Every account is already carrying a
            complete record: assessments taken, an interview scored, evidence accumulated over twelve months,
            gaps measured against the role it holds. Start with the officer to see one person end to end, then
            open the administrator to see the same evidence aggregated across the workforce.
          </p>
          <div className="mt-4">
            <DemoAccess />
          </div>
        </section>

        {/* ---------------------------------------------------- services -- */}
        <section id="services" aria-labelledby="services-h" className="scroll-mt-4">
          <h2 id="services-h" className="border-b border-rule pb-2 text-[19px] font-semibold text-ink">
            Services on the portal
          </h2>
          <ul className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {SERVICES.map((s) => (
              <li key={s.title} className="flex flex-col rounded border border-rule bg-surface p-4">
                <span className="flex h-10 w-10 items-center justify-center rounded border border-rule bg-tint-accent text-accent">
                  <Icon name={s.icon} size={22} />
                </span>
                <h3 className="mt-3 text-[15px] font-semibold text-ink">{s.title}</h3>
                <p className="mt-1 flex-1 text-[13.5px] leading-relaxed text-ink-2">{s.body}</p>
                <p className="mt-3 border-t border-rule pt-2 text-[12px] text-ink-3">For: {s.role}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* ----------------------------------------------- how it works -- */}
        <section id="how" aria-labelledby="how-h" className="scroll-mt-4">
          <h2 id="how-h" className="border-b border-rule pb-2 text-[19px] font-semibold text-ink">
            How it works
          </h2>
          <ol className="mt-4 grid gap-4 md:grid-cols-4">
            {STEPS.map((step, i) => (
              <li key={step.title} className="rounded border border-rule bg-surface p-4">
                <div className="flex items-center gap-2.5">
                  <span className="tabular flex h-7 w-7 items-center justify-center rounded-full bg-accent text-[13px] font-semibold text-white">
                    {i + 1}
                  </span>
                  <h3 className="text-[15px] font-semibold text-ink">{step.title}</h3>
                </div>
                <p className="mt-2 text-[13.5px] leading-relaxed text-ink-2">{step.body}</p>
              </li>
            ))}
          </ol>
          <figure className="mt-6 rounded border border-rule bg-surface p-4">
            <figcaption className="text-[15px] font-semibold text-ink">System architecture</figcaption>
            <p className="mt-1 text-[13.5px] leading-relaxed text-ink-2">
              Every assessment, interview, uploaded document and supervisor rating is appended to one evidence
              record per officer. Competency levels, gaps and readiness are derived from that record, a
              recommender ranks iGOT Karmayogi courses against the gaps, and a completed course feeds back as
              new evidence. Nothing writes a level directly. Government services are reached through pluggable
              adapters: Bhashini for Indian-language speech and translation, iGOT Karmayogi for the course
              catalogue, Parichay for single sign-on, and API Setu for verifying a claimed certificate.
            </p>
            <div className="mt-3 overflow-x-auto">
              <img
                src="/architecture.svg"
                alt="SANKHYA architecture: users and the React portal on the left, the FastAPI service with evidence sources, the append-only evidence record, derived competency profile, gap analysis and recommender in the middle, and PostgreSQL, Redis, the speech worker, the LLM judge and the iGOT adapter on the right."
                className="min-w-[960px] w-full"
                width={1600}
                height={900}
              />
            </div>
          </figure>
        </section>

        {/* -------------------------------------------- reference material -- */}
        <section id="material" aria-labelledby="material-h" className="scroll-mt-4">
          <h2 id="material-h" className="border-b border-rule pb-2 text-[19px] font-semibold text-ink">
            Reference material
          </h2>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div className="rounded border border-rule bg-surface p-5">
              <h3 className="text-[15.5px] font-semibold text-ink">Material the portal learns from</h3>
              <p className="mt-2 text-[13.5px] leading-relaxed text-ink-2">
                A department already owns the material an assessment should be built from. Upload it and the
                questions come back written, cited and ready for review, so nobody writes a question bank by hand.
              </p>
              <ol className="mt-3 space-y-2.5">
                {MATERIAL_STEPS.map((s, i) => (
                  <li key={s.title} className="flex gap-2.5">
                    <span className="tabular mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent text-[11px] font-semibold text-white">
                      {i + 1}
                    </span>
                    <p className="text-[13.5px] leading-snug text-ink-2">
                      <span className="font-semibold text-ink">{s.title}</span> {s.body}
                    </p>
                  </li>
                ))}
              </ol>
              <p className="mt-3 border-t border-rule pt-3 text-[13px] leading-relaxed text-ink-2">
                Subject experts upload and review from the{" "}
                <span className="font-semibold text-ink">Review queue</span> inside the portal. Open the
                demonstration as a subject expert above to see a generated question beside the passage it came from.
              </p>
            </div>

            <div className="rounded border border-rule bg-surface p-5">
              <h3 className="text-[15.5px] font-semibold text-ink">Standards and sources it is built on</h3>
              <p className="mt-2 text-[13.5px] leading-relaxed text-ink-2">
                Nothing here is invented. Roles, competencies, courses and accessibility rules come from published
                government material, and the measurement model comes from the literature on adaptive testing.
              </p>
              <ul className="mt-3 divide-y divide-rule border-t border-rule">
                {REFERENCES.map((r) => (
                  <li key={r.name} className="py-2.5">
                    <p className="text-[13.5px] leading-snug text-ink-2">
                      {r.href ? (
                        <a
                          href={r.href}
                          className="font-semibold text-accent underline underline-offset-2 hover:text-accent-strong"
                          rel="noreferrer noopener"
                          target="_blank"
                        >
                          {r.name}
                        </a>
                      ) : (
                        <span className="font-semibold text-ink">{r.name}</span>
                      )}{" "}
                      {r.body}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------- roles -- */}
        <section id="roles" aria-labelledby="roles-h" className="scroll-mt-4">
          <h2 id="roles-h" className="border-b border-rule pb-2 text-[19px] font-semibold text-ink">
            Who can use the portal
          </h2>
          <div className="mt-4 overflow-x-auto rounded border border-rule bg-surface">
            <table className="data-table min-w-[560px]">
              <thead>
                <tr>
                  <th scope="col" className="w-56">User type</th>
                  <th scope="col">What they can do</th>
                </tr>
              </thead>
              <tbody>
                {ROLES.map(([role, what]) => (
                  <tr key={role}>
                    <th scope="row" className="!bg-surface font-semibold text-ink">
                      {role}
                    </th>
                    <td className="text-ink-2">{what}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* --------------------------------------------------------- faq -- */}
        <section id="faq" aria-labelledby="faq-h" className="scroll-mt-4">
          <h2 id="faq-h" className="border-b border-rule pb-2 text-[19px] font-semibold text-ink">
            Frequently asked questions
          </h2>
          <div className="mt-4">
            <Faq />
          </div>
        </section>
      </div>
    </PublicShell>
  );
}
