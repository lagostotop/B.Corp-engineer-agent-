const CACHE_NAME = 'brain3-cache-v3'; // bump version to force update
const STATIC_CACHE = [
  '/',
  '/static/manifest.json',
  '/static/icon-180.png',
  '/static/icon-192.png',
  '/static/icon-512.png'
];

// Install - only cache static files
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(STATIC_CACHE))
      .catch(err => console.log('Cache failed:', err))
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

// Fetch - Network first for app, Cache first for static
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // 1. NEVER cache POST, /ask, /config, or supabase/CDN
  if (event.request.method !== 'GET' || 
      url.pathname.includes('/ask') || 
      url.pathname.includes('/config') ||
      url.hostname.includes('supabase') ||
      url.hostname.includes('cdn.jsdelivr') ||
      url.hostname.includes('fonts.googleapis')) {
    return fetch(event.request); // just go to network
  }

  // 2. For everything else: Cache first, then network
  event.respondWith(
    caches.match(event.request)
      .then(cached => {
        return cached || fetch(event.request).then(response => {
          // Only cache successful responses
          if(response && response.status === 200) {
            return caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, response.clone());
              return response;
            });
          }
          return response;
        });
      })
      .catch(() => caches.match('/')) // Offline fallback to home
  );
});
