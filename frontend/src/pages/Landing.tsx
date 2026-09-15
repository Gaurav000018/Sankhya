import { Link } from "react-router-dom";

import { useAuth } from "../auth";
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
            ["Services", "#services"],
            ["How it works", "#how"],
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
                  <Link to="/login" className={btnPrimary}>
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
