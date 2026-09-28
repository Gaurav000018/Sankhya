import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import { Icon } from "./portal";
import { ErrorNote } from "./ui";

/**
 * One-click entry to the four seeded demonstration accounts.
 *
 * Someone evaluating this should not have to copy an address and a password out
 * of a README before they can see anything. These accounts are public fixtures
 * over synthetic data and the sign-in page already prints them, so a button
 * that uses them exposes nothing a reader could not already read.
 *
 * Each account lands on the screen that account exists to show, rather than
 * dropping everybody on the same dashboard.
 */
const DEMO_PASSWORD = "Sankhya@2026";

interface DemoAccount {
  role: string;
  email: string;
  icon: string;
  landing: string;
  sees: string;
}

const ACCOUNTS: DemoAccount[] = [
  {
    role: "Officer",
    email: "venkatesan@sankhya.gov.in",
    icon: "dashboard",
    landing: "/dashboard",
    sees: "A Deputy Director carrying 47 evidence records: a full Skill Twin, a critical GIS gap, and a self-rating two levels above the assessed one.",
  },
  {
    role: "Supervisor",
    email: "director.esd@sankhya.gov.in",
    icon: "team",
    landing: "/team",
    sees: "A division of 26 officers ordered by readiness, with the widest gap and the evidence count for each.",
  },
  {
    role: "Subject expert",
    email: "sme@sankhya.gov.in",
    icon: "review",
    landing: "/review",
    sees: "Questions generated from uploaded material, each shown beside the passage it was drawn from, waiting to be approved or rejected.",
  },
  {
    role: "Administrator",
    email: "admin@sankhya.gov.in",
    icon: "workforce",
    landing: "/admin",
    sees: "204 officers across 8 divisions and 3,685 evidence records, with capacity-building priorities and the draft ACBP.",
  },
];

export function DemoAccess({ compact = false }: { compact?: boolean }) {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function open(account: DemoAccount) {
    setBusy(account.email);
    setError(null);
    try {
      const { access_token } = await api.loginWithPassword(account.email, DEMO_PASSWORD);
      await signIn(access_token);
      navigate(account.landing);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : "The demonstration service did not respond. It may not be running on this deployment.",
      );
      setBusy(null);
    }
  }

  return (
    <div>
      <ul className={compact ? "grid gap-2" : "grid gap-3 sm:grid-cols-2 xl:grid-cols-4"}>
        {ACCOUNTS.map((a) => (
          <li key={a.email}>
            <button
              type="button"
              onClick={() => void open(a)}
              disabled={busy !== null}
              aria-busy={busy === a.email}
              className="flex h-full w-full flex-col items-start gap-1.5 rounded border border-rule bg-surface p-3.5 text-left hover:border-accent hover:bg-tint-accent disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded border border-rule bg-tint-accent text-accent">
                  <Icon name={a.icon} size={16} />
                </span>
                <span className="text-[14.5px] font-semibold text-ink">
                  {busy === a.email ? `Opening ${a.role}…` : `Open as ${a.role}`}
                </span>
              </span>
              {!compact && <span className="text-[12.5px] leading-snug text-ink-2">{a.sees}</span>}
              <span className="tabular text-[11.5px] text-ink-3">{a.email}</span>
            </button>
          </li>
        ))}
      </ul>
      {error && (
        <div className="mt-3">
          <ErrorNote message={error} />
        </div>
      )}
      <p className="mt-3 text-[12px] text-ink-3">
        Read-only demonstration over synthetic data. No record here belongs to a real officer. The same
        accounts are listed on the sign-in page; the password is <span className="font-semibold">{DEMO_PASSWORD}</span>.
      </p>
    </div>
  );
}
