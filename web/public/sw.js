// sw.js - Goodpath PWA Service Worker
const CACHE_NAME = 'goodpath-cache-v1';

// We want to aggressively cache maplibregl tiles and static assets so the app survives dead-zones
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      // Precache the core application shell
      return cache.addAll([
        '/',
        '/manifest.json',
        '/favicon.svg',
        '/styles.css'
      ]);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames
          .filter(name => name !== CACHE_NAME)
          .map(name => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Strategy: Stale-While-Revalidate for PMTiles and API reads
  // Exclude auth borders, admin paths, and POST requests
  if (
    event.request.method === 'GET' && 
    !url.pathname.startsWith('/admin') &&
    !url.pathname.startsWith('/auth')
  ) {
    event.respondWith(
      caches.match(event.request).then(cachedResponse => {
        const fetchPromise = fetch(event.request).then(networkResponse => {
          // Cache the fresh response dynamically
          if (networkResponse.ok) {
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, networkResponse.clone());
            });
          }
          return networkResponse;
        }).catch(() => {
          // Network failed, we either have the cached response or we return an offline mock if image
        });
        
        // Return cached immediately if we have it, but fetchPromise will update cache in background
        return cachedResponse || fetchPromise;
      })
    );
  }
});
