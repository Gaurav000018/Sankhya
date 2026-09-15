import { Link } from "react-router-dom";
import type { ReactNode } from "react";

import { LOCALES, LOCALE_NAMES, useI18n } from "../i18n";

/*
 * Portal chrome shared by the signed-in workspace, the public home page and the
 * sign-in screens: a thin ministry strip, the product bar, a tricolour rule and
 * a plain footer. Kept in one place so every screen carries the same identity.
 *
 * This is a hackathon prototype, and the strip and footer say so. It uses no
 * national emblem and does not present itself as an official Government site.
 */

export function SankhyaMark({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <rect x="0.5" y="0.5" width="39" height="39" rx="4" fill="var(--color-accent)" />
      <rect x="9" y="22" width="4.5" height="9" fill="#ffffff" />
      <rect x="17.75" y="15" width="4.5" height="16" fill="#ffffff" />
      <rect x="26.5" y="9" width="4.5" height="22" fill="var(--color-saffron)" />
    </svg>
  );
}

export function TricolourBand() {
  return (
    <div aria-hidden="true" className="flex h-[3px]">
      <span className="flex-1 bg-saffron" />
      <span className="flex-1 bg-white" />
      <span className="flex-1 bg-india-green" />
    </div>
  );
}

/** The thin top strip: ministry, prototype notice, language, skip link. */
export function MinistryStrip() {
  const { locale, setLocale, t } = useI18n();
  return (
    <div className="bg-navy-900 text-[12px] text-white">
      <div className="mx-auto flex h-8 max-w-[1440px] items-center justify-between gap-4 px-4 sm:px-6">
        <span className="truncate">
          <span lang="hi">सांख्यिकी और कार्यक्रम कार्यान्वयन मंत्रालय</span>
          <span className="mx-2 text-white/60">|</span>
          <span>Ministry of Statistics and Programme Implementation</span>
        </span>
        <div className="flex shrink-0 items-center gap-3">
          <a href="#main" className="hidden text-white/85 underline-offset-2 hover:underline sm:inline">
            {t("nav.skipToContent")}
          </a>
          <span className="hidden text-white/60 sm:inline">|</span>
          <label htmlFor="portal-locale" className="sr-only">
            {t("nav.language")}
          </label>
          <select
            id="portal-locale"
            value={locale}
            onChange={(e) => setLocale(e.target.value as typeof locale)}
            className="rounded-sm border border-white/40 bg-navy-900 px-1.5 py-0.5 text-[12px] text-white"
          >
            {LOCALES.map((code) => (
              <option key={code} value={code}>
                {LOCALE_NAMES[code]}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}

/** Product identity bar. `right` carries sign-in or the officer's session. */
export function BrandBar({ right, left }: { right?: ReactNode; left?: ReactNode }) {
  return (
    <div className="border-b border-rule bg-surface">
      <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between gap-4 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          {left}
          <Link to="/" className="flex min-w-0 items-center gap-3" aria-label="SANKHYA home">
            <SankhyaMark />
            <span className="min-w-0 leading-tight">
              <span className="block text-[18px] font-bold tracking-[0.06em] text-accent">
                SANKHYA
              </span>
              <span className="block truncate text-[12px] text-ink-3">
                Competency Management Portal for Statistical Officers
              </span>
            </span>
          </Link>
        </div>
        {right}
      </div>
    </div>
  );
}

export function PortalFooter() {
  return (
    <footer className="no-print mt-10 border-t border-rule bg-surface">
      <div className="mx-auto grid max-w-[1440px] gap-6 px-4 py-6 text-[12.5px] text-ink-3 sm:px-6 md:grid-cols-[1fr_auto]">
        <div className="space-y-1">
          <p className="font-semibold text-ink-2">SANKHYA · Competency Management Portal</p>
          <p>
            Prototype developed for Smart India Hackathon 2026, problem statement SIH26101
            (MoSPI). Not an official Government of India website. All officer data shown is
            synthetic.
          </p>
        </div>
        <ul className="flex flex-wrap items-start gap-x-5 gap-y-1">
          <li>
            <a href="https://www.mospi.gov.in" className="hover:text-accent hover:underline" rel="noreferrer" target="_blank">
              mospi.gov.in
            </a>
          </li>
          <li>
            <a href="https://igotkarmayogi.gov.in" className="hover:text-accent hover:underline" rel="noreferrer" target="_blank">
              iGOT Karmayogi
            </a>
          </li>
          <li>
            <a href="https://nssta.gov.in" className="hover:text-accent hover:underline" rel="noreferrer" target="_blank">
              NSSTA
            </a>
          </li>
        </ul>
      </div>
    </footer>
  );
}

/* ------------------------------------------------------------------ icons -- */

const ICON_PATHS: Record<string, ReactNode> = {
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="8" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="15" width="7" height="6" rx="1" />
    </>
  ),
  journey: (
    <>
      <circle cx="6" cy="18" r="2" />
      <circle cx="18" cy="6" r="2" />
      <path d="M8 18h5a3 3 0 0 0 0-6h-2a3 3 0 0 1 0-6h5" />
    </>
  ),
  learning: (
    <>
      <path d="M3 5.5A1.5 1.5 0 0 1 4.5 4H10a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H3z" />
      <path d="M21 5.5A1.5 1.5 0 0 0 19.5 4H14a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h7z" />
    </>
  ),
  promotion: (
    <>
      <path d="M4 20h16" />
      <path d="M7 16v-4M12 16V8M17 16V5" />
    </>
  ),
  team: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 20a6 6 0 0 1 12 0" />
      <path d="M16 4.5a3 3 0 0 1 0 6M18 14a5 5 0 0 1 3 6" />
    </>
  ),
  review: (
    <>
      <path d="M9 4h6a1 1 0 0 1 1 1v1H8V5a1 1 0 0 1 1-1z" />
      <path d="M8 5H6a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1h-2" />
      <path d="m9 14 2 2 4-4" />
    </>
  ),
  workforce: (
    <>
      <path d="M3 21h18" />
      <path d="M5 21V10l7-5 7 5v11" />
      <path d="M9 21v-6h6v6" />
    </>
  ),
  capacityPlan: (
    <>
      <rect x="4" y="4" width="16" height="17" rx="1" />
      <path d="M4 9h16M9 4v5M8 13h3M8 17h6" />
    </>
  ),
  quiz: (
    <>
      <rect x="4" y="3" width="16" height="18" rx="1" />
      <path d="m8 9 1.5 1.5L12 8M8 15l1.5 1.5L12 14M14 9.5h3M14 15.5h3" />
    </>
  ),
  interview: (
    <>
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" />
    </>
  ),
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  close: <path d="M6 6l12 12M18 6 6 18" />,
  chevron: <path d="m9 6 6 6-6 6" />,
  signout: (
    <>
      <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3" />
      <path d="M10 17l5-5-5-5M15 12H4" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </>
  ),
};

export function Icon({
  name,
  size = 18,
  className = "",
}: {
  name: keyof typeof ICON_PATHS | string;
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={`shrink-0 ${className}`}
    >
      {ICON_PATHS[name] ?? ICON_PATHS.dashboard}
    </svg>
  );
}

/** Chrome for public screens: the home page, sign-in and account recovery. */
export function PublicShell({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex min-h-full flex-col">
      <header>
        <MinistryStrip />
        <BrandBar
          right={
            right ?? (
              <Link
                to="/"
                className="rounded border border-rule-strong px-3 py-1.5 text-[13px] font-medium text-accent hover:bg-tint-accent"
              >
                Home
              </Link>
            )
          }
        />
        <TricolourBand />
      </header>
      <main id="main" tabIndex={-1} className="flex-1">
        {children}
      </main>
      <PortalFooter />
    </div>
  );
}
