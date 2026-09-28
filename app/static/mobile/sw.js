const CACHE_NAME = 'driveguardian-mobile-v1';
const ASSETS_TO_CACHE = [
  '/mobile',
  '/static/mobile/styles.css',
  '/static/mobile/app.js',
  '/static/mobile/manifest.json',
  '/static/mobile/icon-192.png',
  '/static/mobile/icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE).catch((err) => {
        console.warn('PWA cache prefetch note:', err);
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  // Do not intercept SSE stream or live MJPEG video streams or API calls
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/events-media/')) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(event.request).catch(() => {
        if (event.request.mode === 'navigate') {
          return caches.match('/mobile');
        }
      });
    })
  );
});
