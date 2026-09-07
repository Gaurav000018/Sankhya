import { useEffect } from "react";

import { useT } from "../i18n";
import type { MessageKey } from "../i18n";

/**
 * Keeps the browser tab title in step with the route, in the reader's language.
 *
 * A single-page app that never changes its title leaves every tab, bookmark and
 * history entry reading "SANKHYA" (WCAG 2.4.2 Page Titled). Taking a message key
 * rather than a string means a Hindi reader does not get a Hindi page sitting in
 * an English tab.
 */
export function usePageTitle(key: MessageKey) {
  const t = useT();
  useEffect(() => {
    document.title = `${t(key)} · SANKHYA`;
  }, [key, t]);
}
