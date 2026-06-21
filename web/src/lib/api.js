// SSR: resolved inside Docker via service name or explicit env
const _SSR_BASE = (typeof process !== "undefined" && process.env.API_BASE_URL) || import.meta.env.API_BASE_URL || "http://api:8000";

/**
 * Builds a full URL for server-side fetch calls (Astro frontmatter).
 * Never use in browser code — `http://api:8000` is Docker-internal.
 */
export function apiUrl(path) {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${_SSR_BASE}${p}`;
}
