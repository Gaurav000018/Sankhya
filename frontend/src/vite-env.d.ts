/// <reference types="vite/client" />

/**
 * Build-time configuration.
 *
 * Only variables prefixed `VITE_` reach the browser bundle, which is Vite's
 * guard against a server secret being inlined into public JavaScript by
 * accident. Nothing here is a secret — the API's address is visible in the
 * network tab the moment the page makes a request.
 */
interface ImportMetaEnv {
  /**
   * Origin of the SANKHYA API, e.g. `https://sankhya-api.example.gov.in`.
   *
   * Leave unset to call `/api/*` on the same origin — which is what the Vite
   * dev proxy serves, and what a host-level rewrite serves in production.
   * Setting it makes the browser call the API directly, so the API's
   * `CORS_ORIGINS` must then list this site's origin.
   */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
