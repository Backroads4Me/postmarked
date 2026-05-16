// SSR: resolved inside Docker via service name or explicit env
const _SSR_BASE = import.meta.env.API_BASE_URL || "http://api:8000";

/**
 * Builds a full URL for server-side fetch calls (Astro frontmatter).
 * Never use in browser code — `http://api:8000` is Docker-internal.
 */
export function apiUrl(path) {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${_SSR_BASE}${p}`;
}

/**
 * Builds a root-relative URL for browser fetch calls (React islands, inline scripts).
 * Astro middleware proxies /api/* and /media/* to the backend, so no host needed.
 */
export function clientApiUrl(path) {
  const p = path.startsWith("/") ? path : `/${path}`;
  return p;
}

// Keep for backwards compat with any SSR pages still using the old export
export const API_BASE_URL = _SSR_BASE;
