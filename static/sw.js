// VidZora Service Worker - Network First with Auto-Purge
const CACHE_NAME = 'vidzora-cache-v2';

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  // Always fetch fresh from network for all HTML pages, scripts, and API requests
  if (
    e.request.mode === 'navigate' || 
    e.request.destination === 'document' || 
    e.request.destination === 'script' ||
    e.request.url.includes('/api/')
  ) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request))
    );
    return;
  }

  // Fallback for static media/icons
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
