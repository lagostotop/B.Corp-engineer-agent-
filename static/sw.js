/* =========================================================
   BRAIN 3.0 SERVICE WORKER v5.5.5
   Production PWA with Network-First API
   ========================================================= */

const CACHE_NAME = 'brain3-cache-v5-5-5'; // BUMPED for this deploy
const STATIC_CACHE = [
  '/',
  '/static/manifest.json?v=5-5-5', // Match your version
  '/static/app.js?v=5-5-5',        // Match your version
  '/static/brain3d.png',
  '/static/icon-180.png', 
  '/static/icon-192.png', 
  '/static/icon-512.png'
];

// INSTALL - Cache only static files
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(STATIC_CACHE))
      .catch(err => console.log('Brain 3.0 SW: Cache failed:', err))
  );
});

// ACTIVATE - Delete old caches
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
  console.log('Brain 3.0 SW: Activated v5.5.5');
});

// FETCH - Smart strategy
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // 1. NEVER CACHE: API, POST, CDN, Supabase, Fonts
  if (
    event.request.method !== 'GET' ||
    url.pathname.startsWith('/api/') || 
    url.hostname.includes('supabase') ||
    url.hostname.includes('cdn.jsdelivr') ||
    url.hostname.includes('fonts.googleapis') ||
    url.hostname.includes('fonts.gstatic')
  ) {
    return; // network only - IMPORTANT for auth
  }

  // 2. HTML PAGES: Network first, fallback to cache
  if (event.request.mode === 'navigate' || event.request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(event.request)
        .catch(() => caches.match('/')) 
    );
    return;
  }

  // 3. STATIC ASSETS: Cache first, then network + update cache
  event.respondWith(
    caches.match(event.request)
      .then(cached => {
        const fetchPromise = fetch(event.request).then(response => {
          if (response && response.status === 200) {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, responseClone);
            });
          }
          return response;
        }).catch(() => cached); // offline fallback
        return cached || fetchPromise;
      })
  );
});
