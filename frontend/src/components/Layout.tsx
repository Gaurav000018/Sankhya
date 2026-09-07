import { NavLink, useNavigate } from "react-router-dom";
import type { ReactNode } from "react";

import { ROLE_ROUTES, useAuth } from "../auth";
import { LOCALES, LOCALE_NAMES, useI18n } from "../i18n";
import type { MessageKey } from "../i18n";

const NAV_KEYS: Record<string, MessageKey> = {
  "/": "nav.dashboard",
  "/learning": "nav.learning",
  "/promotion": "nav.promotion",
  "/team": "nav.team",
  "/review": "nav.review",
  "/admin": "nav.workforce",
  "/acbp": "nav.capacityPlan",
  "/quiz": "nav.quiz",
  "/interview": "nav.interview",
  "/settings": "nav.settings",
};

const ROLE_KEYS: Record<string, MessageKey> = {
  learner: "role.learner",
  supervisor: "role.supervisor",
  sme: "role.sme",
  admin: "role.admin",
};

export function Layout({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth();
  const { locale, setLocale, t } = useI18n();
  const navigate = useNavigate();

  const links = (ROLE_ROUTES[user?.role ?? ""] ?? []).filter((p) => p in NAV_KEYS);

  return (
    <div className="min-h-full">
      <a href="#main" className="skip-link">
        {t("nav.skipToContent")}
      </a>
      <header className="bg-navy text-[#eceae4]">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between gap-6 px-6">
          <div className="flex items-center gap-7">
            <div className="flex items-center gap-2.5">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#c9a961" strokeWidth="1.8" strokeLinecap="round">
                <path d="M4 20V13" /><path d="M9.3 20V8" /><path d="M14.7 20V15" /><path d="M20 20V4" />
              </svg>
              <span className="font-serif text-[17px] font-semibold tracking-[0.08em] text-[#f4f2ec]">
                SANKHYA
              </span>
            </div>
            <nav aria-label={t("nav.primary")} className="flex gap-1">
              {links.map((path) => (
                <NavLink
                  key={path}
                  to={path}
                  end={path === "/"}
                  className={({ isActive }) =>
                    `px-2.5 py-1.5 text-[13px] transition-colors ${
                      isActive
                        ? "font-medium text-[#f4f2ec] shadow-[inset_0_-2px_0_#c9a961]"
                        : "text-[#a9b1c2] hover:text-[#f4f2ec]"
                    }`
                  }
                >
                  {t(NAV_KEYS[path])}
                </NavLink>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-3 text-xs text-[#a9b1c2]">
            <label htmlFor="locale" className="sr-only">
              {t("nav.language")}
            </label>
            <select
              id="locale"
              value={locale}
              onChange={(e) => setLocale(e.target.value as typeof locale)}
              className="border border-[#3a4358] bg-transparent px-1.5 py-1 text-[12px] text-[#a9b1c2] focus:border-[#5a6478]"
            >
              {LOCALES.map((code) => (
                <option key={code} value={code} className="text-ink">
                  {LOCALE_NAMES[code]}
                </option>
              ))}
            </select>
            <span className="hidden font-mono tracking-[0.04em] sm:inline">
              MoSPI · {user?.role ? t(ROLE_KEYS[user.role]) : ""}
            </span>
            <button
              onClick={() => {
                signOut();
                navigate("/login");
              }}
              className="border border-[#3a4358] px-2.5 py-1 text-[12px] text-[#a9b1c2] transition-colors hover:border-[#5a6478] hover:text-[#f4f2ec]"
            >
              {t("nav.signOut")}
            </button>
          </div>
        </div>
      </header>

      <main id="main" tabIndex={-1} className="mx-auto max-w-[1400px] px-6 py-7">
        {children}
      </main>
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  meta,
  action,
}: {
  title: string;
  subtitle?: string;
  meta?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1
          tabIndex={-1}
          ref={(node) => {
            // Moving focus to the heading on navigation is what tells a screen
            // reader the page changed. A client-side route change is otherwise
            // silent, and focus stays on whatever link was clicked.
            if (node && node.dataset.focused !== "1") {
              node.dataset.focused = "1";
              node.focus({ preventScroll: true });
            }
          }}
          className="font-serif text-[25px] font-semibold leading-tight tracking-[-0.01em]"
        >
          {title}
        </h1>
        {(subtitle || meta) && (
          <div className="mt-1.5 flex flex-wrap items-center gap-3 text-[13px] text-ink-2">
            {subtitle && <span>{subtitle}</span>}
            {subtitle && meta && <span className="text-rule-strong">|</span>}
            {meta && <span className="font-mono text-[11.5px] text-ink-3">{meta}</span>}
          </div>
        )}
      </div>
      {action}
    </div>
  );
}
