self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open('bcorp-v1').then((cache) => {
      return cache.addAll([
        '/',
        '/static/manifest.json',
        '/static/icon-192.png'
      ]);
    })
  );
});

self.addEventListener('fetch', (e) => {
  e.respondWith(
    caches.match(e.request).then((response) => response || fetch(e.request))
  );
});
