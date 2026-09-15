import { useEffect, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import type { ReactNode } from "react";

import { ROLE_ROUTES, useAuth } from "../auth";
import { useI18n } from "../i18n";
import type { MessageKey } from "../i18n";
import { BrandBar, Icon, MinistryStrip, PortalFooter, TricolourBand } from "./portal";

const NAV_KEYS: Record<string, MessageKey> = {
  "/dashboard": "nav.dashboard",
  "/journey": "nav.journey",
  "/learning": "nav.learning",
  "/promotion": "nav.promotion",
  "/team": "nav.team",
  "/review": "nav.review",
  "/officers": "nav.officers",
  "/admin": "nav.workforce",
  "/acbp": "nav.capacityPlan",
  "/quiz": "nav.quiz",
  "/interview": "nav.interview",
  "/settings": "nav.settings",
};

const NAV_ICONS: Record<string, string> = {
  "/dashboard": "dashboard",
  "/journey": "journey",
  "/learning": "learning",
  "/promotion": "promotion",
  "/team": "team",
  "/review": "review",
  "/admin": "workforce",
  "/acbp": "capacityPlan",
  "/quiz": "quiz",
  "/interview": "interview",
  "/settings": "settings",
};

/* Sidebar groups, in the order an officer works through them. A route the
   signed-in role cannot open is simply absent, and an empty group is hidden. */
const NAV_GROUPS: { label: string; paths: string[] }[] = [
  { label: "My workspace", paths: ["/dashboard", "/journey", "/learning", "/promotion"] },
  { label: "Assessments", paths: ["/quiz", "/interview"] },
  { label: "Administration", paths: ["/team", "/review", "/admin", "/acbp"] },
  { label: "Account", paths: ["/settings"] },
];

const ROLE_KEYS: Record<string, MessageKey> = {
  learner: "role.learner",
  supervisor: "role.supervisor",
  sme: "role.sme",
  admin: "role.admin",
};

function SideNav({ allowed, onNavigate }: { allowed: Set<string>; onNavigate?: () => void }) {
  const { t } = useI18n();
  return (
    <nav aria-label={t("nav.primary")} className="py-3">
      {NAV_GROUPS.map((group) => {
        const paths = group.paths.filter((p) => allowed.has(p));
        if (paths.length === 0) return null;
        return (
          <div key={group.label} className="mb-3">
            <div className="px-5 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-3">
              {group.label}
            </div>
            <ul>
              {paths.map((path) => (
                <li key={path}>
                  <NavLink
                    to={path}
                    end={path === "/dashboard"}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      `flex items-center gap-3 border-l-[3px] px-5 py-2 text-[13.5px] ${
                        isActive
                          ? "border-accent bg-tint-accent font-semibold text-accent"
                          : "border-transparent text-ink-2 hover:bg-surface-2 hover:text-ink"
                      }`
                    }
                  >
                    <Icon name={NAV_ICONS[path]} />
                    {t(NAV_KEYS[path])}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // The drawer is a mobile affordance; it closes on every navigation.
  useEffect(() => setDrawerOpen(false), [location.pathname]);

  const allowed = new Set((ROLE_ROUTES[user?.role ?? ""] ?? []).filter((p) => p in NAV_KEYS));
  const roleLabel = user?.role ? t(ROLE_KEYS[user.role]) : "";

  const session = (
    <div className="flex items-center gap-3">
      <div className="hidden items-center gap-2.5 text-right md:flex">
        <div className="leading-tight">
          <div className="text-[13px] font-semibold text-ink">{user?.full_name}</div>
          <div className="text-[12px] text-ink-3">{roleLabel}</div>
        </div>
        <span className="flex h-9 w-9 items-center justify-center rounded-full border border-rule bg-surface-2 text-accent">
          <Icon name="user" size={18} />
        </span>
      </div>
      <button
        onClick={() => {
          signOut();
          navigate("/");
        }}
        aria-label={t("nav.signOut")}
        className="inline-flex items-center gap-1.5 whitespace-nowrap rounded border border-rule-strong px-2.5 py-1.5 text-[13px] font-medium text-accent hover:bg-tint-accent sm:px-3"
      >
        <Icon name="signout" size={16} />
        <span className="hidden sm:inline">{t("nav.signOut")}</span>
      </button>
    </div>
  );

  return (
    <div className="flex min-h-full flex-col">
      {/* Rendered here rather than inside the shared header so the bypass link
          is the first focusable element of every signed-in page. */}
      <a href="#main" className="skip-link">
        {t("nav.skipToContent")}
      </a>
      <header className="no-print">
        <MinistryStrip />
        <BrandBar
          right={session}
          left={
            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              aria-label="Open navigation"
              className="rounded border border-rule p-1.5 text-ink-2 lg:hidden"
            >
              <Icon name="menu" size={20} />
            </button>
          }
        />
        <TricolourBand />
      </header>

      <div className="mx-auto flex w-full max-w-[1440px] flex-1">
        <aside className="no-print hidden w-60 shrink-0 border-r border-rule bg-surface lg:block">
          <div className="sticky top-0">
            <SideNav allowed={allowed} />
          </div>
        </aside>

        {drawerOpen && (
          <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
            <button
              type="button"
              aria-label="Close navigation"
              onClick={() => setDrawerOpen(false)}
              className="absolute inset-0 bg-ink/40"
            />
            <div className="relative h-full w-72 max-w-[85%] overflow-y-auto border-r border-rule bg-surface">
              <div className="flex items-center justify-between border-b border-rule px-5 py-3">
                <span className="text-[14px] font-semibold text-accent">Menu</span>
                <button type="button" onClick={() => setDrawerOpen(false)} aria-label="Close navigation" className="p-1 text-ink-2">
                  <Icon name="close" />
                </button>
              </div>
              <SideNav allowed={allowed} onNavigate={() => setDrawerOpen(false)} />
            </div>
          </div>
        )}

        <main id="main" tabIndex={-1} className="min-w-0 flex-1 px-4 py-6 sm:px-8">
          {children}
        </main>
      </div>

      <PortalFooter />
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
    <div className="mb-6 border-b border-rule pb-4">
      <nav aria-label="Breadcrumb" className="mb-2 text-[12.5px] text-ink-3">
        <ol className="flex flex-wrap items-center gap-1">
          <li>
            <Link to="/dashboard" className="text-accent hover:underline">
              Home
            </Link>
          </li>
          <li aria-hidden="true">
            <Icon name="chevron" size={12} />
          </li>
          <li aria-current="page" className="text-ink-2">
            {title}
          </li>
        </ol>
      </nav>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
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
            className="text-[22px] font-semibold leading-tight text-ink"
          >
            {title}
          </h1>
          {(subtitle || meta) && (
            <p className="mt-1 text-[13.5px] text-ink-2">
              {subtitle}
              {subtitle && meta && <span className="mx-2 text-rule-strong">|</span>}
              {meta && <span className="text-ink-3">{meta}</span>}
            </p>
          )}
        </div>
        {action}
      </div>
    </div>
  );
}
