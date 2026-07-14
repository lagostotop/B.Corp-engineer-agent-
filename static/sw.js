const CACHE_NAME = 'brain3-cache-v2';
const urlsToCache = [
  '/',
  '/static/index.html',
  '/static/manifest.json',
  '/static/icon-180.png',
  '/static/icon-192.png',
  '/static/icon-512.png',
  'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap',
  'https://cdn.jsdelivr.net/npm/marked@14.1.2/lib/marked.umd.js',
  'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2'
];

// Install - cache files
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

// Activate - delete old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(name => name !== CACHE_NAME)
                  .map(name => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// Fetch - serve from cache, fallback to network
self.addEventListener('fetch', event => {
  // Don't cache POST requests to /ask
  if (event.request.method !== 'GET') {
    return;
  }
  
  event.respondWith(
    caches.match(event.request)
      .then(cached => {
        return cached || fetch(event.request).then(response => {
          // Cache new files dynamically
          return caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, response.clone());
            return response;
          });
        });
      })
      .catch(() => caches.match('/static/index.html')) // Offline fallback
  );
});
