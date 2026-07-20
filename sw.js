/* Almacén Fitos — service worker
   Sube una versión nueva (cambia CACHE) cuando actualices index.html o sw.js.
   registro.json se actualiza solo con estrategia stale-while-revalidate. */
var CACHE = 'fitos-v1';
var CORE = [
  './',
  './index.html',
  './registro.json',
  './manifest.webmanifest',
  './icon-180.png',
  './icon-192.png',
  './icon-512.png',
  './icon-512-maskable.png'
];

self.addEventListener('install', function(e){
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(function(c){ return c.addAll(CORE).catch(function(){}); }));
});

self.addEventListener('activate', function(e){
  e.waitUntil(
    caches.keys().then(function(keys){
      return Promise.all(keys.map(function(k){ if(k !== CACHE) return caches.delete(k); }));
    }).then(function(){ return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function(e){
  var req = e.request;
  if(req.method !== 'GET') return;
  var url;
  try { url = new URL(req.url); } catch(_) { return; }
  if(url.origin !== location.origin) return;   // solo mismo origen

  e.respondWith(
    caches.open(CACHE).then(function(cache){
      return cache.match(req).then(function(cached){
        var fetching = fetch(req).then(function(res){
          if(res && res.ok) cache.put(req, res.clone());
          return res;
        }).catch(function(){ return null; });

        if(cached){ return cached; }             // sirve del caché al instante; refresca en segundo plano
        return fetching.then(function(res){
          if(res) return res;
          if(req.mode === 'navigate') return cache.match('./index.html');
          return new Response('', { status: 504, statusText: 'offline' });
        });
      });
    })
  );
});
