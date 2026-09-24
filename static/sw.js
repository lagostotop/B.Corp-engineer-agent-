/* =========================================================
   BRAIN 3.0 SERVICE WORKER v5.5.6
   Production PWA with Network-First API
   ========================================================= */

const CACHE_NAME = "brain3-cache-v5-5-6";

const STATIC_CACHE = [
  "/",
  "/static/manifest.json?v=5-5-6",
  "/static/app.js?v=5-5-6",
  "/static/logo.png"
];

// INSTALL
self.addEventListener("install",event=>{
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache=>cache.addAll(STATIC_CACHE))
      .catch(err=>console.log("Brain 3.0 SW: Cache failed:",err))
  );
});

// ACTIVATE
self.addEventListener("activate",event=>{
  event.waitUntil(
    caches.keys().then(cacheNames=>
      Promise.all(
        cacheNames
          .filter(name=>name!==CACHE_NAME)
          .map(name=>caches.delete(name))
      )
    )
  );
  self.clients.claim();
  console.log("Brain 3.0 SW: Activated v5.5.6");
});

// FETCH
self.addEventListener("fetch",event=>{
  const url=new URL(event.request.url);

  // NEVER CACHE API/auth/external resources
  if(
    event.request.method!=="GET"||
    url.pathname.startsWith("/api/")||
    url.hostname.includes("supabase")||
    url.hostname.includes("cdn.jsdelivr")||
    url.hostname.includes("fonts.googleapis")||
    url.hostname.includes("fonts.gstatic")
  ){
    return;
  }

  // HTML: network first, cached fallback
  if(
    event.request.mode==="navigate"||
    event.request.headers.get("accept")?.includes("text/html")
  ){
    event.respondWith(
      fetch(event.request).catch(()=>caches.match("/"))
    );
    return;
  }

  // Static assets: cache first, network fallback/update
  event.respondWith(
    caches.match(event.request).then(cached=>{
      const fetchPromise=fetch(event.request)
        .then(response=>{
          if(response&&response.status===200){
            const responseClone=response.clone();
            caches.open(CACHE_NAME).then(cache=>{
              cache.put(event.request,responseClone);
            });
          }
          return response;
        })
        .catch(()=>cached);

      return cached||fetchPromise;
    })
  );
});