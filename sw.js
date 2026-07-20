/* Almacén Fitos — service worker
   Sube una versión nueva (cambia CACHE) cuando actualices index.html o sw.js.
   registro.json y alias.json se actualizan solos con estrategia stale-while-revalidate.
   El detalle de usos (/detalle/*.json, Capa 3) NO se precachea: son 14,6 MB en 2063
   ficheros. Se guarda bajo demanda en DETALLE, un caché aparte que sobrevive a los
   cambios de versión para no perder lo ya consultado en cada despliegue. */
var CACHE = 'fitos-v3';
var DETALLE = 'fitos-detalle';
var DETALLE_MAX = 300;          // ~2 MB en el peor caso; evicción del más antiguo
var CORE = [
  './',
  './index.html',
  './registro.json',
  './alias.json',
  './manifest.webmanifest',
  './icon-180.png',
  './icon-192.png',
  './icon-512.png',
  './icon-512-maskable.png'
];

self.addEventListener('install', function(e){
  self.skipWaiting();
  // Precache recurso a recurso: addAll() es atómico y un solo 404 (p. ej. alias.json
  // aún no publicado) dejaría la app sin nada cacheado y sin offline.
  e.waitUntil(caches.open(CACHE).then(function(c){
    return Promise.all(CORE.map(function(u){ return c.add(u).catch(function(){}); }));
  }));
});

self.addEventListener('activate', function(e){
  e.waitUntil(
    caches.keys().then(function(keys){
      // Se borran las versiones viejas del CORE, pero NUNCA el caché de detalle:
      // si no, cada despliegue vaciaría lo que el usuario ya tiene descargado.
      return Promise.all(keys.map(function(k){
        if(k !== CACHE && k !== DETALLE) return caches.delete(k);
      }));
    }).then(function(){ return self.clients.claim(); })
  );
});

/* Detalle de usos: cache-first (el contenido solo cambia al regenerar el sitio) con
   un tope simple de entradas; al superarlo se elimina la más antigua, que en la
   Cache API es la primera que devuelve keys(). */
function detalleResponse(req){
  return caches.open(DETALLE).then(function(cache){
    return cache.match(req).then(function(cached){
      if(cached) return cached;
      return fetch(req).then(function(res){
        if(res && res.ok){
          cache.put(req, res.clone()).then(function(){
            return cache.keys().then(function(keys){
              if(keys.length > DETALLE_MAX) return cache.delete(keys[0]);
            });
          }).catch(function(){});
        }
        return res;
      }).catch(function(){
        return new Response('', { status: 504, statusText: 'offline' });
      });
    });
  });
}

self.addEventListener('fetch', function(e){
  var req = e.request;
  if(req.method !== 'GET') return;
  var url;
  try { url = new URL(req.url); } catch(_) { return; }
  if(url.origin !== location.origin) return;   // solo mismo origen

  if(url.pathname.indexOf('/detalle/') !== -1){ e.respondWith(detalleResponse(req)); return; }

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
