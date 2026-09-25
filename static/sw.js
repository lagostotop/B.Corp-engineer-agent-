const CACHE_NAME="brain3-frontend-v11";

const STATIC_ASSETS=[
"/",
"/static/style.css?v=11",
"/static/app.js?v=11",
"/static/auth.js?v=11",
"/static/manifest.json",
"/static/logo.png",
"/static/icon-192.png",
"/static/icon-512.png"
];

self.addEventListener("install",event=>{
self.skipWaiting();

event.waitUntil(
caches.open(CACHE_NAME)
.then(cache=>cache.addAll(STATIC_ASSETS))
.catch(error=>console.warn("Brain 3.0 cache install:",error))
);
});

self.addEventListener("activate",event=>{
event.waitUntil(
caches.keys()
.then(keys=>
Promise.all(
keys
.filter(key=>key!==CACHE_NAME)
.map(key=>caches.delete(key))
)
)
.then(()=>self.clients.claim())
);
});

self.addEventListener("fetch",event=>{
const request=event.request;

if(request.method!=="GET")return;

const url=new URL(request.url);

if(
url.pathname.startsWith("/api/")||
url.hostname.includes("supabase")||
url.hostname.includes("cdn.jsdelivr.net")
){
return;
}

if(request.mode==="navigate"){
event.respondWith(
fetch(request)
.catch(()=>caches.match("/"))
);
return;
}

event.respondWith(
caches.match(request)
.then(cached=>{
const network=fetch(request)
.then(response=>{
if(response&&response.ok){
const clone=response.clone();

caches.open(CACHE_NAME)
.then(cache=>cache.put(request,clone));
}
return response;
})
.catch(()=>cached);

return cached||network;
})
);
});