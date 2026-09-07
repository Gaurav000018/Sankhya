import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import {
  FALLBACK_LOCALE,
  LOCALES,
  MESSAGES,
  type Locale,
  type MessageKey,
} from "./locales";

/**
 * Translation, without a library.
 *
 * The app has one dimension of variation (language) and a few hundred strings,
 * so react-i18next would be more configuration than code. Three things this
 * does that a naive `t()` does not:
 *
 * 1. **Falls back to English**, never to the key. A user shown `nav.dashboard`
 *    learns nothing.
 * 2. **Sets `<html lang>`**, so a screen reader switches pronunciation and
 *    Devanagari is read as Hindi rather than mispronounced English.
 * 3. **Remembers the choice**, because an officer who reads Hindi should not
 *    have to pick it on every visit.
 */

const STORAGE_KEY = "sankhya.locale";

interface I18nState {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nState | null>(null);

function readStoredLocale(): Locale {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && (LOCALES as readonly string[]).includes(stored)) {
      return stored as Locale;
    }
    // No stored choice: honour the browser, since an officer whose device is
    // set to Hindi probably wants Hindi.
    const preferred = navigator.language?.slice(0, 2);
    if (preferred && (LOCALES as readonly string[]).includes(preferred)) {
      return preferred as Locale;
    }
  } catch {
    /* private browsing — fall through to the default */
  }
  return FALLBACK_LOCALE;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(readStoredLocale);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* the choice just will not persist */
    }
  }, []);

  const t = useCallback(
    (key: MessageKey, vars?: Record<string, string | number>) => {
      const message =
        MESSAGES[locale]?.[key] ?? MESSAGES[FALLBACK_LOCALE][key] ?? key;
      if (!vars) return message;
      return Object.entries(vars).reduce(
        (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
        message,
      );
    },
    [locale],
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nState {
  const context = useContext(I18nContext);
  if (!context) throw new Error("useI18n must be used inside I18nProvider");
  return context;
}

/** Convenience for components that only need to translate. */
export function useT() {
  return useI18n().t;
}

export { LOCALES, LOCALE_NAMES } from "./locales";
export type { Locale, MessageKey } from "./locales";
