// sw.js - Goodpath PWA Service Worker
const CACHE_NAME = 'goodpath-cache-v3';

// Astro hashes filenames for cache-busting (e.g. _astro/index.Dg3fK.js).
// These are immutable — serve cache-first with no revalidation.
// Non-hashed static assets (favicon, manifest, fonts, pmtiles) use
// stale-while-revalidate so they stay fresh without blocking the user.
const IMMUTABLE_RE = /\/_astro\//;

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll([
        '/manifest.json',
        '/favicon.svg',
      ]);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames =>
      Promise.all(
        cacheNames
          .filter(name => name !== CACHE_NAME)
          .map(name => caches.delete(name))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Never intercept admin, auth, API, or HTML pages
  const isCacheableAsset =
    event.request.method === 'GET' &&
    !url.pathname.startsWith('/admin') &&
    !url.pathname.startsWith('/auth') &&
    !url.pathname.startsWith('/api/') &&
    /\.(css|js|png|jpg|jpeg|gif|svg|ico|woff2|woff|ttf|pmtiles)(\?|$)/i.test(url.pathname);

  if (!isCacheableAsset) return;

  if (IMMUTABLE_RE.test(url.pathname)) {
    // Cache-first: hashed filenames never change, no need to revalidate
    event.respondWith(
      caches.match(event.request).then(cached => {
        if (cached) return cached;
        return fetch(event.request).then(response => {
          if (response.ok) {
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, response.clone()));
          }
          return response;
        });
      })
    );
  } else {
    // Stale-while-revalidate: return cache immediately, update in background
    event.respondWith(
      caches.open(CACHE_NAME).then(cache =>
        cache.match(event.request).then(cached => {
          const fetchPromise = fetch(event.request)
            .then(response => {
              if (response.ok) cache.put(event.request, response.clone());
              return response;
            })
            .catch(() => cached); // network failed — fall back to stale cache

          return cached || fetchPromise;
        })
      )
    );
  }
});
