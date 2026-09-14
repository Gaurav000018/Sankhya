import { useEffect, useRef, useState } from "react";

/**
 * Google Sign-In, rendered by Google Identity Services.
 *
 * The button is Google's own, drawn into a container we provide. That is a
 * requirement of their brand terms, not a shortcut — and it means the flow never
 * touches a password field of ours.
 *
 * What comes back is an ID token (a signed JWT). It is handed straight to the
 * API, which verifies the signature against Google's published keys before
 * trusting a single claim in it. Nothing here treats the token as proof of
 * anything; this component only carries it.
 *
 * The script is loaded once per page and shared: two mounted buttons must not
 * race to add two copies of it.
 */

const SCRIPT_SRC = "https://accounts.google.com/gsi/client";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: Record<string, unknown>) => void;
          renderButton: (parent: HTMLElement, options: Record<string, unknown>) => void;
        };
      };
    };
  }
}

let scriptPromise: Promise<void> | null = null;

function loadGoogleScript(): Promise<void> {
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise<void>((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve();
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT_SRC}"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () => reject(new Error("blocked")));
      return;
    }
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    // Ad blockers and strict network policies both block this host. That is a
    // normal outcome, not an exception to surface as a crash.
    script.onerror = () => {
      scriptPromise = null;
      reject(new Error("blocked"));
    };
    document.head.appendChild(script);
  });
  return scriptPromise;
}

export function GoogleSignIn({
  clientId,
  onCredential,
  disabled,
}: {
  clientId: string;
  onCredential: (credential: string) => void;
  disabled?: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  // The callback is read through a ref so that re-rendering the parent does not
  // tear down and re-initialise Google's button.
  const callback = useRef(onCredential);
  callback.current = onCredential;

  useEffect(() => {
    let cancelled = false;

    loadGoogleScript()
      .then(() => {
        if (cancelled || !container.current || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: (response: { credential?: string }) => {
            if (response.credential) callback.current(response.credential);
          },
          // Off deliberately: One Tap pops up unprompted on page load, which on
          // a government sign-in page reads as a phishing overlay.
          auto_select: false,
          cancel_on_tap_outside: true,
        });
        window.google.accounts.id.renderButton(container.current, {
          theme: "filled_black",
          size: "large",
          shape: "pill",
          text: "signin_with",
          logo_alignment: "center",
          width: 360,
        });
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
    };
  }, [clientId]);

  if (failed) {
    return (
      <p className="text-center text-[12px] leading-relaxed text-ink-3">
        Google sign-in could not load — it is usually blocked by an ad blocker or
        a network policy. Use your password or an email code instead.
      </p>
    );
  }

  return (
    <div
      ref={container}
      // Google renders an iframe here and ignores pointer-events on its parent,
      // so a busy state has to dim and block at this level.
      className={`flex justify-center transition-opacity ${
        disabled ? "pointer-events-none opacity-50" : ""
      }`}
    />
  );
}

/** "or" rule, between the Google button and the password form. */
export function AuthDivider() {
  return (
    <div className="my-5 flex items-center gap-3">
      <span className="h-px flex-1 bg-rule" />
      <span className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-3">
        or
      </span>
      <span className="h-px flex-1 bg-rule" />
    </div>
  );
}
