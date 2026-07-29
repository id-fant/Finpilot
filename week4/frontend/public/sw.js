const SHELL = "finpilot-shell-v1";
const SHELL_ASSETS = ["/", "/manifest.webmanifest"];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(SHELL).then(cache => cache.addAll(SHELL_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== SHELL).map(key => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  // Financial API data and state-changing requests must never be served from
  // an offline cache. The PWA is a read-only shell when disconnected.
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/ws/")) return;
  if (event.request.mode === "navigate") {
    event.respondWith(fetch(event.request).catch(() => caches.match("/")));
  }
});
