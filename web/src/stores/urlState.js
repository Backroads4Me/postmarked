import { map } from 'nanostores';

// We manage a mapping of keys to their values via a map store
export const urlState = map({
  stop_id: null,
  media_id: null,
});

// Avoid executing browser APIs when SSR rendering in Astro
const isBrowser = typeof window !== 'undefined';

if (isBrowser) {
  // Prime store from URL on load
  const params = new URLSearchParams(window.location.search);
  const initial = {};
  for (const [key, value] of params.entries()) {
    initial[key] = value;
  }
  urlState.set({ ...urlState.get(), ...initial });

  // Subscribe to changes and mutate history
  urlState.listen((value) => {
    const url = new URL(window.location);
    let changed = false;

    Object.entries(value).forEach(([key, val]) => {
      if (val !== null && val !== undefined) {
        if (url.searchParams.get(key) !== String(val)) {
          url.searchParams.set(key, val);
          changed = true;
        }
      } else if (url.searchParams.has(key)) {
        url.searchParams.delete(key);
        changed = true;
      }
    });

    if (changed) {
      window.history.replaceState({}, '', url);
    }
  });

  // Watch for back/forward events to update store natively
  window.addEventListener('popstate', () => {
    const popParams = new URLSearchParams(window.location.search);
    const update = { stop_id: null, media_id: null };
    for (const [key, value] of popParams.entries()) {
      update[key] = value;
    }
    urlState.set(update);
  });
}
